

import json

from langchain_core.tools import tool

from app.session import Session, current_session, emit
from app.tools.specializations import snap_specialization


def _archive_report(session: Session, raw_text: str, diagnosis: dict) -> None:
    """Persist the analysed report. Best-effort: a DB hiccup must not lose a
    diagnosis the patient is already looking at."""
    try:
        from app.database import SessionLocal
        from app.models import ReportUpload

        db = SessionLocal()
        try:
            db.add(ReportUpload(
                patient_name=session.patient_name() or "Guest",
                raw_text=raw_text,
                hypothesis=diagnosis.get("primary_hypothesis", ""),
                specialization=diagnosis.get("recommended_specialization", ""),
            ))
            db.commit()
        finally:
            db.close()
    except Exception as exc:                       
        print(f"[ACDSS] could not archive report: {exc}")


@tool
def analyze_lab_report(patient_context: str = "") -> str:
    """Analyse the lab report the patient uploaded in this conversation.

    Reads the uploaded report itself — you do not pass the report text.
    `patient_context` is anything the patient said that bears on it: symptoms,
    how long they've felt this way, medications, pregnancy, existing conditions.
    Pass it along so the analysis accounts for the person, not just the numbers.
    """
    session = current_session()
    text = (session.pending_report or "").strip()

    if not text:
        if session.has_diagnosis():
            return ("No new report was uploaded. A diagnosis already exists for "
                    "this patient; get_patient_record returns it.")
        return "No lab report has been uploaded in this conversation."

    context = " ".join(filter(None, [session.report_note, patient_context])).strip()

    from app.Dual_Agent.Diagnosis_Agent.agent import run_diagnosis_agent

    diagnosis = run_diagnosis_agent(text, doctor_notes=context)
    diagnosis["recommended_specialization"] = snap_specialization(
        diagnosis.get("recommended_specialization", "")
    )

    session.diagnosis = diagnosis
    session.pending_report = None  
    session.report_note = ""
    session.analysed_reports += 1
    emit("diagnosis", diagnosis)

    _archive_report(session, text, diagnosis)

    abnormalities = diagnosis.get("key_abnormalities") or []
    return (
        "Diagnosis complete. A card with the full lab table is now on screen.\n"
        f"Primary hypothesis: {diagnosis.get('primary_hypothesis', 'N/A')}\n"
        f"Plain explanation: {diagnosis.get('simple_explanation', '')}\n"
        f"Key abnormalities: {', '.join(abnormalities) or 'none noted'}\n"
        f"Confidence: {diagnosis.get('confidence_score', 'N/A')}\n"
        f"Suggested specialist: {diagnosis.get('recommended_specialization')}\n"
        f"Context used: {context or 'none provided'}"
    )


@tool
def get_patient_record(query: str = "") -> str:
    """Recall this patient's diagnosis, lab values, treatment plan, and booking.

    Use this before answering anything about their results, so the answer comes
    from what was actually found rather than from memory of earlier turns.
    `query` is optional and just describes what you're looking for.
    """
    session = current_session()
    diagnosis = session.diagnosis or {}
    treatment = session.treatment or {}

    if not (diagnosis or treatment or session.booking):
        return "No lab report has been analysed for this patient yet."

    lines = []

    if diagnosis:
        lines.append("=== DIAGNOSIS ===")
        lines.append(f"Condition: {diagnosis.get('primary_hypothesis', 'N/A')}")
        if diagnosis.get("simple_explanation"):
            lines.append(f"Explanation: {diagnosis['simple_explanation']}")
        if diagnosis.get("key_abnormalities"):
            lines.append(f"Key findings: {', '.join(diagnosis['key_abnormalities'])}")
        if diagnosis.get("extracted_lab_values"):
            lines.append(f"Lab values: {json.dumps(diagnosis['extracted_lab_values'])}")
        if diagnosis.get("recommended_specialization"):
            lines.append(f"Suggested specialist: {diagnosis['recommended_specialization']}")

    if treatment:
        lines.append("\n=== TREATMENT PLAN ===")
        if treatment.get("disease_explanation"):
            lines.append(f"Overview: {treatment['disease_explanation']}")
        for step in treatment.get("treatment_plan", []):
            if isinstance(step, dict):
                lines.append(
                    f"- {step.get('medication_or_action', '')}: "
                    f"{step.get('dosage_or_detail', '')}"
                )
        if treatment.get("prognosis"):
            lines.append(f"Outlook: {treatment['prognosis']}")
        if treatment.get("severity_level"):
            lines.append(f"Severity: {treatment['severity_level']}")

    if session.booking:
        lines.append(
            f"\n=== APPOINTMENT ===\n{session.booking['patient_name']} with "
            f"{session.booking['doctor_name']} at {session.booking['slot']}"
        )

    return "\n".join(lines)
