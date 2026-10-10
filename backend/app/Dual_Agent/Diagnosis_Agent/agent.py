

from .architecture import diagnosis_agent
from .node_tools import map_specialization


def run_diagnosis_agent(raw_ocr_text: str, doctor_notes: str = "") -> dict:
    """
    Run the Diagnosis Agent end-to-end.

    Internally executes a 4-node LangGraph:
      Node 1 — Extract lab key/value pairs from raw OCR text
      Node 2 — Retrieve reference ranges from ChromaDB (RAG)
      Node 3 — Analyse labs vs. guidelines → primary hypothesis
      Node 4 — Evaluate diagnostic quality → confidence score, specialization

    Args:
        raw_ocr_text:  Text extracted from the uploaded lab report image (via OCR).
        doctor_notes:  Optional free-text context from the doctor or patient.

    Returns:
        dict with keys:
          primary_hypothesis, simple_explanation, detailed_analysis,
          extracted_lab_values, recommended_specialization,
          confidence_score, key_abnormalities, evaluation_notes, completeness_flag
    """
    context = (doctor_notes or "Patient uploaded a lab report for analysis.").strip()

    final_state = diagnosis_agent.invoke({
        "doctor_explanation":       context,
        "raw_lab_text":             raw_ocr_text,
        "extracted_lab_values":     {},
        "retrieved_lab_guidelines": "",
        "evaluation_results":       {},
        "evaluation_summary":       {},
        "retry_count":              0,
    })

    evaluation = final_state.get("evaluation_results", {})
    summary    = final_state.get("evaluation_summary", {})
    hypothesis = evaluation.get("primary_hypothesis", "General health concern")

    return {
        "primary_hypothesis":         hypothesis,
        "simple_explanation":         evaluation.get("simple_explanation", ""),
        "detailed_analysis":          evaluation.get("detailed_analysis", []),
        "extracted_lab_values":       final_state.get("extracted_lab_values", {}),
        "recommended_specialization": summary.get("recommended_specialization",
                                                   map_specialization(hypothesis)),
        "confidence_score":           summary.get("confidence_score", 75),
        "key_abnormalities":          summary.get("key_abnormalities", []),
        "evaluation_notes":           summary.get("evaluation_notes", ""),
        "completeness_flag":          summary.get("completeness_flag", "partial"),
    }
