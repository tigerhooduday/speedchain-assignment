# speedchain-assignment — AI Receptionist Assistant

**Project**: AI Receptionist Assistant (FastAPI backend + React frontend)  
**Persona**: Astra — Virtual receptionist for *NovaCare Clinic* (sample clinic)

---

## Demo video
Include a short demo (3–6 minutes) showing:
1. Project architecture and files.
2. How to run backend & frontend locally.
3. Voice booking flow end-to-end (voice → transcription → LLM routing → TTS reply → booking creation → confirmation email).
4. Show `data/bookings.json` and the confirmation email received.

(Record with Loom or local screen recorder, upload `demo.mp4` or Loom link.)

---

## Repo structure (root)


```
speedchain-assignment/
├─ backend/
│ ├─ main.py
│ ├─ requirements.txt
│ ├─ routes/
│ ├─ services/
│ ├─ data/ # doctors.json, bookings.json, openai.json (template), smtp.json (template)
│ └─ ...
├─ frontend/
│ ├─ index.html
│ ├─ src/
│ └─ package.json
├─ README.md
└─ demo.mp4 (or loom-link.txt)
```



---

## Quick start — Backend

1. Create & activate a venv:
```bash
cd backend
python -m venv .venv
# windows
.venv\Scripts\activate
# unix
source .venv/bin/activate
pip install -r requirements.txt
```





1. Prepare `backend/data/`:

- `doctors.json` (seeded list, example below)
- `bookings.json` — **ensure** this file starts as a valid JSON array: `[]`
- `openai.json` (optional if using cloud LLM)
- `smtp.json` (optional: sample template provided; use App Password for Gmail)

Example `backend/data/doctors.json`:



```json
[
  {"id": 1, "name": "Dr. R.K. Gupta", "specialization": "Dermatology", "available_slots": ["Wed 10:00", "Fri 16:00"]},
  {"id": 2, "name": "Dr. A. Sharma", "specialization": "General Medicine", "available_slots": ["Mon 11:00", "Thu 15:00"]}
]

```



3. Run backend:

```
uvicorn main:app --reload --port 8000

```



## Quick start — Frontend (React / Vite)



```
cd frontend
npm install
npm run dev
# open http://localhost:3000

```

Make sure `API_BASE` in `src/components/AssistantButton.jsx` points to `http://localhost:8000/api`.

----------------------------------------------------------------------------------------------------------------------------------------------------------



`backend/data/openai.json` 

```
{ "api_key": "sk-REPLACE_WITH_YOUR_KEY" }
```



`backend/data/smtp.json` 

```
{
  "host": "smtp.gmail.com",
  "port": 587,
  "use_tls": true,
  "username": "your.email@gmail.com",
  "password": "APP_PASSWORD_OR_TOKEN",
  "from_email": "NovaCare Clinic <your.email@gmail.com>"
}

```





