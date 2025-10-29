# backend/routes/bookings_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from services.booking_service import create_booking, find_doctor_by_name_or_id, load_doctors
from services.time_utils import now_ist_iso

router = APIRouter(prefix="/api")

class BookingCreate(BaseModel):
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    patient_name: str
    patient_email: EmailStr
    requested_slot: str
    note: Optional[str] = ""

@router.post("/bookings/create")
def api_create_booking(payload: BookingCreate):
    # resolve doctor id if only name provided
    doctor_id = payload.doctor_id
    if not doctor_id and payload.doctor_name:
        doc = find_doctor_by_name_or_id(payload.doctor_name)
        if doc:
            doctor_id = doc.get("id")
    if not doctor_id:
        raise HTTPException(status_code=400, detail="doctor_id or valid doctor_name is required")
    try:
        booking = create_booking(
            doctor_id=int(doctor_id),
            patient_name=payload.patient_name,
            patient_email=payload.patient_email,
            requested_slot=payload.requested_slot,
            note=payload.note or ""
        )
        booking["created_at_ist"] = now_ist_iso()
        return {"ok": True, "booking": booking}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
