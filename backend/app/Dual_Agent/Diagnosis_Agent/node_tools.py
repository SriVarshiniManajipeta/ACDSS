

import json
import re

from langchain_core.prompts import PromptTemplate

from .llm_models import llm, retriever
from .model import DiagnosisAgentState

from langgraph.graph import StateGraph, END

_SPEC_RULES = [
    (("diabetes", "glucose", "hba1c", "insulin", "glycated",
      "thyroid", "tsh", "endocrine"),                              "Endocrinologist"),
    (("cardiac", "heart", "cholesterol", "ldl", "hdl",
      "triglyceride", "lipid", "troponin"),                        "Cardiologist"),
    (("liver", "hepatic", "hepatitis", "cirrhosis", "ast", "alt",
      "bilirubin", "pancreatic", "amylase", "lipase"),             "Gastroenterologist"),
    (("neurological", "seizure", "migraine", "neuropathy",
      "stroke", "epilepsy"),                                        "Neurologist"),
    (("lung", "respiratory", "pneumonia", "asthma", "copd",
      "tuberculosis", "tb"),                                        "Pulmonologist"),
    (("kidney", "renal", "creatinine", "bun", "urea",
      "nephritis", "gfr", "proteinuria"),                           "Nephrologist"),
    (("psychiatric", "depression", "anxiety", "bipolar",
      "mental health"),                                             "Psychiatrist"),
    (("bone", "fracture", "arthritis", "osteoporosis",
      "vitamin d", "calcium"),                                      "Orthopedic"),
    (("skin", "dermatitis", "eczema", "psoriasis", "rash"),        "Dermatologist"),
]


def map_specialization(hypothesis: str) -> str:
    """Map a free-text primary hypothesis to the nearest doctor specialization."""
    text = hypothesis.lower()
    for keywords, spec in _SPEC_RULES:
        if any(k in text for k in keywords):
            return spec
    return "General Physician"

def route_evaluation(state: DiagnosisAgentState) -> str:
    summary = state.get("evaluation_summary", {})
    score = summary.get("confidence_score", 100)
    retry_count = state.get("retry_count", 0)
    
    if score < 80 and retry_count <= 2:
        print(f"[DiagnosisAgent] Confidence score {score} is low. Retrying analysis (Attempt {retry_count})...")
        return "analyze_labs"
    return END


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
    """Safely extract a JSON object from an LLM response, ignoring filler text."""
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


_EXTRACT_PROMPT = PromptTemplate.from_template("""
You are a medical data extraction specialist.
Read the raw text extracted (via OCR) from a lab report.
Identify ALL laboratory tests and their corresponding numeric values (including units).

Doctor's Context: {explanation}
Raw Lab Text: {text}

Return ONLY a valid JSON dictionary where:
- keys   = Test Name  (e.g. "Glucose", "HbA1c", "AST")
- values = Result     (e.g. "189 mg/dL", "8.1 %", "240 IU/L")

Do NOT include markdown, code fences, or the word "json".
Start your response with {{ and end with }}.
""")


def _extract_labs_node(state: DiagnosisAgentState) -> dict:
    """Node 1 — Use the LLM to pull structured key→value pairs from raw OCR text."""
    print("[DiagnosisAgent] Node 1: Extracting lab values from OCR text...")

    try:
        response = llm.invoke(_EXTRACT_PROMPT.format(
            explanation=state["doctor_explanation"][:300],
            text=state["raw_lab_text"][:6000],
        ))
        extracted = _parse_json(_content_text(response.content))
    except Exception as e:
        print(f"[DiagnosisAgent] Node 1 LLM error: {e}")
        extracted = {}
    print(f"[DiagnosisAgent] Extracted {len(extracted)} lab values.")
    return {"extracted_lab_values": extracted}


def _retrieve_context_node(state: DiagnosisAgentState) -> dict:
    """Node 2 — Query ChromaDB for normal ranges and clinical significance of each test."""
    print("[DiagnosisAgent] Node 2: Retrieving reference ranges from knowledge base...")

    combined = ""
    for test in list(state["extracted_lab_values"].keys())[:10]:
        print(f"  -> Searching: {test}")
        try:
            docs = retriever.invoke(
                f"What is the normal reference range and clinical significance of {test}?"
            )
            chunk = "\n".join(d.page_content[:400] for d in docs)
            combined += f"\n--- {test} ---\n{chunk}"
        except Exception as e:
            print(f"[DiagnosisAgent] Node 2 retriever error for {test}: {e}")
        if len(combined) > 4000:
            break

    return {"retrieved_lab_guidelines": combined}


