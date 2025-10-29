import json
from pathlib import Path
import hashlib
import secrets
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
USERS_FILE = DATA_DIR / "users.json"

# session tokens in-memory (for demo). Not persisted.
_sessions = {}

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def _load_users():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        # create default admin user
        default = {
            "users": [
                {
                    "username": "admin",
                    "password_hash": _hash_password("admin123")  # demo password
                }
            ]
        }
        USERS_FILE.write_text(json.dumps(default, indent=2))
    data = json.loads(USERS_FILE.read_text())
    return data.get("users", [])

def authenticate_admin(username: str, password: str) -> bool:
    users = _load_users()
    h = _hash_password(password)
    for u in users:
        if u.get("username") == username and u.get("password_hash") == h:
            return True
    return False

def create_session_token(username: str, ttl_minutes: int = 60*24):
    token = secrets.token_urlsafe(24)
    expires = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    _sessions[token] = {"username": username, "expires": expires}
    return token

def validate_token(token: str) -> bool:
    info = _sessions.get(token)
    if not info:
        return False
    if info["expires"] < datetime.utcnow():
        del _sessions[token]
        return False
    return True
