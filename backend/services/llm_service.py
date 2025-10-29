# backend/services/llm_service.py
"""
LLM service wrapper using OpenAI v1.x client.
Extended entity extraction to include 'chief_complaint' to help suggest specializations.
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any

OPENAI_CFG_FILE = Path(__file__).resolve().parents[2] / "data" / "openai.json"

def _load_openai_key() -> Optional[str]:
    if OPENAI_CFG_FILE.exists():
        try:
            data = json.loads(OPENAI_CFG_FILE.read_text())
            return data.get("api_key")
        except Exception:
            return None
    return None

def _create_client(api_key: str):
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("OpenAI library not available: " + str(e))
    return OpenAI(api_key=api_key)

def _safe_extract_json_from_text(text: str) -> Optional[dict]:
    if not text:
        return None
    # fenced json
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if m:
        s = m.group(1)
        try:
            return json.loads(s)
        except Exception:
            pass
    # balanced braces
    start = text.find('{')
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i+1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        break
    # fallback kv lines
    lines = text.splitlines()
    kv = {}
    for ln in lines:
        if ':' in ln:
            k,v = ln.split(':',1)
            k = k.strip().lower().replace(" ", "_")
            v = v.strip()
            if k in ("doctor_name","doctor","patient_name","patient_email","requested_slot","slot","time","email","chief_complaint","complaint"):
                if k.startswith("doctor"):
                    kv["doctor_name"] = v
                elif "email" in k:
                    kv["patient_email"] = v
                elif k.startswith("patient"):
                    kv["patient_name"] = v
                elif "slot" in k or "time" in k:
                    kv["requested_slot"] = v
                elif "complaint" in k:
                    kv["chief_complaint"] = v
    if kv:
        return kv
    return None

def chat_with_llm(prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
    key = _load_openai_key()
    if not key:
        lower = prompt.lower()
        if any(w in lower for w in ["book", "appointment", "schedule", "reserve"]):
            reply = ("I can help book an appointment. Tell me doctor name or specialization, patient name, email and preferred slot/time.")
        elif any(g in lower for g in ["hi","hello","hey"]):
            reply = "Hi! I'm Astra, your clinic assistant."
        else:
            reply = "No cloud LLM configured. Please provide booking details plainly."
        return {"ok": True, "reply": reply}

    try:
        client = _create_client(key)
    except Exception as e:
        return {"ok": False, "error": f"Failed to init OpenAI client: {e}"}

    try:
        # use Responses API
        if system_prompt:
            resp = client.responses.create(
                model="gpt-4o-mini",
                instructions=system_prompt,
                input=[{"role":"user","content":[{"type":"input_text","text":prompt}]}],
                max_output_tokens=512,
                temperature=0.2
            )
        else:
            resp = client.responses.create(
                model="gpt-4o-mini",
                input=[{"role":"user","content":[{"type":"input_text","text":prompt}]}],
                max_output_tokens=512,
                temperature=0.2
            )
        text_out = ""
        try:
            text_out = resp.output_text if hasattr(resp, "output_text") else ""
        except Exception:
            text_out = ""

        if not text_out:
            try:
                out = getattr(resp, "output", None) or (resp.get("output") if isinstance(resp, dict) else None)
                if out and isinstance(out, list):
                    parts = []
                    for itm in out:
                        if isinstance(itm, dict) and "content" in itm and isinstance(itm["content"], list):
                            for c in itm["content"]:
                                if isinstance(c, dict) and c.get("type") == "output_text":
                                    parts.append(c.get("text",""))
                        elif isinstance(itm, str):
                            parts.append(itm)
                    text_out = " ".join([p for p in parts if p]).strip()
            except Exception:
                pass

        if not text_out:
            try:
                text_out = resp["choices"][0]["message"]["content"]
            except Exception:
                pass

        if not text_out:
            return {"ok": False, "error": "LLM returned empty response"}
        return {"ok": True, "reply": text_out.strip()}
    except Exception as e:
        return {"ok": False, "error": f"LLM call failed: {e}"}

def extract_entities_via_llm(text: str) -> Dict[str, Any]:
    """
    Asks LLM to return JSON that includes 'chief_complaint' to help map to specialization.
    Output keys:
      - intent
      - doctor_name
      - patient_name
      - patient_email
      - requested_slot
      - candidate_slots
      - chief_complaint
    """
    key = _load_openai_key()
    if not key:
        return {"ok": False, "error": "No OpenAI key configured"}

    try:
        client = _create_client(key)
    except Exception as e:
        return {"ok": False, "error": f"OpenAI client init failed: {e}"}

    instruction = (
        "You MUST output ONLY one valid JSON object (no extra text). The JSON keys must be: "
        "\"intent\" (string, 'book_appointment' or 'unknown'), "
        "\"doctor_name\" (string|null), "
        "\"patient_name\" (string|null), "
        "\"patient_email\" (string|null), "
        "\"requested_slot\" (string|null), "
        "\"candidate_slots\" (array), "
        "\"chief_complaint\" (string|null). "
        "If unsure about any field, use null or empty array. Example: "
        "{\"intent\":\"book_appointment\",\"doctor_name\":\"Dr. R.K. Gupta\",\"patient_name\":\"Rahul Verma\",\"patient_email\":\"rahul@example.com\",\"requested_slot\":\"Fri 16:00\",\"candidate_slots\":[],\"chief_complaint\":\"skin rash\"}"
    )

    try:
        resp = client.responses.create(
            model="gpt-4o-mini",
            instructions=instruction,
            input=[{"role":"user","content":[{"type":"input_text","text": text}]}],
            max_output_tokens=512,
            temperature=0.0
        )

        text_out = ""
        try:
            text_out = resp.output_text if hasattr(resp, "output_text") else ""
        except Exception:
            text_out = ""

        if not text_out:
            try:
                out = getattr(resp, "output", None) or (resp.get("output") if isinstance(resp, dict) else None)
                if out and isinstance(out, list):
                    parts = []
                    for itm in out:
                        if isinstance(itm, dict) and "content" in itm and isinstance(itm["content"], list):
                            for c in itm["content"]:
                                if isinstance(c, dict) and c.get("type") == "output_text":
                                    parts.append(c.get("text",""))
                        elif isinstance(itm, str):
                            parts.append(itm)
                    text_out = " ".join([p for p in parts if p]).strip()
            except Exception:
                pass

        if not text_out:
            try:
                text_out = resp["choices"][0]["message"]["content"]
            except Exception:
                pass

        if not text_out:
            return {"ok": False, "error": "LLM returned no text for entity extraction"}

        parsed = _safe_extract_json_from_text(text_out)
        if parsed is None:
            try:
                parsed = json.loads(text_out)
            except Exception:
                parsed = None

        if parsed is None:
            return {"ok": False, "error": "Failed to parse JSON from LLM output", "raw": text_out}

        entities = {
            "intent": parsed.get("intent") if isinstance(parsed.get("intent"), str) else ("book_appointment" if "book" in text.lower() else "unknown"),
            "doctor_name": parsed.get("doctor_name") or None,
            "patient_name": parsed.get("patient_name") or None,
            "patient_email": parsed.get("patient_email") or None,
            "requested_slot": parsed.get("requested_slot") or None,
            "candidate_slots": parsed.get("candidate_slots") or parsed.get("slots") or [],
            "chief_complaint": parsed.get("chief_complaint") or None
        }
        if not isinstance(entities["candidate_slots"], list):
            try:
                entities["candidate_slots"] = [s.strip() for s in str(entities["candidate_slots"]).split(",") if s.strip()]
            except Exception:
                entities["candidate_slots"] = []
        return {"ok": True, "entities": entities, "raw_text": text_out}
    except Exception as e:
        return {"ok": False, "error": f"LLM extraction failed: {e}"}
