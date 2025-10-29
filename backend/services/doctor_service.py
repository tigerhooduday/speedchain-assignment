import json
from pathlib import Path
from services.auth_service import validate_token

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DOCTORS_FILE = DATA_DIR / "doctors.json"

def _ensure_doctors_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DOCTORS_FILE.exists():
        # create default 5-slot doctors (editable later)
        default = {
            "doctors": [
                {"id": 1, "name": "Dr. R.K. Gupta", "specialization": "Dermatology", "bio": "Senior dermatologist", "available_slots": ["Wed 10:00", "Fri 16:00"]},
                {"id": 2, "name": "Dr. Aditi Mehra", "specialization": "Physiotherapy", "bio": "Expert in sports injuries", "available_slots": ["Mon 11:00", "Thu 15:00"]},
                {"id": 3, "name": "Dr. Rohan Kapoor", "specialization": "Psychology", "bio": "Mental wellness coach", "available_slots": ["Tue 10:00", "Fri 12:00"]},
                {"id": 4, "name": "Ms. Nisha Bansal", "specialization": "Yoga & Fitness", "bio": "Holistic fitness trainer", "available_slots": ["Mon 9:00", "Wed 14:00"]},
                {"id": 5, "name": "Dr. Meena Sharma", "specialization": "Cardiology", "bio": "Heart specialist", "available_slots": ["Thu 11:00", "Sat 10:00"]}
            ]
        }
        DOCTORS_FILE.write_text(json.dumps(default, indent=2))

def get_all_doctors():
    _ensure_doctors_file()
    data = json.loads(DOCTORS_FILE.read_text())
    return data.get("doctors", [])

def get_doctor_by_id(doc_id: int):
    docs = get_all_doctors()
    for d in docs:
        if d["id"] == doc_id:
            return d
    return None

def update_doctor_by_id(doc_id: int, payload: dict, admin_token: str):
    # Simple token validation
    if not validate_token(admin_token):
        return None
    _ensure_doctors_file()
    data = json.loads(DOCTORS_FILE.read_text())
    docs = data.get("doctors", [])
    for i, d in enumerate(docs):
        if d["id"] == doc_id:
            # sanitize and update only allowed fields
            docs[i]["name"] = payload.get("name", d["name"])
            docs[i]["specialization"] = payload.get("specialization", d["specialization"])
            docs[i]["bio"] = payload.get("bio", d.get("bio", ""))
            docs[i]["available_slots"] = payload.get("available_slots", d.get("available_slots", []))
            data["doctors"] = docs
            DOCTORS_FILE.write_text(json.dumps(data, indent=2))
            return docs[i]
    return None
