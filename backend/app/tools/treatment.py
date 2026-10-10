

from langchain_core.tools import tool

from app.session import blocked_after, current_session, emit


@tool
def build_treatment_plan(symptoms: str = "") -> str:
    """Build a personalised treatment plan from this patient's diagnosis.

    Requires a diagnosis to already exist. `symptoms` is everything the patient
    has described about how they currently feel — pass it through so the plan
    reflects the person, not only their lab numbers.

    Call this to produce a plan for the first time, or to redo it because
    something genuinely changed (new symptoms, a revised diagnosis). If a plan
    is already on record and the patient is asking something else — a general
    question, a detail about the existing plan — get_patient_record answers
    that without rebuilding anything.
    """
    if blocked_after("diagnosis"):
        return ("The diagnosis was produced moments ago, in this same turn. "
                "Stop here: the patient has only asked what the report says. "
                "Show them the diagnosis and let them ask for a plan.")

    session = current_session()
    diagnosis = session.diagnosis or {}

    if not session.has_diagnosis():
        return ("No diagnosis exists for this patient, so there is nothing to "
                "build a plan from. A lab report needs to be analysed first.")

    from app.Dual_Agent.Treatment_Agent.agent import run_treatment_agent

    treatment = run_treatment_agent(diagnosis, symptoms or "")
    session.treatment = treatment

    emit("treatment", {
        **treatment,
        "problem": {
            "hypothesis": diagnosis.get("primary_hypothesis"),
            "findings": diagnosis.get("key_abnormalities"),
            "plain": diagnosis.get("simple_explanation"),
        },
    })

    steps = [
        s.get("medication_or_action", "")
        for s in treatment.get("treatment_plan", [])
        if isinstance(s, dict)
    ]
    return (
        "Treatment plan ready. A card with every step is now on screen.\n"
        f"Overview: {treatment.get('disease_explanation', '')}\n"
        f"Steps: {'; '.join(filter(None, steps)) or 'see plan'}\n"
        f"Severity: {treatment.get('severity_level', 'moderate')}\n"
        f"Prognosis: {treatment.get('prognosis', '')}\n"
        f"Symptoms considered: {symptoms or 'none reported'}"
    )
