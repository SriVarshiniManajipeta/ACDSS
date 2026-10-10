

import os
import re

from langchain_core.tools import tool

PASSAGES_PER_STORE = int(os.getenv("ACDSS_RAG_K", "3"))
PASSAGE_CHARS = 600
TOTAL_CHARS = 2600

MIN_RELEVANCE = float(os.getenv("ACDSS_RAG_MIN_RELEVANCE", "0.15"))

_stores = None


def _load_stores() -> list:
    """Import and cache the two vector stores. Never raises."""
    global _stores
    if _stores is not None:
        return _stores

    _stores = []
    sources = [
        ("Lab reference guide", "app.Dual_Agent.Diagnosis_Agent.llm_models"),
        ("Treatment guidelines", "app.Dual_Agent.Treatment_Agent.llm_models"),
    ]
    for label, module_path in sources:
        try:
            module = __import__(module_path, fromlist=["vectorstore"])
            _stores.append((label, module.vectorstore))
        except Exception as exc:
            print(f"[ACDSS] knowledge base '{label}' unavailable: "
                  f"{type(exc).__name__}: {exc}")
    return _stores


def _search(store, query: str) -> list[tuple[float, str]]:
    """Return [(relevance, passage)], best first. Never raises."""
    try:
        scored = store.similarity_search_with_relevance_scores(
            query, k=PASSAGES_PER_STORE
        )
        return [
            (score, doc.page_content)
            for doc, score in scored
            if score is None or score >= MIN_RELEVANCE
        ]
    except Exception:
        try:
            docs = store.similarity_search(query, k=PASSAGES_PER_STORE)
            return [(1.0, doc.page_content) for doc in docs]
        except Exception as exc:
            print(f"[ACDSS] retrieval failed: {type(exc).__name__}: {exc}")
            return []


def _tidy(text: str) -> str:
    """PDF extraction leaves ragged newlines and runs of spaces."""
    return re.sub(r"\s+", " ", (text or "")).strip()


@tool
def medical_lookup(query: str) -> str:
    """Look up a medical question in the clinical guideline knowledge base.

    Takes a plain question in ordinary English — "what does ferritin measure",
    "normal range for creatinine", "how is anaemia usually managed" — and
    returns the passages from the reference guides that address it.

    Use this for general medical questions, for what a test or term means, and
    for reference ranges. It searches the guidelines, not this patient's file;
    to recall what was found for *this* patient, use get_patient_record instead.

    Returns the passages found, or says plainly that nothing matched.
    """
    question = (query or "").strip()
    if not question:
        return "No question was supplied to look up."

    stores = _load_stores()
    if not stores:
        return ("The clinical knowledge base is not available, so this could not "
                "be looked up. Answer from general knowledge and say that you "
                "could not check the guidelines.")

    hits: list[tuple[float, str, str]] = []
    for label, store in stores:
        for score, passage in _search(store, question):
            hits.append((score, label, _tidy(passage)[:PASSAGE_CHARS]))

    hits.sort(key=lambda h: h[0], reverse=True)
    seen: set[str] = set()
    lines: list[str] = []
    used = 0

    for _score, label, passage in hits:
        fingerprint = passage[:120].lower()
        if not passage or fingerprint in seen:
            continue
        seen.add(fingerprint)
        entry = f"[{label}] {passage}"
        if used + len(entry) > TOTAL_CHARS:
            break
        lines.append(entry)
        used += len(entry)

    if not lines:
        return (f"Nothing in the clinical guidelines matches '{question}'. "
                "Answer from general knowledge and be clear that this specific "
                "point isn't covered by the reference material.")

    return (
        f"Guideline passages relevant to '{question}':\n\n"
        + "\n\n".join(lines)
    )
