

from .architecture import treatment_agent


def run_treatment_agent(diagnosis_result: dict, patient_symptoms: str = "") -> dict:
    """
    Run the standalone Treatment Agent end-to-end.

    Internally executes a 4-node LangGraph:
      Node 1 — Identify contraindications from labs and patient history
      Node 2 — Retrieve clinical management context from ChromaDB
      Node 3 — Generate a comprehensive, patient-safe treatment plan
      Node 4 — Assess severity and generate follow-up question

    Args:
        diagnosis_result:  Dict returned by run_diagnosis_agent() or run_diagnosis_only().
                           Must contain: primary_hypothesis, extracted_lab_values.
        patient_symptoms:  Additional symptoms described by the patient in chat.

    Returns:
        dict with keys:
          disease_explanation, treatment_plan, prognosis, follow_up,
          severity_level, follow_up_question
    """
    primary_hyp    = diagnosis_result.get("primary_hypothesis", "General health concern")
    extracted_labs = diagnosis_result.get("extracted_lab_values", {})
    doctor_notes   = diagnosis_result.get("doctor_explanation", "")
    symptoms       = (patient_symptoms or "None reported").strip()

    final_state = treatment_agent.invoke({
        "doctor_explanation":       doctor_notes,
        "extracted_lab_values":     extracted_labs,
        "primary_diagnosis":        primary_hyp,
        "patient_symptoms":         symptoms,
        "patient_constraints":      [],
        "clinical_context":         "",
        "optimized_treatment_plan": {},
        "severity_level":           "moderate",
        "follow_up_question":       "",
    })

    plan = final_state.get("optimized_treatment_plan", {})

    return {
        "disease_explanation": plan.get("disease_explanation", ""),
        "treatment_plan":      plan.get("optimized_treatment_plan", []),
        "prognosis":           plan.get("prognosis", ""),
        "follow_up":           plan.get("follow_up", ""),
        "severity_level":      final_state.get("severity_level", "moderate"),
        "follow_up_question":  final_state.get("follow_up_question",
                                                "Are you experiencing any new or worsening symptoms?"),
    }
