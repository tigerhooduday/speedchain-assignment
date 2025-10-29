# backend/services/session_service.py
import json
from pathlib import Path
import uuid
from datetime import datetime
from typing import Optional

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SESSIONS_FILE = DATA_DIR / "sessions.json"

def _ensure_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SESSIONS_FILE.exists():
        SESSIONS_FILE.write_text(json.dumps({}, indent=2))

def load_all_sessions():
    _ensure_file()
    try:
        return json.loads(SESSIONS_FILE.read_text())
    except Exception:
        return {}

def save_all_sessions(data: dict):
    _ensure_file()
    SESSIONS_FILE.write_text(json.dumps(data, indent=2))

def create_session(preferred_id: Optional[str] = None):
    """
    Create a session. If preferred_id is provided and not already used, the session will use that id.
    Returns the created session object (with .id).
    """
    sessions = load_all_sessions()
    # use preferred id if given and not colliding
    sid = preferred_id if preferred_id else str(uuid.uuid4())
    # ensure uniqueness; if preferred exists, generate a new one
    if sid in sessions:
        # if preferred exists, do not overwrite — return existing session
        return sessions[sid]
    sessions[sid] = {
        "id": sid,
        "created_at": datetime.utcnow().isoformat(),
        "messages": [],  # list of {role: 'user'|'assistant', text: "...", at: ts}
        "metadata": {},  # extracted fields: doctor_id, doctor_name, patient_name, patient_email, requested_slot
        "state": "collecting"  # collecting | confirming | done
    }
    save_all_sessions(sessions)
    return sessions[sid]

def get_session(session_id: str):
    sessions = load_all_sessions()
    return sessions.get(session_id)

def update_session(session_id: str, session_obj: dict):
    sessions = load_all_sessions()
    sessions[session_id] = session_obj
    save_all_sessions(sessions)
    return session_obj

def append_message(session_id: str, role: str, text: str):
    s = get_session(session_id)
    if not s:
        # create a new session using the session_id provided (so client's id will be honored)
        s = create_session(preferred_id=session_id)
    s.setdefault("messages", []).append({"role": role, "text": text, "at": datetime.utcnow().isoformat()})
    update_session(session_id, s)
    return s
