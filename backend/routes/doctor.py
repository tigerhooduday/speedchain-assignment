from fastapi import APIRouter, HTTPException, Body, Query
from typing import List, Optional
from pydantic import BaseModel
from services.doctor_service import get_all_doctors, update_doctor_by_id, get_doctor_by_id

router = APIRouter()

class DoctorModel(BaseModel):
    id: int
    name: str
    specialization: str
    bio: Optional[str] = ""
    available_slots: Optional[List[str]] = []

@router.get("/", response_model=List[DoctorModel])
def list_doctors():
    return get_all_doctors()

@router.get("/{doctor_id}", response_model=DoctorModel)
def get_doctor(doctor_id: int):
    doc = get_doctor_by_id(doctor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doc

@router.put("/{doctor_id}", response_model=DoctorModel)
def update_doctor(doctor_id: int, payload: DoctorModel = Body(...), admin_token: str = Query(..., description="Admin session token")):
    # Note: simple token validation delegated to auth_service inside update function
    updated = update_doctor_by_id(doctor_id, payload.dict(), admin_token)
    if not updated:
        raise HTTPException(status_code=403, detail="Unauthorized or update failed")
    return updated
