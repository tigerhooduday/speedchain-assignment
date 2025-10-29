# backend/routes/voice.py
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import traceback, json, re, os
from services.transcribe_service import transcribe_audio_bytes
from services.llm_service import chat_with_llm, extract_entities_via_llm
from services.tts_service import text_to_speech_base64
from services.session_service import create_session, get_session, append_message, update_session
from services.booking_service import create_booking, find_doctor_by_name_or_id, load_doctors, load_bookings, save_bookings
from services.time_utils import now_ist_iso
from datetime import datetime

router = APIRouter()

# ---------------- constants & regex ----------------
GREET_RE = re.compile(r'\b(hi|hello|hey|good morning|good afternoon|good evening)\b', re.I)
BOOK_RE = re.compile(r'\b(book|appointment|reserve|schedule|need (?:a )?doctor|confirm)\b', re.I)
NAME_RE = re.compile(r'\b(my name is|i am|this is)\s+([A-Za-z\u00C0-\u024F\u0900-\u097F\s\'\-]+)', re.I)
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')

SPECIALTY_KEYWORDS = {
    "Dermatology": ["skin", "rash", "itch", "acne", "eczema", "psoriasis", "dermat"],
    "Cardiology": ["heart", "chest pain", "palpitation", "palpitations", "cardio", "blood pressure", "bp"],
    "Ophthalmology": ["eye", "vision", "blurry", "red eye", "eye pain"],
    "Dentistry": ["tooth", "teeth", "dental", "toothache", "cavity"],
    "General Medicine": ["fever","cough","cold","headache","pain","sick","ill","general physician","gp","physician"]
}

