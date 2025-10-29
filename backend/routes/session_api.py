# backend/routes/session_api.py
from fastapi import APIRouter
from services.session_service import create_session

router = APIRouter(prefix="/api")

@router.post("/session/new")
def new_session():
    """
    Create a fresh session id and return it.
    """
    sess = create_session()
    return {"ok": True, "session_id": sess.get("id")}
