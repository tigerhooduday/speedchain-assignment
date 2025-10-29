from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.auth_service import authenticate_admin, create_session_token, validate_token

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    ok = authenticate_admin(req.username, req.password)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_session_token(req.username)
    return {"token": token}

@router.get("/validate")
def validate(token: str):
    ok = validate_token(token)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"valid": True}