SPECIALTY_PHRASE_MAP = {
    "general physician": "General Medicine",
    "gp": "General Medicine",
    "general medicine": "General Medicine",
    "dermatology": "Dermatology",
    "cardiology": "Cardiology",
    "ophthalmology": "Ophthalmology",
    "dentistry": "Dentistry",
    "general": "General Medicine"
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LLM_DEBUG_PATH = os.path.join(DATA_DIR, "llm_debug.json")


def _append_llm_debug(entry: dict):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        arr = []
        if os.path.exists(LLM_DEBUG_PATH):
            try:
                with open(LLM_DEBUG_PATH, "r", encoding="utf-8") as f:
                    arr = json.load(f) or []
            except Exception:
                arr = []
        arr.append(entry)
        arr = arr[-300:]
        with open(LLM_DEBUG_PATH, "w", encoding="utf-8") as f:
            json.dump(arr, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------- helper functions ----------------
def detect_specialization_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    s = text.strip().lower()
    PHRASE_MAP = {
        "gp": "General Medicine",
        "general physician": "General Medicine",
        "general medicine": "General Medicine",
        "dermatology": "Dermatology",
        "cardiology": "Cardiology",
        "ophthalmology": "Ophthalmology",
        "dentistry": "Dentistry",
        "skin": "Dermatology",
        "tooth": "Dentistry",
    }
    for phrase, canon in PHRASE_MAP.items():
        if s == phrase or re.search(r'\b' + re.escape(phrase) + r'\b', s):
            return canon

    SYMPTOM_MAP = {
        "Dermatology": ["skin", "rash", "itch", "acne", "eczema", "psoriasis", "skin allergy", "rashes"],
        "Cardiology": ["heart", "chest pain", "palpitation", "palpitations", "shortness of breath", "heart pain"],
        "Ophthalmology": ["eye", "vision", "blurry", "red eye", "eye pain"],
        "Dentistry": ["toothache", "tooth", "teeth", "dental", "cavity"],
        "General Medicine": ["fever", "temperature", "cough", "cold", "headache", "body pain", "pain", "sore", "ill", "sick"]
    }

    for spec, terms in SYMPTOM_MAP.items():
        for t in terms:
            if re.search(r'\b' + re.escape(t) + r'\b', s):
                return spec
    for spec, terms in SYMPTOM_MAP.items():
        for t in terms:
            if t in s:
                return spec
    return None


def load_doctors_safe() -> List[Dict[str, Any]]:
    try:
        return load_doctors()
    except Exception:
        return [
            {"id": 1, "name": "Dr. R.K. Gupta", "specialization": "Dermatology", "available_slots": ["Wed 10:00", "Fri 16:00"]},
            {"id": 2, "name": "Dr. A. Sharma", "specialization": "General Medicine", "available_slots": ["Mon 11:00", "Thu 15:00"]},
        ]


def find_doctors_for_specialization(spec: str) -> List[Dict[str, Any]]:
    docs = load_doctors_safe()
    if not spec:
        return []
    spec_l = spec.lower().strip()
    matched = [d for d in docs if d.get("specialization") and spec_l == d.get("specialization").lower()]
    if matched:
        return matched
    matched = [d for d in docs if (d.get("specialization") and spec_l in d.get("specialization").lower()) or (d.get("name") and spec_l in d.get("name").lower())]
    return matched


def detect_doctor_name_in_text(text: str) -> Optional[Dict[str, Any]]:
    docs = load_doctors_safe()
    if not text:
        return None
    t = text.lower()
    for d in docs:
        name = (d.get("name") or "").lower()
        if name and name in t:
            return d
    for d in docs:
        name = (d.get("name") or "").lower()
        tokens = [tok for tok in re.split(r'\s+', name) if tok]
        for tok in tokens:
            if tok and re.search(r'\b' + re.escape(tok) + r'\b', t):
                return d
    return None


def extract_patient_name_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    try:
        m = NAME_RE.search(text)
        if m:
            return m.group(2).strip()
    except Exception:
        pass
    m2 = re.search(r'\bname[:\s]*([A-Za-z\u00C0-\u024F\u0900-\u097F\']{2,}(?:\s+[A-Za-z\u00C0-\u024F\u0900-\u097F\']{1,})?)', text, re.I)
    if m2:
        return m2.group(1).strip()
    words = [w.strip() for w in re.split(r'\s+', text) if w.strip()]

    def is_name_token(w: str) -> bool:
        try:
            return bool(re.fullmatch(r"[\w\u0900-\u097F'-]+", w))
        except Exception:
            return False

    if len(words) == 1 and is_name_token(words[0]) and len(words[0]) >= 2:
        return words[0]
    if len(words) == 2 and is_name_token(words[0]) and is_name_token(words[1]):
        return f"{words[0]} {words[1]}"
    return None


def is_negative_answer(text: str) -> bool:
    s = (text or "").strip().lower()
    return s in ("no", "nah", "n", "na", "none", "nope", "not", "no thanks", "no, thanks")


# slot helpers
DAY_ALIASES = {
    "mon": "Mon", "monday": "Mon",
    "tue": "Tue", "tues": "Tue", "tuesday": "Tue",
    "wed": "Wed", "wednesday": "Wed",
    "thu": "Thu", "thurs": "Thu", "thursday": "Thu",
    "fri": "Fri", "friday": "Fri",
    "sat": "Sat", "saturday": "Sat",
    "sun": "Sun", "sunday": "Sun"
}
TIME_RE = re.compile(r'(\d{1,2})(?::|[\s]?[\.]?[\s]?)(\d{1,2})?(?:[:\s]?(\d{1,2}))?\s*(am|pm)?', re.I)
DAY_RE = re.compile(r'\b(mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b', re.I)


def normalize_slot_text(slot: str) -> str:
    s = (slot or "").strip()
    day_m = DAY_RE.search(s)
    time_m = TIME_RE.search(s)
    day_part = day_m.group(0).title()[:3] if day_m else ""
    time_part = ""
    if time_m:
        try:
            h = int(time_m.group(1))
            m = time_m.group(2) or "00"
            ampm = time_m.group(4)
            if ampm:
                if ampm.lower().startswith("p") and h != 12:
                    h = (h % 12) + 12
                if ampm.lower().startswith("a") and h == 12:
                    h = 0
            time_part = f"{h:02d}:{int(m):02d}"
        except Exception:
            time_part = ""
    if not time_part:
        nums = re.findall(r'\d+', s)
        if len(nums) >= 1:
            try:
                h = int(nums[0])
                m = int(nums[1]) if len(nums) >= 2 else 0
                time_part = f"{h:02d}:{m:02d}"
            except Exception:
                time_part = ""
    if day_part and time_part:
        return f"{day_part} {time_part}"
    if time_part:
        return time_part
    return s


def match_slot_from_text(text: str, available_slots: List[str]) -> Optional[str]:
    if not text or not available_slots:
        return None
    norm_map = {}
    for s in available_slots:
        n = normalize_slot_text(s)
        norm_map[n.lower()] = s
    t = text.strip()
    for s in available_slots:
        if s.lower() in t.lower():
            return s
    user_norm = normalize_slot_text(t).lower()
    if user_norm in norm_map:
        return norm_map[user_norm]
    time_only = re.search(r'\b\d{1,2}(?::\d{2})?\s*(am|pm)?\b', t, re.I)
    if time_only:
        ut = time_only.group(0).strip().lower()
        for nkey, orig in norm_map.items():
            if ut in nkey or nkey.endswith(ut):
                return orig
        try:
            hh = int(re.findall(r'\d+', ut)[0])
            for nkey, orig in norm_map.items():
                m = re.search(r'(\d{1,2}):(\d{2})', nkey)
                if m and int(m.group(1)) == hh:
                    return orig
        except Exception:
            pass
    day_m = DAY_RE.search(t)
    if day_m:
        day_key = day_m.group(0).lower()
        day_norm = DAY_ALIASES.get(day_key, day_key.title()[:3])
        for nkey, orig in norm_map.items():
            if nkey.startswith(day_norm.lower()):
                if re.search(r'\d', t):
                    time_m = re.search(r'\d{1,2}(?::\d{2})?', t)
                    if time_m and time_m.group(0) in nkey:
                        return orig
                else:
                    return orig
    return None


# --- request model ---
class ConverseRequest(BaseModel):
    session_id: Optional[str] = None
    text: str


# ---------------- routes ----------------
@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        content = await file.read()
        result = transcribe_audio_bytes(content, filename_hint=file.filename or "audio.webm")
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/converse")
def converse(req: ConverseRequest):
    try:
        text = (req.text or "").strip()
        if not text:
            return {"ok": False, "error": "Empty text", "session_id": req.session_id}

        # session handling
        if req.session_id:
            session = get_session(req.session_id)
            if not session:
                session = create_session(preferred_id=req.session_id)
        else:
            session = create_session()
        sid = session["id"]

        append_message(sid, "user", text)

        # immediate patient name capture (explicit phrases)
        pname = extract_patient_name_from_text(text)
        if pname:
            meta = session.get("metadata", {}) or {}
            if not meta.get("patient_name"):
                meta["patient_name"] = pname
                session["metadata"] = meta
                update_session(sid, session)

        # ---------------- quick path: user said "book" AFTER we already suggested doctors from a complaint -----
        meta_now = session.get("metadata", {}) or {}
        if BOOK_RE.search(text) and not (meta_now.get("doctor_id") or meta_now.get("doctor_name")) and meta_now.get("provisional_note_from_complaint"):
            prov = meta_now.get("provisional_note_from_complaint")
            spec = detect_specialization_from_text(prov) or meta_now.get("detected_specialization")
            matched = find_doctors_for_specialization(spec) if spec else []
            if matched:
                first = matched[0]
                meta_now["doctor_id"] = first.get("id")
                meta_now["doctor_name"] = first.get("name")
                slots = first.get("available_slots", []) or []
                if slots:
                    meta_now["requested_slot"] = slots[0]
                session["metadata"] = meta_now
                update_session(sid, session)

                reply = f"Okay — I'll prepare a booking with {first.get('name')} ({first.get('specialization')}). May I have the patient's name, please?"
                tts = text_to_speech_base64(reply)
                append_message(sid, "assistant", reply)
                return {
                    "ok": True,
                    "session_id": sid,
                    "reply": reply,
                    "audio_base64": tts.get("audio_base64") if tts.get("ok") else None,
                    "expect": "ask_patient_info",
                    "doctors": matched
                }

        # 0) Quick doctor detection up-front (user mentioned specific doctor)
        doctor_detected = detect_doctor_name_in_text(text)
        if doctor_detected:
            # ensure slots variable exists
            slots = doctor_detected.get("available_slots", []) or []
            meta = session.get("metadata", {}) or {}
            if not meta.get("doctor_id"):
                meta["doctor_id"] = doctor_detected.get("id")
                meta["doctor_name"] = doctor_detected.get("name")
                session["metadata"] = meta
                update_session(sid, session)

            # try to match if user already provided a slot/time in same utterance
            matched_slot = match_slot_from_text(text, slots)
            if matched_slot:
                meta["requested_slot"] = matched_slot
                session["metadata"] = meta
                update_session(sid, session)
                missing = []
                if not meta.get("patient_name"):
                    missing.append("name")
                if not meta.get("patient_email"):
                    missing.append("email")
                if not missing:
                    reply = f"Got it — {doctor_detected.get('name')} at {matched_slot}. Should I confirm the booking? Reply 'yes' to confirm."
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "confirm"}
                else:
                    if "name" in missing:
                        reply = "May I have the patient's name, please?"
                    elif "email" in missing:
                        reply = "Please provide an email for confirmation."
                    else:
                        reply = f"{doctor_detected.get('name')} at {matched_slot}. What is the patient's name and email?"
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_patient_info"}

            if slots:
                reply = f"{doctor_detected.get('name')} is available at: {', '.join(slots)}. Which slot works for you?"
            else:
                reply = f"{doctor_detected.get('name')} — please tell me your preferred date/time."
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_slot", "doctors": [doctor_detected]}

        # 1) Greeting detection
        if GREET_RE.search(text):
            try:
                ist_iso = now_ist_iso()
                ist_hour = int(ist_iso[11:13])
                if 5 <= ist_hour < 12:
                    greet = "Good morning"
                elif 12 <= ist_hour < 17:
                    greet = "Good afternoon"
                elif 17 <= ist_hour < 22:
                    greet = "Good evening"
                else:
                    greet = "Hello"
            except Exception:
                greet = "Hello"
            reply = f"{greet}! How can I help you today?"
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "collecting"}

        # Booking intent: ask for complaint
        meta_now = session.get("metadata", {}) or {}
        has_complaint_or_doctor = bool(meta_now.get("chief_complaint") or meta_now.get("doctor_id") or meta_now.get("doctor_name"))
        if BOOK_RE.search(text) and not has_complaint_or_doctor and (session.get("state") not in ("confirming", "awaiting_notes", "done")):
            reply = "Sure — I can help with that. What problem are you experiencing or what symptoms do you have?"
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            session["state"] = "collecting"
            update_session(sid, session)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_complaint"}

        # Awaiting notes after booking
        if session.get("state") == "awaiting_notes":
            booking_id = session.get("pending_booking_id")
            user_txt = text.strip()
            if booking_id:
                bookings = load_bookings()
                b = next((x for x in bookings if x.get("id") == booking_id), None)
                if b:
                    if is_negative_answer(user_txt):
                        b["note"] = "NA"
                    else:
                        b["note"] = user_txt
                    save_bookings(bookings)
                    reply = f"Notes saved for booking #{b.get('id')}."
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    session["state"] = "done"
                    update_session(sid, session)
                    return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "booking": b}
                else:
                    reply = "I couldn't find the booking to attach notes."
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    session["state"] = "done"
                    update_session(sid, session)
                    return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None}

        # LLM-assisted extraction (only when needed)
        meta = session.get("metadata", {}) or {}
        needs_extraction = not (meta.get("chief_complaint") and (meta.get("doctor_id") or meta.get("doctor_name")) and meta.get("patient_name"))
        if needs_extraction:
            llm_resp = extract_entities_via_llm(text)
            if llm_resp.get("ok"):
                ent = llm_resp.get("entities", {})
                _append_llm_debug({"type": "extract_ok", "input": text, "entities": ent, "raw": llm_resp.get("raw_text")})
                if ent.get("chief_complaint"):
                    meta["chief_complaint"] = ent.get("chief_complaint")
                if ent.get("doctor_name"):
                    meta["doctor_name"] = ent.get("doctor_name")
                    doc = find_doctor_by_name_or_id(ent.get("doctor_name"))
                    if doc:
                        meta["doctor_id"] = doc.get("id")
                if ent.get("patient_name"):
                    meta["patient_name"] = ent.get("patient_name")
                if ent.get("patient_email"):
                    meta["patient_email"] = ent.get("patient_email")
                if ent.get("requested_slot"):
                    meta["requested_slot"] = ent.get("requested_slot")
                if ent.get("candidate_slots"):
                    meta["candidate_slots"] = ent.get("candidate_slots")
                session["metadata"] = meta
                update_session(sid, session)
            else:
                _append_llm_debug({"type": "extract_fail", "input": text, "error": llm_resp.get("error")})
                doc = detect_doctor_name_in_text(text)
                if doc:
                    meta["doctor_id"] = doc.get("id")
                    meta["doctor_name"] = doc.get("name")
                em = EMAIL_RE.search(text)
                if em:
                    meta["patient_email"] = em.group(0)
                pname = extract_patient_name_from_text(text)
                if pname and not meta.get("patient_name"):
                    meta["patient_name"] = pname
                spec = detect_specialization_from_text(text)
                if spec and not meta.get("chief_complaint"):
                    meta["chief_complaint"] = text
                    meta["detected_specialization"] = spec
                session["metadata"] = meta
                update_session(sid, session)

        # After extraction: if we have a complaint but no doctor: consider suggesting specialty conservatively
        meta = session.get("metadata", {}) or {}
        if meta.get("chief_complaint") and not (meta.get("doctor_id") or meta.get("doctor_name")):
            spec = meta.get("detected_specialization") or detect_specialization_from_text(meta.get("chief_complaint"))
            if spec:
                matched = find_doctors_for_specialization(spec)
                if matched:
                    lines = []
                    for d in matched:
                        slots = ", ".join(d.get("available_slots", [])) or "no slots"
                        lines.append(f"{d.get('name')} ({d.get('specialization')}) — {slots}")
                    reply = f"Based on that, I suggest {spec}. We have: " + " ; ".join(lines) + ". Which doctor would you prefer?"
                    meta["provisional_note_from_complaint"] = meta.get("chief_complaint")
                    session["metadata"] = meta
                    update_session(sid, session)
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_doctor", "doctors": matched}
            reply = "Could you tell me what problem or symptoms you have in more detail (so I can suggest the best specialist)?"
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_specialty"}

        # Doctor chosen but slot not chosen
        meta = session.get("metadata", {}) or {}
        if (meta.get("doctor_id") or meta.get("doctor_name")) and not meta.get("requested_slot"):
            doc = None
            if meta.get("doctor_id"):
                try:
                    doc = find_doctor_by_name_or_id(int(meta.get("doctor_id")))
                except Exception:
                    doc = find_doctor_by_name_or_id(meta.get("doctor_name"))
            else:
                doc = find_doctor_by_name_or_id(meta.get("doctor_name"))
            dname = doc.get("name") if doc else (meta.get("doctor_name") or "the requested doctor")
            slots = doc.get("available_slots", []) if doc else []
            matched_slot = match_slot_from_text(text, slots)
            if matched_slot:
                meta["requested_slot"] = matched_slot
                session["metadata"] = meta
                update_session(sid, session)
                missing = []
                if not meta.get("patient_name"):
                    missing.append("name")
                if not meta.get("patient_email"):
                    missing.append("email")
                if not missing:
                    reply = f"Got it — {dname} at {matched_slot}. Should I confirm the booking? Reply 'yes' to confirm."
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "confirm"}
                else:
                    if "name" in missing:
                        reply = "May I have the patient's name, please?"
                    elif "email" in missing:
                        reply = "Please provide an email for confirmation."
                    else:
                        reply = f"{dname} at {matched_slot}. What is the patient's name and email?"
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_patient_info"}
            if slots:
                reply = f"{dname} is available at: {', '.join(slots)}. Which slot works for you?"
            else:
                reply = f"{dname} — please tell me your preferred date/time."
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_slot"}

        # If requested slot present and user says 'book' -> confirm or ask missing fields
        meta = session.get("metadata", {}) or {}
        if meta.get("requested_slot") and BOOK_RE.search(text):
            missing = []
            if not meta.get("patient_name"):
                missing.append("name")
            if not meta.get("patient_email"):
                missing.append("email")
            if not missing:
                reply = f"Confirm: Book {meta.get('doctor_name') or meta.get('doctor_id')} for {meta.get('patient_name')} at {meta.get('requested_slot')}. Reply 'yes' to confirm."
                session["state"] = "confirming"
                update_session(sid, session)
                tts = text_to_speech_base64(reply)
                append_message(sid, "assistant", reply)
                return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "confirm"}
            else:
                if "name" in missing:
                    reply = "May I have the patient's name, please?"
                elif "email" in missing:
                    reply = "Please provide an email for confirmation."
                tts = text_to_speech_base64(reply)
                append_message(sid, "assistant", reply)
                return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_patient_info"}

        # If ready to confirm booking (all fields present)
        meta = session.get("metadata", {}) or {}
        missing = []
        if not (meta.get("doctor_id") or meta.get("doctor_name")):
            missing.append("doctor")
        if not meta.get("patient_name"):
            missing.append("name")
        if not meta.get("patient_email"):
            missing.append("email")
        if not meta.get("requested_slot"):
            missing.append("slot")
        if not missing and session.get("state") not in ("confirming", "awaiting_notes", "done"):
            doctor_label = meta.get("doctor_name") or f"Doctor #{meta.get('doctor_id')}"
            slot = meta.get("requested_slot")
            name = meta.get("patient_name")
            email = meta.get("patient_email")
            complaint = meta.get("provisional_note_from_complaint") or meta.get("chief_complaint") or ""
            reply = f"Confirm: Book {doctor_label} for {name} at {slot}. Reason: \"{complaint}\". Send confirmation to {email}? Reply 'yes' to confirm."
            session["state"] = "confirming"
            update_session(sid, session)
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "confirm"}

        # Confirming -> create booking on 'yes'
        if session.get("state") == "confirming":
            if text.strip().lower() in ("yes", "y", "confirm", "sure", "ok"):
                try:
                    doc_id = meta.get("doctor_id")
                    if not doc_id and meta.get("doctor_name"):
                        doc = find_doctor_by_name_or_id(meta.get("doctor_name"))
                        if doc:
                            doc_id = doc.get("id")
                    if not doc_id:
                        raise ValueError("Doctor not resolved")
                    pname = meta.get("patient_name")
                    pemail = meta.get("patient_email")
                    pslot = meta.get("requested_slot")
                    if not (pname and pemail and pslot):
                        raise ValueError("Incomplete booking details")
                    note = meta.get("provisional_note_from_complaint") or meta.get("chief_complaint") or ""
                    booking = create_booking(doctor_id=doc_id, patient_name=pname, patient_email=pemail, requested_slot=pslot, note=note)
                    booking["created_at_ist"] = now_ist_iso()
                    session["state"] = "awaiting_notes"
                    session["pending_booking_id"] = booking.get("id")
                    update_session(sid, session)
                    reply = f"Your appointment is confirmed — booking id {booking.get('id')}. Would you like to add any notes about the patient? Reply with notes or say 'no'."
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_notes", "booking": booking}
                except Exception as e:
                    traceback.print_exc()
                    reply = f"Booking failed: {e}"
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    return {"ok": False, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None}
            else:
                session["state"] = "collecting"
                update_session(sid, session)
                reply = "Okay — booking cancelled. How else can I help?"
                tts = text_to_speech_base64(reply)
                append_message(sid, "assistant", reply)
                return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None}

        # Ask next missing field heuristics
        if "doctor" in missing:
            spec = detect_specialization_from_text(text)
            if spec:
                matched = find_doctors_for_specialization(spec)
                if matched:
                    lines = [f"{d.get('name')} ({', '.join(d.get('available_slots', [])) or 'no slots'})" for d in matched]
                    reply = f"I recommend {spec}. Available: " + " ; ".join(lines) + ". Which doctor would you prefer?"
                    meta["detected_specialization"] = spec
                    session["metadata"] = meta
                    update_session(sid, session)
                    tts = text_to_speech_base64(reply)
                    append_message(sid, "assistant", reply)
                    return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_doctor", "doctors": matched}
            reply = "Which specialization or doctor would you like to see? (Example: 'Dermatology' or 'Dr. R. K. Gupta')."
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_doctor"}

        if "name" in missing:
            reply = "May I have the patient's name, please? A single name is fine."
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_name"}

        if "email" in missing:
            reply = "Please provide an email address for the confirmation."
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_email"}

        if "slot" in missing:
            cand = meta.get("candidate_slots") or []
            if cand:
                reply = f"I found these candidate slots: {', '.join(cand)}. Which one works for you?"
            else:
                reply = "Please tell me a preferred slot/time (e.g., 'tomorrow 3pm' or 'Fri 16:00')."
            tts = text_to_speech_base64(reply)
            append_message(sid, "assistant", reply)
            return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None, "expect": "ask_slot"}

        # fallback LLM follow-up if nothing else matched
        llm = chat_with_llm(text, system_prompt="You are Astra, a friendly receptionist assistant. Ask one concise follow-up question to continue booking.")
        if llm.get("ok") and llm.get("reply"):
            reply = llm.get("reply")
            _append_llm_debug({"type": "fallback_llm", "input": text, "llm": llm})
        else:
            reply = "Sorry, I didn't understand — could you rephrase?"
        tts = text_to_speech_base64(reply)
        append_message(sid, "assistant", reply)
        return {"ok": True, "session_id": sid, "reply": reply, "audio_base64": tts.get("audio_base64") if tts.get("ok") else None}

    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": str(e)}
