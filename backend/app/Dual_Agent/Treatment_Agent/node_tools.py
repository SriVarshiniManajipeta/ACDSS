

import json
import re
from langchain_core.prompts import PromptTemplate

from .llm_models import llm, retriever
from .model import TreatmentAgentState

def _content_text(content) -> str:
    """Flatten an LLM response's `.content` into plain text.

    Usually a string, but some providers return message content as a list of
    blocks (e.g. `[{"type": "text", "text": "..."}]`) instead of a flat
    string — seen from Gemini under certain response shapes. A bare
    `_parse_json(response.content)` then raised
    `AttributeError: 'list' object has no attribute 'strip'` before the JSON
    parse ever ran, silently degrading every node's output to `{}`.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ]
        return " ".join(p for p in parts if p)
    return str(content or "")


def _parse_json(text: str) -> dict:
    """Safely extract a JSON object from an LLM response."""
    text = text.strip()
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _constraint_check_node(state: TreatmentAgentState) -> dict:
    """Node 1 — Identify contraindications from labs and patient history."""
    print("[TreatmentAgent] Node 1: Checking contraindications...")
    prompt = PromptTemplate.from_template("""
Review the patient's lab results and doctor's notes.
Identify any conditions that would constrain or contraindicate certain treatments.

Primary Diagnosis: {diagnosis}
Patient Lab Results: {labs}
Doctor's Notes: {notes}
Patient Symptoms: {symptoms}

Return ONLY valid JSON:
{{"contraindications": ["list of constraints or none"]}}
Start with {{ end with }}.
""")
    try:
        response = llm.invoke(prompt.format(
            diagnosis=state.get("primary_diagnosis", "")[:500],
            labs=json.dumps(dict(list(state.get("extracted_lab_values", {}).items())[:10])),
            notes=state.get("doctor_explanation", "")[:500],
            symptoms=state.get("patient_symptoms", "None reported")[:500],
        ))
        extracted = _parse_json(_content_text(response.content))
    except Exception as e:
        print(f"[TreatmentAgent] Node 1 LLM error: {e}")
        extracted = {}
    constraints = extracted.get("contraindications", [])
    constraints = [
        c for c in constraints
        if isinstance(c, str) and c.lower().strip() not in ("none", "n/a", "no contraindications", "no constraints", "")
    ]
    print(f"[TreatmentAgent] Found {len(constraints)} contraindications.")
    return {"patient_constraints": constraints}


def _clinical_context_node(state: TreatmentAgentState) -> dict:
    """Node 2 — Retrieve clinical management context from ChromaDB."""
    print("[TreatmentAgent] Node 2: Retrieving clinical context...")
    diagnosis = state.get("primary_diagnosis", "")[:500]
    try:
        docs = retriever.invoke(
            f"Clinical management, treatment, and monitoring for: {diagnosis}"
        )
        context = "\n".join(d.page_content[:400] for d in docs)[:2000]
    except Exception as e:
        print(f"[TreatmentAgent] Node 2 retriever error: {e}")
        context = ""
    return {"clinical_context": context}


def _treatment_generation_node(state: TreatmentAgentState) -> dict:
    """Node 3 — Generate a comprehensive, patient-safe treatment plan."""
    print("[TreatmentAgent] Node 3: Generating treatment plan...")
    prompt = PromptTemplate.from_template("""
You are a Treatment Planner Agent. Generate a comprehensive, patient-safe clinical plan.
MUST respect the listed contraindications. Consider reported symptoms when tailoring the plan.

Primary Diagnosis: {diagnosis}
Patient Symptoms: {symptoms}
Patient Constraints / Contraindications: {constraints}
Clinical Context (from knowledge base): {context}

Return ONLY valid JSON:
{{
  "disease_explanation": "Brief 2-sentence patient-friendly explanation",
  "optimized_treatment_plan": [
    {{
      "medication_or_action": "...",
      "dosage_or_detail": "...",
      "rationale": "..."
    }}
  ],
  "prognosis": "Expected outcome with treatment (1-2 sentences)",
  "follow_up": "Recommended follow-up tests or monitoring schedule"
}}
Start with {{ end with }}.
""")
    try:
        response = llm.invoke(prompt.format(
            diagnosis=state.get("primary_diagnosis", "")[:500],
            symptoms=state.get("patient_symptoms", "None reported")[:500],
            constraints=json.dumps(state.get("patient_constraints", [])[:6]),
            context=state.get("clinical_context", "")[:2000],
        ))
        result = _parse_json(_content_text(response.content))
    except Exception as e:
        print(f"[TreatmentAgent] Node 3 LLM error: {e}")
        result = {}
    print("[TreatmentAgent] Plan generated.")
    return {"optimized_treatment_plan": result}


def _treatment_evaluation_node(state: TreatmentAgentState) -> dict:
    """Node 4 — Severity assessment and targeted follow-up question generation."""
    print("[TreatmentAgent] Node 4: Assessing severity and generating follow-up...")
    plan         = state.get("optimized_treatment_plan", {})
    diagnosis    = state.get("primary_diagnosis", "")
    symptoms     = state.get("patient_symptoms", "")
    constraints  = state.get("patient_constraints", [])
    steps        = plan.get("optimized_treatment_plan", [])

    prompt = PromptTemplate.from_template("""
You are a Senior Clinical Evaluator. Assess the overall clinical severity
and generate one targeted follow-up question the clinician should ask the patient.

Diagnosis: {diagnosis}
Patient Symptoms: {symptoms}
Contraindications: {constraints}
Treatment Steps Count: {step_count}
Prognosis: {prognosis}

Follow-up question rules:
- For "critical/severe": focus on emergency warning signs to watch for
- For "moderate": focus on lifestyle triggers or comorbidities
- For "mild": focus on monitoring and prevention

Return ONLY valid JSON:
{{
  "severity_level": "mild | moderate | severe | critical",
  "severity_rationale": "1 sentence explaining severity choice",
  "follow_up_question": "Single clear question to ask the patient next"
}}

Start with {{ end with }}.
""")
    try:
        response = llm.invoke(prompt.format(
            diagnosis=diagnosis[:500],
            symptoms=symptoms[:500] or "Not specified",
            constraints=", ".join(constraints[:6]) or "None",
            step_count=len(steps),
            prognosis=plan.get("prognosis", "")[:300],
        ))
        result = _parse_json(_content_text(response.content))
    except Exception as e:
        print(f"[TreatmentAgent] Node 4 LLM error: {e}")
        result = {}

    severity   = result.get("severity_level", "moderate")
    follow_up  = result.get("follow_up_question",
                            "Are you currently experiencing any new or worsening symptoms?")

    print(f"[TreatmentAgent] Severity: {severity} | Follow-up: {follow_up}")
    return {
        "severity_level":    severity,
        "follow_up_question": follow_up,
    }
