from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, doctor, booking,  voice, session
from routes import doctors_api, bookings_api
from routes import session_api
from routes import voice

app = FastAPI(title="Speedchain Assignment - AI Receptionist Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth")
app.include_router(doctor.router, prefix="/api/doctors")
app.include_router(booking.router, prefix="/api/bookings")
app.include_router(voice.router, prefix="/api/voice")
app.include_router(session.router, prefix="/api/sessions")
app.include_router(doctors_api.router)
app.include_router(bookings_api.router)
app.include_router(session_api.router)
app.include_router(voice.router, prefix="/api/voice")

@app.get("/")
def root():
    return {"status": "ok", "message": "AI Receptionist backend is running"}
