# backend/routes/booking.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
import json
from pathlib import Path
from services.email_service import send_confirmation_email

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
BOOKINGS_FILE = DATA_DIR / "bookings.json"
DOCTORS_FILE = DATA_DIR / "doctors.json"

class BookingRequest(BaseModel):
    doctor_id: int
    patient_name: str
    patient_email: EmailStr
    requested_slot: str  # must be one of doctor's available_slots ideally
    note: Optional[str] = None

def _ensure_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not BOOKINGS_FILE.exists():
        BOOKINGS_FILE.write_text(json.dumps([], indent=2))
    if not DOCTORS_FILE.exists():
        DOCTORS_FILE.write_text(json.dumps({"doctors": []}, indent=2))

@router.post("/create")
def create_booking(req: BookingRequest):
    _ensure_files()
    bookings = json.loads(BOOKINGS_FILE.read_text()) if BOOKINGS_FILE.exists() else []
    doctors = json.loads(DOCTORS_FILE.read_text()).get("doctors", []) if DOCTORS_FILE.exists() else []

    doctor = next((d for d in doctors if d.get("id") == req.doctor_id), None)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Conflict check
    for b in bookings:
        if b.get("doctor_id") == req.doctor_id and b.get("requested_slot") == req.requested_slot:
            raise HTTPException(status_code=409, detail="Requested slot already booked for this doctor")

    note = req.note or ""
    if req.requested_slot not in doctor.get("available_slots", []):
        note = note + " [requested slot not in doctor's listed slots]"

    booking = {
        "id": (bookings[-1]["id"] + 1) if bookings else 1,
        "doctor_id": req.doctor_id,
        "doctor_name": doctor.get("name"),
        "patient_name": req.patient_name,
        "patient_email": req.patient_email,
        "requested_slot": req.requested_slot,
        "note": note
    }
    bookings.append(booking)
    BOOKINGS_FILE.write_text(json.dumps(bookings, indent=2))

    subject = f"Appointment Confirmed — {doctor.get('name')}"
    body = f"Hello {req.patient_name},\n\nYour appointment with {doctor.get('name')} ({doctor.get('specialization')}) is confirmed for {req.requested_slot}.\n\nRegards,\nNovaCare Wellness Clinic"
    email_sent = send_confirmation_email(req.patient_email, subject, body)
    booking["email_sent"] = bool(email_sent)

    return {"ok": True, "booking": booking, "email_sent": booking["email_sent"]}

@router.get("/list")
def list_bookings():
    _ensure_files()
    try:
        bookings = json.loads(BOOKINGS_FILE.read_text())
        return {"ok": True, "bookings": bookings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{booking_id}")
def get_booking(booking_id: int):
    _ensure_files()
    try:
        bookings = json.loads(BOOKINGS_FILE.read_text())
        b = next((x for x in bookings if x.get("id") == booking_id), None)
        if not b:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {"ok": True, "booking": b}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
