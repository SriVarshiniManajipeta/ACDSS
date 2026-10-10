

import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session as DbSession
from starlette.concurrency import run_in_threadpool

from .agent import action
from .database import get_db
from .messages import general_request, report_message
from .models import Appointment, ChatMessage, Doctor, Patient
from .schemas import AppointmentCreate, AppointmentOut, ChatResponse, DoctorOut
from .seed import seed_database
from .session import store

load_dotenv()

_env_origin = os.getenv("FRONTEND_ORIGIN", "")
ALLOWED_ORIGINS = [o.strip() for o in _env_origin.split(",") if o.strip()] or [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/bmp", "image/tiff"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(_app):
    seed_database()
    yield


app = FastAPI(title="ACDSS Clinical Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def doctor_to_out(doctor: Doctor) -> DoctorOut:
    return DoctorOut(
        id=doctor.id,
        name=doctor.name,
        specialization=doctor.specialization,
        hospital=doctor.hospital,
        location=doctor.location,
        experience_years=doctor.experience_years,
        rating=doctor.rating,
        available_slots=[
            s.strip() for s in (doctor.available_slots or "").split(",") if s.strip()
        ],
    )


PATIENT_FIELDS = {"name", "age", "gender", "phone"}
MAX_FIELD_CHARS = 120


def _parse_patient(raw: str) -> Optional[dict]:
    try:
        data = json.loads(raw or "{}")
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, dict):
        return None

    clean: dict = {}
    for key in PATIENT_FIELDS:
        value = data.get(key)
        if value in (None, ""):
            continue
        clean[key] = value[:MAX_FIELD_CHARS] if isinstance(value, str) else value
    return clean or None


def _ocr(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}'. Upload a JPG or PNG.",
        )

    # Starlette spools a large part to disk while parsing the form, but a plain
    # .read() still pulls the whole thing into memory — a 2 GB upload becomes
    # 2 GB RSS before this check ever runs. Read one byte past the limit and
    # no further, so an oversized upload never fully lands in memory.
    image_bytes = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 10 MB).")

    from .ocr import extract_text_from_image

    text = extract_text_from_image(image_bytes)
    if not text:
        raise HTTPException(
            status_code=422,
            detail="Couldn't read any text from that image. Try a clearer, "
                   "higher-resolution photo of the report.",
        )
    return text


# API_VERSION changes whenever the /chat contract changes. GET / reports it, so
# "is the server actually running my new code?" is one curl away instead of a
# 422 with no explanation.
API_VERSION = "agent-v2"


@app.get("/")
def root():
    return {
        "message": "ACDSS backend running",
        "api": API_VERSION,
        "chat_accepts": ["multipart/form-data", "application/json"],
    }


async def _read_turn(request: Request) -> tuple[dict, Optional[UploadFile]]:
    """Read one turn from either a multipart form or a JSON body.

    The frontend posts multipart because a turn may carry an image. Accepting
    JSON too means a cached older bundle, a curl, or any API client still works
    instead of failing with an opaque 422.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" in content_type or "x-www-form-urlencoded" in content_type:
        form = await request.form()
        upload = form.get("file")
        # A form field named "file" that isn't a file part (empty string, say)
        # is not an upload — treat it as absent rather than 422ing.
        if not hasattr(upload, "filename") or not getattr(upload, "filename", ""):
            upload = None
        return {
            "message": str(form.get("message") or ""),
            "session_id": str(form.get("session_id") or ""),
            "patient": str(form.get("patient") or "{}"),
        }, upload

    try:
        payload = await request.json()
    except Exception:                                  # noqa: BLE001
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    patient = payload.get("patient")
    return {
        "message": str(payload.get("message") or ""),
        "session_id": str(payload.get("session_id") or ""),
        "patient": json.dumps(patient) if isinstance(patient, dict) else "{}",
    }, None


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, db: DbSession = Depends(get_db)):
    """One turn of conversation. The agent decides everything that happens.

    The agent receives one string and nothing else:

        typed a message   →  that message
        attached an image →  the text OCR read off it

    No instruction is wrapped around either. Recognising that a page of lab
    values wants diagnosing is the agent's job; if this function said so, the
    flow would just be hardcoded one level further up.

    There is no third case and no `intent` flag. The Treatment button sends
    "Please build my treatment plan." like any other message — the agent
    already receives the conversation as `chat_history`.
    """
    fields, upload = await _read_turn(request)

    message = fields["message"]
    session = store.get_or_create(fields["session_id"] or None)
    parsed_patient = _parse_patient(fields["patient"])

    # The agent gets one string: what the patient typed, or what OCR read off
    # their image. Nothing is added to it — working out that a wall of lab
    # values wants diagnosing is the agent's job, not this function's.
    if upload is not None:
        raw_text = await run_in_threadpool(_ocr, upload)
        session.pending_report = raw_text          # authoritative copy for the tool
        session.report_note = message.strip()
        text = report_message(raw_text, message)
    else:
        text = general_request(message)

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Nothing to send — provide a message or an image.",
        )

    # action() blocks on the LLM; keep it off the event loop.
    turn = await run_in_threadpool(action, text, session.id, parsed_patient)

    db.add(ChatMessage(user_message=message or text[:500], ai_response=turn.reply))
    db.commit()

    return ChatResponse(
        session_id=turn.session_id,
        reply=turn.reply,
        events=turn.events,
        tools_used=turn.tools_used,
    )


@app.get("/doctors", response_model=list[DoctorOut])
def list_doctors(
    specialization: str | None = None,
    location:       str | None = None,
    db:             DbSession  = Depends(get_db),
):
    query = db.query(Doctor)
    if specialization:
        query = query.filter(Doctor.specialization == specialization)
    if location:
        query = query.filter(Doctor.location.ilike(f"%{location}%"))
    return [doctor_to_out(d) for d in query.order_by(Doctor.rating.desc()).all()]


@app.post("/appointments", response_model=AppointmentOut)
def create_appointment(req: AppointmentCreate, db: DbSession = Depends(get_db)):
    """Direct booking, for when the patient clicks a slot on a doctor card.

    The agent can also book conversationally; both paths write the same rows.
    A click is unambiguous, so it doesn't need to round-trip through the LLM.
    """
    doctor = db.query(Doctor).filter(Doctor.id == req.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    booked_session = store.get(req.session_id)

    patient = None
    if booked_session and booked_session.patient_id:
        patient = db.get(Patient, booked_session.patient_id)
    elif req.phone:
        patient = (
            db.query(Patient)
            .filter(Patient.name == req.patient_name, Patient.phone == req.phone)
            .first()
        )

    if patient is None:
        patient = Patient(
            name=req.patient_name, age=req.age, gender=req.gender, phone=req.phone
        )
        db.add(patient)
        db.flush()

    if booked_session:
        booked_session.patient_id = patient.id

    duplicate = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id,
            Appointment.doctor_id == doctor.id,
            Appointment.slot == req.slot,
            Appointment.status == "booked",
        )
        .first()
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="This slot is already booked.")

    appointment = Appointment(
        patient_id=patient.id, doctor_id=doctor.id, slot=req.slot, status="booked"
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    booking = {
        "id": appointment.id,
        "doctor_name": doctor.name,
        "patient_name": patient.name,
        "slot": appointment.slot,
        "status": appointment.status,
    }

    if booked_session is not None:
        booked_session.booking = booking
        booked_session.remember(
            "assistant",
            f"[Appointment booked with {doctor.name} at {appointment.slot}.]",
        )

    return AppointmentOut(**booking)