_ANALYZE_PROMPT = PromptTemplate.from_template("""
You are an expert Clinical Decision Support Agent.
Evaluate the patient's lab results strictly using the provided Medical Reference Text.
Take the Doctor's Context into consideration when writing your summary.

Doctor's Context: {explanation}
Patient Lab Results (JSON): {lab_inputs}
Medical Reference Text (from RAG Database): {context}
{evaluator_feedback}

For each test, determine if it is Normal, High, or Low based on the reference text.
If abnormal, list the potential clinical causes or associated diseases.

Return ONLY a valid JSON object in this exact structure:
{{
  "primary_hypothesis": "A concise 1-2 sentence summary of the most likely condition",
  "simple_explanation": "2-3 sentences in plain everyday English a patient can understand. No jargon.",
  "detailed_analysis": [
    {{
      "test_name": "...",
      "patient_value": "...",
      "reference_range": "...",
      "status": "Normal | High | Low | Borderline",
      "potential_causes": ["...", "..."]
    }}
  ]
}}

Do NOT include markdown, code fences, or the word "json".
Start your response with {{ and end with }}.
""")


def _analyze_labs_node(state: DiagnosisAgentState) -> dict:
    """Node 3 — Combine extracted values + RAG context to produce a structured diagnosis."""
    print("[DiagnosisAgent] Node 3: Analysing results against medical guidelines...")

    retry_count = state.get("retry_count", 0)
    feedback_str = ""
    if retry_count > 0:
        notes = state.get("evaluation_summary", {}).get("evaluation_notes", "")
        feedback_str = f"\nPrevious Evaluator Feedback (Address these issues):\n{notes}\n"

    try:
        response = llm.invoke(_ANALYZE_PROMPT.format(
            explanation=state["doctor_explanation"][:300],
            lab_inputs=json.dumps(state["extracted_lab_values"]),
            context=state["retrieved_lab_guidelines"][:4000],
            evaluator_feedback=feedback_str,
        ))
        result = _parse_json(_content_text(response.content))
    except Exception as e:
        print(f"[DiagnosisAgent] Node 3 LLM error: {e}")
        result = {}
    print("[DiagnosisAgent] Analysis complete.")
    return {"evaluation_results": result}


_EVALUATE_PROMPT = PromptTemplate.from_template("""
You are a Senior Clinical Auditor. Your job is to verify an AI-generated diagnosis by comparing it against the raw lab data and the medical reference guidelines.

Raw Lab Values (Extracted): {raw_labs}
Medical Guidelines (ChromaDB): {chroma_context}

AI-Generated Diagnosis to Evaluate:
Primary Hypothesis: {hypothesis}
Abnormal Findings Flagged by AI: {abnormals}

Compare the AI-Generated Diagnosis against the Raw Lab Values and Medical Guidelines.
Check for Hallucinations: Did the AI invent any abnormal values that weren't in the raw labs?
Check for Missed Data: Did the AI miss any abnormal values that the guidelines say are high/low?

Rate and evaluate the diagnosis. Return ONLY valid JSON:
{{
  "confidence_score": <integer 0-100 based on accuracy of the diagnosis>,
  "completeness_flag": "complete | partial | insufficient",
  "key_abnormalities": ["most critical finding 1", "most critical finding 2"],
  "evaluation_notes": "reviewer commentary on whether the diagnosis accurately reflects the raw labs and guidelines. Flag any hallucinations here.",
  "recommended_specialization": "single best specialist type (e.g. Endocrinologist)"
}}

Start your response with {{ and end with }}.
""")


def _evaluate_diagnosis_node(state: DiagnosisAgentState) -> dict:
    """
    Node 4 (Diagnosis Evaluator) — Quality-gate that reviews the raw diagnosis against ground truth data:
      - confidence_score       (0–100)
      - completeness_flag      (complete / partial / insufficient)
      - key_abnormalities      list of the most critical abnormal findings
      - evaluation_notes       any caveats, missing data flags, or hallucination warnings
      - recommended_specialization  map the hypothesis to a specialist
    """
    print("[DiagnosisAgent] Node 4 (Evaluator): Cross-checking diagnosis against raw labs and guidelines...")

    evaluation = state.get("evaluation_results", {})
    detailed   = evaluation.get("detailed_analysis", [])
    if not isinstance(detailed, list):
        detailed = []
    hypothesis = evaluation.get("primary_hypothesis", "")

    abnormals = [
        f"{r.get('test_name','?')}: {r.get('patient_value','?')} ({r.get('status','?')})"
        for r in detailed if r.get("status", "Normal") != "Normal"
    ]
    
    raw_labs = json.dumps(state.get("extracted_lab_values", {}))
    chroma_context = state.get("retrieved_lab_guidelines", "")

    try:
        response = llm.invoke(_EVALUATE_PROMPT.format(
            raw_labs=raw_labs,
            chroma_context=chroma_context[:3000], # Limit context to save tokens
            hypothesis=hypothesis[:500],
            abnormals="; ".join(abnormals[:6]) or "None flagged",
        ))
        summary = _parse_json(_content_text(response.content))
    except Exception as e:
        print(f"[DiagnosisAgent] Node 4 LLM error: {e}")
        summary = {}

    summary["recommended_specialization"] = map_specialization(hypothesis)

    print(f"[DiagnosisAgent] Confidence: {summary.get('confidence_score', '?')}% | "
          f"Completeness: {summary.get('completeness_flag', '?')}")
          
    current_retry = state.get("retry_count", 0)
    new_retry = current_retry
    if summary.get("confidence_score", 0) < 80:
        new_retry += 1
        
    return {"evaluation_summary": summary, "retry_count": new_retry}
