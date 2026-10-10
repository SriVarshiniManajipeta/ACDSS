
from langchain_core.tools import tool

from app.database import SessionLocal
from app.models import Appointment, Doctor, Patient
from app.session import blocked_after, current_session, emit


@tool
def book_appointment(doctor_name: str, slot: str, patient_name: str = "") -> str:
    """Book an appointment for this patient.

    Needs a real doctor, one of that doctor's real open slots, and the patient's
    name. Any of those missing comes back as a statement of what's missing.
    `patient_name` is only needed if the patient hasn't filled in their details.
    """
    blocked = blocked_after("diagnosis", "treatment", "doctors")
    if blocked:
        return (f"A {blocked} was produced moments ago, in this same turn. "
                "Booking is irreversible — the patient must pick a doctor and "
                "a slot themselves before this is called.")

    session = current_session()

    if not (doctor_name or "").strip():
        return "No doctor was specified."
    if not (slot or "").strip():
        return "No time slot was specified."

    name = session.patient_name() or (patient_name or "").strip()
    if not name:
        return ("The patient's name is not on record and none was supplied, so "
                "the booking cannot be made.")

    db = SessionLocal()
    try:
        matches = (
            db.query(Doctor).filter(Doctor.name.ilike(f"%{doctor_name.strip()}%")).all()
        )
        if not matches:
            return f"No doctor matching '{doctor_name}' is listed."
        if len(matches) > 1:
            return (f"Several doctors match '{doctor_name}': "
                    f"{'; '.join(d.name for d in matches)}")

        doctor = matches[0]
        available = [
            s.strip() for s in (doctor.available_slots or "").split(",") if s.strip()
        ]
        if available and slot.strip().lower() not in [s.lower() for s in available]:
            return (f"'{slot}' is not one of {doctor.name}'s open slots. "
                    f"Available: {', '.join(available)}")

        try:
            age = int(session.patient["age"]) if session.patient.get("age") else None
        except (TypeError, ValueError):
            age = None

        phone = session.patient.get("phone") or None

       
        patient = None
        if session.patient_id: 
            patient = db.get(Patient, session.patient_id)
        elif phone:
            patient = (
                db.query(Patient)
                .filter(Patient.name == name, Patient.phone == phone)
                .first()
            )

        if patient is None:
            patient = Patient(
                name=name, age=age,
                gender=session.patient.get("gender") or None, phone=phone,
            )
            db.add(patient)
            db.flush()

        session.patient_id = patient.id

        appointment = Appointment(
            patient_id=patient.id, doctor_id=doctor.id,
            slot=slot.strip(), status="booked",
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
        session.booking = booking
        emit("booking", booking)

        return (f"Appointment booked: {patient.name} with {doctor.name} at "
                f"{appointment.slot}. A confirmation card is on screen.")
    except Exception as exc:
        db.rollback()
        return f"The booking could not be saved: {exc}"
    finally:
        db.close()
