# backend/routes/session.py
from fastapi import APIRouter, HTTPException
from services.session_service import get_session, load_all_sessions

router = APIRouter()

@router.get("/{session_id}")
def get_session_route(session_id: str):
    s = get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True, "session": s}

@router.get("/")
def list_sessions():
    # for debugging/demo only
    sessions = load_all_sessions()
    return {"ok": True, "sessions": sessions}
