# backend/routes/doctors_api.py
from fastapi import APIRouter, Query
from typing import List, Optional
from services.booking_service import load_doctors
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")

@router.get("/doctors", response_model=List[dict])
def get_doctors(specialization: Optional[str] = Query(None, description="Optional specialization filter")):
    """
    Returns the list of doctors. If 'specialization' query param provided, filters by that (case-insensitive).
    """
    docs = load_doctors()
    if specialization:
        s = specialization.strip().lower()
        docs = [d for d in docs if d.get("specialization") and s in d.get("specialization").lower()]
    return JSONResponse(content=docs)
