

from .Diagnosis_Agent.agent import run_diagnosis_agent
from .Treatment_Agent.agent import run_treatment_agent
from .meta_evaluator import run_meta_evaluation


def run_dual_agent_pipeline(
    raw_ocr_text: str,
    doctor_notes: str = "",
    patient_symptoms: str = "",
) -> dict:
    """
    Run the full dual-agent pipeline:
      1. Diagnosis Agent  → structured diagnosis result
      2. Treatment Agent  → personalised treatment plan
      3. Meta-Evaluator   → cross-validation, safety verdict, quality score

    Args:
        raw_ocr_text:      OCR-extracted text from the lab report.
        doctor_notes:      Optional context from the doctor/patient.
        patient_symptoms:  Additional symptoms described in chat.

    Returns:
        Merged dict containing all diagnosis + treatment + meta-evaluation keys.
    """
    print("\n[DualAgent] ─── Starting Diagnosis Agent ───")
    diagnosis_result = run_diagnosis_agent(raw_ocr_text, doctor_notes)

    print("\n[DualAgent] ─── Starting Treatment Agent ───")

    diagnosis_result["doctor_explanation"] = doctor_notes
    treatment_result = run_treatment_agent(diagnosis_result, patient_symptoms)

    print("\n[DualAgent] ─── Starting Final Meta-Evaluator ───")

    _raw_treatment = {
        "severity_level":   treatment_result.get("severity_level", "moderate"),
        "prognosis":        treatment_result.get("prognosis", ""),
        "treatment_plan":   treatment_result.get("treatment_plan", []),
    }
    # Forward contraindications from treatment agent to meta-evaluator
    diagnosis_result["patient_constraints"] = treatment_result.get("patient_constraints", [])
    meta_result = run_meta_evaluation(
        diagnosis_result=diagnosis_result,
        treatment_result=_raw_treatment,
    )

    print("\n[DualAgent] ─── Pipeline Complete ───")

    return {
        "primary_hypothesis":         diagnosis_result.get("primary_hypothesis", "General health concern"),
        "simple_explanation":         diagnosis_result.get("simple_explanation", ""),
        "detailed_analysis":          diagnosis_result.get("detailed_analysis", []),
        "extracted_lab_values":       diagnosis_result.get("extracted_lab_values", {}),
        "recommended_specialization": diagnosis_result.get("recommended_specialization", "General Physician"),
        "confidence_score":           diagnosis_result.get("confidence_score", 75),
        "key_abnormalities":          diagnosis_result.get("key_abnormalities", []),
        "evaluation_notes":           diagnosis_result.get("evaluation_notes", ""),
        "completeness_flag":          diagnosis_result.get("completeness_flag", "partial"),
        "disease_explanation":        treatment_result.get("disease_explanation", ""),
        "treatment_plan":             treatment_result.get("treatment_plan", []),
        "prognosis":                  treatment_result.get("prognosis", ""),
        "follow_up":                  treatment_result.get("follow_up", ""),
        "severity_level":             treatment_result.get("severity_level", "moderate"),
        "follow_up_question":         treatment_result.get("follow_up_question", ""),
        "meta_evaluation":            meta_result,
    }
