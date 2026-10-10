

from langchain_core.tools import tool

from app.database import SessionLocal
from app.models import Doctor
from app.session import blocked_after, current_session, emit
from app.tools.specializations import snap_specialization


def _payload(doctor: Doctor) -> dict:
    return {
        "id": doctor.id,
        "name": doctor.name,
        "specialization": doctor.specialization,
        "hospital": doctor.hospital,
        "location": doctor.location,
        "experience_years": doctor.experience_years,
        "rating": doctor.rating,
        "available_slots": [
            s.strip() for s in (doctor.available_slots or "").split(",") if s.strip()
        ],
    }


@tool
def find_specialists(specialization: str = "", location: str = "") -> str:
    """Look up doctors and show them to the patient as bookable cards.

    `specialization` must be one of: General Physician, Cardiologist,
    Nephrologist, Endocrinologist, Gastroenterologist, Dermatologist,
    Neurologist, Orthopedic, Ophthalmologist, Psychiatrist, Pulmonologist,
    Emergency Medicine. Leave it blank to use the specialist their diagnosis
    suggests. `location` optionally filters by city.
    """
    blocked = blocked_after("diagnosis", "treatment")
    if blocked:
        return (f"A {blocked} was produced moments ago, in this same turn. Stop "
                "here: the patient has not asked to see a doctor. Show them what "
                "you have and let them ask.")

    session = current_session()
    suggested = (session.diagnosis or {}).get("recommended_specialization", "")
    spec = snap_specialization(specialization or suggested)

    db = SessionLocal()
    try:
        query = db.query(Doctor).filter(Doctor.specialization == spec)
        if location.strip():
            query = query.filter(Doctor.location.ilike(f"%{location.strip()}%"))
        doctors = query.order_by(Doctor.rating.desc()).limit(5).all()

        widened = False
        if not doctors and location.strip():
            widened = True
            doctors = (db.query(Doctor).filter(Doctor.specialization == spec)
                       .order_by(Doctor.rating.desc()).limit(5).all())
        if not doctors:
            spec = "General Physician"
            doctors = (db.query(Doctor).filter(Doctor.specialization == spec)
                       .order_by(Doctor.rating.desc()).limit(5).all())
        if not doctors:
            return f"No doctors are listed for {spec}."

        payload = [_payload(d) for d in doctors]
        emit("doctors", {"specialization": spec, "doctors": payload})

        listing = "\n".join(
            f"- {d['name']} ({d['specialization']}, {d['hospital']}, {d['location']}) "
            f"— rating {d['rating']}, {d['experience_years']}y experience, "
            f"slots: {', '.join(d['available_slots']) or 'none listed'}"
            for d in payload
        )
        note = (f"\nNo {spec}s were listed in '{location}', so this is the wider list."
                if widened else "")
        return f"{len(payload)} {spec}(s) shown to the patient as cards:\n{listing}{note}"
    finally:
        db.close()


@tool
def get_doctor_availability(doctor_name: str) -> str:
    """Look up one doctor's open appointment slots by name. Partial names work."""
    name = (doctor_name or "").strip()
    if not name:
        return "No doctor name was given."

    db = SessionLocal()
    try:
        matches = db.query(Doctor).filter(Doctor.name.ilike(f"%{name}%")).all()
        if not matches:
            return f"No doctor matching '{name}' is listed."
        if len(matches) > 1:
            options = "; ".join(
                f"{d.name} ({d.specialization}, {d.location})" for d in matches
            )
            return f"Several doctors match '{name}': {options}"

        doctor = matches[0]
        slots = [
            s.strip() for s in (doctor.available_slots or "").split(",") if s.strip()
        ]
        return (
            f"{doctor.name} — {doctor.specialization} at {doctor.hospital}, "
            f"{doctor.location} (rating {doctor.rating}). "
            f"Open slots: {', '.join(slots) if slots else 'none listed'}"
        )
    finally:
        db.close()
