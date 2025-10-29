# backend/services/booking_service.py
import json
from pathlib import Path
from typing import Optional
from services.email_service import send_confirmation_email
from datetime import datetime
from zoneinfo import ZoneInfo

from services.time_utils import now_ist_iso

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BOOKINGS_FILE = DATA_DIR / "bookings.json"
DOCTORS_FILE = DATA_DIR / "doctors.json"

def _ensure_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not BOOKINGS_FILE.exists():
        BOOKINGS_FILE.write_text(json.dumps([], indent=2))
    if not DOCTORS_FILE.exists():
        DOCTORS_FILE.write_text(json.dumps({"doctors": []}, indent=2))

def load_bookings():
    _ensure_files()
    try:
        return json.loads(BOOKINGS_FILE.read_text())
    except Exception:
        return []

def save_bookings(bookings):
    BOOKINGS_FILE.write_text(json.dumps(bookings, indent=2))

def load_doctors():
    _ensure_files()
    try:
        return json.loads(DOCTORS_FILE.read_text()).get("doctors", [])
    except Exception:
        return []

def find_doctor_by_name_or_id(identifier) -> Optional[dict]:
    docs = load_doctors()
    # id match
    try:
        iid = int(identifier)
        for d in docs:
            if d.get("id") == iid:
                return d
    except Exception:
        pass
    txt = str(identifier).lower()
    for d in docs:
        if d.get("name") and txt in d.get("name").lower():
            return d
    for d in docs:
        if d.get("specialization") and txt in d.get("specialization").lower():
            return d
    return None

def create_booking(doctor_id: int, patient_name: str, patient_email: str, requested_slot: str, note: str = "") -> dict:
    _ensure_files()
    bookings = load_bookings()
    doctors = load_doctors()
    doctor = next((d for d in doctors if d.get("id") == doctor_id), None)
    if not doctor:
        raise ValueError("Doctor not found")
    # conflict check
    for b in bookings:
        if b.get("doctor_id") == doctor_id and b.get("requested_slot") == requested_slot:
            raise ValueError("Slot already booked for this doctor")
        

    # created_at_ist = datetime.now(tz=ZoneInfo("Asia/Kolkata")).isoformat()
    created_at_ist = now_ist_iso()
    booking = {
        "id": (bookings[-1]["id"] + 1) if bookings else 1,
        "doctor_id": doctor_id,
        "doctor_name": doctor.get("name"),
        "patient_name": patient_name,
        "patient_email": patient_email,
        "requested_slot": requested_slot,
        "note": note or "",
        "created_at_ist": created_at_ist
    }
    bookings.append(booking)
    save_bookings(bookings)
    # send confirmation email if email_service configured
    try:
        subject = f"Appointment Confirmed — {doctor.get('name')}"
        body = f"Hello {patient_name},\n\nYour appointment with {doctor.get('name')} ({doctor.get('specialization')}) is confirmed for {requested_slot}.\n\nRegards,\nClinic"
        email_sent = send_confirmation_email(patient_email, subject, body)
        booking["email_sent"] = bool(email_sent)
    except Exception:
        booking["email_sent"] = False
    return booking
