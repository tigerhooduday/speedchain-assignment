# backend/services/intent_service.py
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DOCTORS_FILE = DATA_DIR / "doctors.json"

WEEKDAYS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
TIME_RE = re.compile(r'(\b\d{1,2}(:\d{2})?\s?(am|pm)\b)', re.IGNORECASE)
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
NAME_RE = re.compile(r"\b(?:my name is|i am|this is|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.IGNORECASE)

def _load_doctors():
    if not DOCTORS_FILE.exists():
        return []
    data = json.loads(DOCTORS_FILE.read_text())
    return data.get("doctors", [])

def find_doctor_by_text(text: str) -> Optional[Dict[str, Any]]:
    text_l = text.lower()
    docs = _load_doctors()
    # exact name match first
    for d in docs:
        if d["name"].lower() in text_l:
            return d
    # try partial name match (last name)
    for d in docs:
        parts = d["name"].lower().split()
        for p in parts:
            if p and p in text_l:
                return d
    # try specialization match
    for d in docs:
        if d.get("specialization") and d["specialization"].lower() in text_l:
            return d
    return None

def extract_email(text: str) -> Optional[str]:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else None

def extract_name(text: str) -> Optional[str]:
    m = NAME_RE.search(text)
    if m:
        return m.group(1).strip()
    # fallback: "this is Rahul" style
    m2 = re.search(r"\bthis is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text, re.IGNORECASE)
    if m2:
        return m2.group(1).strip()
    return None

def extract_time_and_day(text: str) -> Dict[str, Optional[str]]:
    # find explicit time like "3 pm"
    time_match = TIME_RE.search(text)
    time = time_match.group(1) if time_match else None

    # find weekday mention
    day = None
    for w in WEEKDAYS:
        if w in text.lower():
            day = w.capitalize()
            break
    # handle "tomorrow" and "next <weekday>"
    if "tomorrow" in text.lower():
        day = "Tomorrow"

    return {"time": time, "day": day}

def candidate_slots_for_doctor(doctor: Dict[str, Any], extracted_day: Optional[str], extracted_time: Optional[str]) -> List[str]:
    # From doctor's available_slots, try to pick matching ones
    slots = doctor.get("available_slots", []) or []
    candidates = []
    if extracted_day and extracted_day.lower() == "tomorrow":
        # we can't compute calendar date, so return all slots (UI will show)
        return slots
    if extracted_day:
        # match day token in slot string
        for s in slots:
            if extracted_day.lower() in s.lower():
                candidates.append(s)
    if extracted_time:
        for s in slots:
            if extracted_time.lower() in s.lower():
                if s not in candidates:
                    candidates.append(s)
    # fallback to full list
    if not candidates:
        return slots
    return candidates

def parse_intent(text: str) -> Dict[str, Any]:
    """
    Very small rule-based intent parser:
    Returns: { intent: str, doctor: optional dict, email, name, time, day, candidate_slots: [] }
    """
    text = text.strip()
    lower = text.lower()
    intent = "unknown"
    # basic intent check
    if any(k in lower for k in ["book", "appointment", "schedule", "reserve"]):
        intent = "book_appointment"
    # also if it contains doctor name but no book word, still book (user may say "I want Dr Gupta")
    doctor = find_doctor_by_text(text)
    if doctor and intent == "unknown":
        # user mentioned doctor only — assume booking intent
        intent = "book_appointment"

    email = extract_email(text)
    name = extract_name(text)
    time_day = extract_time_and_day(text)
    candidates = []
    if doctor:
        candidates = candidate_slots_for_doctor(doctor, time_day.get("day"), time_day.get("time"))

    return {
        "intent": intent,
        "doctor": doctor,
        "patient_email": email,
        "patient_name": name,
        "requested_time": time_day.get("time"),
        "requested_day": time_day.get("day"),
        "candidate_slots": candidates
    }
