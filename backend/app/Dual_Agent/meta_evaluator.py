
import json
import re
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq

from dotenv import load_dotenv
load_dotenv()

_llm = None

def _get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0,
            max_tokens=2048,
            max_retries=2,
        )
    return _llm

def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}

_META_EVAL_PROMPT = PromptTemplate.from_template("""
You are a Chief Clinical AI Auditor. Review the complete ACDSS pipeline output below.
Your job is to cross-check whether the treatment plan is CONSISTENT with and SAFE for
the given diagnosis, identify any red flags or contradictions, and produce an overall
quality score for the full pipeline run.

Primary Diagnosis: {diagnosis}
Severity Level: {severity}
Key Abnormal Labs: {abnormalities}
Treatment Steps Count: {step_count}
Prognosis: {prognosis}
Contraindications flagged: {contraindications}

Evaluate:
1. Is the treatment plan consistent with the diagnosis?
2. Are there any critical safety concerns or dangerous omissions?
3. Does severity match the clinical picture?
4. What is the overall pipeline quality?

Return ONLY valid JSON:
{{
  "overall_quality_score": <integer 0-100>,
  "consistency_verdict": "consistent | minor_gaps | inconsistent",
  "safety_verdict": "safe_to_proceed | review_recommended | escalate_immediately",
  "safety_flags": ["flag1 if any, else empty list"],
  "clinical_summary": "2-3 sentence plain-English summary of the full clinical picture for the treating physician",
  "pipeline_recommendations": "1 sentence on what the physician should verify or do next"
}}
""")

def run_meta_evaluation(diagnosis_result: dict, treatment_result: dict) -> dict:
    """
    Final Meta-Evaluator (pipeline-level quality gate).
    Cross-checks the Diagnosis Agent output against the Treatment Agent output.
    """
    primary_hyp    = diagnosis_result.get("primary_hypothesis", "General health concern")
    key_abnormals  = diagnosis_result.get("key_abnormalities", [])
    severity       = treatment_result.get("severity_level", "moderate")
    prognosis      = treatment_result.get("prognosis", "")[:150]
    steps          = treatment_result.get("treatment_plan") or treatment_result.get("optimized_treatment_plan") or []

    contraindications = diagnosis_result.get("patient_constraints", [])

    print("\n[DualAgent] Call 3: Meta-Evaluator cross-validating pipeline output...")
    try:
        response = _get_llm().invoke(_META_EVAL_PROMPT.format(
            diagnosis=primary_hyp[:250],
            severity=severity,
            abnormalities="; ".join(key_abnormals[:5]) or "None flagged",
            step_count=len(steps),
            prognosis=prognosis,
            contraindications=", ".join(contraindications[:3]) or "None",
        ))
        meta = _parse_json(response.content)
    except Exception as e:
        print(f"[DualAgent] Meta-Evaluator LLM error: {e}")
        meta = {}

    quality  = meta.get("overall_quality_score", 80)
    verdict  = meta.get("safety_verdict", "review_recommended")
    print(f"[DualAgent] Meta-Eval done — quality: {quality}% | safety: {verdict}")

    return {
        "overall_quality_score":      quality,
        "consistency_verdict":        meta.get("consistency_verdict", "minor_gaps"),
        "safety_verdict":             verdict,
        "safety_flags":               meta.get("safety_flags", []),
        "clinical_summary":           meta.get("clinical_summary", ""),
        "pipeline_recommendations":   meta.get("pipeline_recommendations", ""),
    }
