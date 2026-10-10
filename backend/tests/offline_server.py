"""
offline_server.py
=================
Run the whole ACDSS backend with no API keys and no network.

Everything is real — routing, the session store, the tool loop, the event
plumbing, the DB writes — except the three things that need outbound calls:

    ChatGroq        → a rule-based stand-in that picks tools by keyword
    Dual_Agent      → canned diagnosis / treatment results
    Tesseract OCR   → canned report text

Useful for working on the frontend without burning tokens, for demoing the flow
on a machine with no keys, and for reproducing transport bugs in isolation.

    cd backend && python tests/offline_server.py           # port 8000
    cd backend && python tests/offline_server.py --port 8010

⚠️  The tool choices here are made by keyword rules, NOT by a language model.
    This proves the plumbing works. It proves nothing about whether the real
    model reaches for the right tool — that's tests/eval_agent_behaviour.py,
    which needs a real GROQ_API_KEY.
"""

import argparse
import os
import sys
import tempfile
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("GROQ_API_KEY", "offline")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite:///{(Path(tempfile.gettempdir()) / 'acdss_offline.db').as_posix()}",
)

BANNER = "\033[33m[offline]\033[0m"

SAMPLE_REPORT = """\
COMPLETE BLOOD COUNT
Haemoglobin      9.1 g/dL      (13.0 - 17.0)
Ferritin         8 ng/mL       (30 - 400)
MCV              72 fL         (80 - 100)
"""

SAMPLE_DIAGNOSIS = {
    "primary_hypothesis": "Iron-deficiency anaemia",
    "simple_explanation": "Your haemoglobin and iron stores are both low, which "
                          "usually means your body doesn't have enough iron to "
                          "make healthy red blood cells.",
    "detailed_analysis": [
        {"test_name": "Haemoglobin", "patient_value": "9.1 g/dL",
         "reference_range": "13.0 - 17.0", "status": "Low",
         "potential_causes": ["iron deficiency", "chronic blood loss"]},
        {"test_name": "Ferritin", "patient_value": "8 ng/mL",
         "reference_range": "30 - 400", "status": "Low",
         "potential_causes": ["depleted iron stores"]},
        {"test_name": "MCV", "patient_value": "72 fL",
         "reference_range": "80 - 100", "status": "Low",
         "potential_causes": ["microcytic anaemia"]},
    ],
    "extracted_lab_values": {"Haemoglobin": "9.1", "Ferritin": "8", "MCV": "72"},
    "recommended_specialization": "General Physician",
    "confidence_score": 88,
    "key_abnormalities": ["Low haemoglobin", "Low ferritin", "Low MCV"],
    "evaluation_notes": "Classic microcytic picture; confirm with iron studies.",
    "completeness_flag": "complete",
}

SAMPLE_TREATMENT = {
    "disease_explanation": "Iron-deficiency anaemia — your iron stores are empty, "
                           "so replacing them is the main job.",
    "treatment_plan": [
        {"medication_or_action": "Ferrous sulfate 325 mg",
         "dosage_or_detail": "Once daily with food and vitamin C",
         "rationale": "Replaces depleted iron stores"},
        {"medication_or_action": "Dietary iron",
         "dosage_or_detail": "Red meat, lentils, spinach, fortified cereal",
         "rationale": "Supports recovery alongside supplementation"},
        {"medication_or_action": "Repeat full blood count",
         "dosage_or_detail": "In 8 weeks",
         "rationale": "Confirms the haemoglobin is responding"},
    ],
    "prognosis": "Good — most people feel noticeably better within a few weeks.",
    "follow_up": "Recheck haemoglobin and ferritin in 8 weeks.",
    "severity_level": "moderate",
    "follow_up_question": "Have you noticed heavy periods or any blood in your stool?",
}

GUIDELINE_PASSAGES = [
    (0.93, "Ferritin is the storage form of iron and the earliest marker of iron "
           "depletion. Reference range 30-400 ng/mL in adult men and 13-150 ng/mL "
           "in adult women."),
    (0.88, "Haemoglobin below 13.0 g/dL in men or 12.0 g/dL in women defines "
           "anaemia. A low MCV alongside it points to a microcytic cause, most "
           "commonly iron deficiency."),
    (0.81, "Confirmed iron deficiency is treated with oral ferrous sulfate 325 mg "
           "daily, taken with vitamin C to aid absorption."),
]


# ── Stand-in chat model ──────────────────────────────────────────────────────

def _install_fake_llm() -> None:
    """A ChatGroq replacement that routes by keyword and narrates the result."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage

    class OfflineChatModel(FakeMessagesListChatModel):
        """Picks a tool by keyword, then writes a reply from the tool output."""

        def __init__(self, **kwargs):
            super().__init__(responses=[])

        def bind_tools(self, tools, **kwargs):
            return self

        def _decide(self, text: str, already_ran: set) -> AIMessage:
            low = text.lower()

            def call(name, args):
                return AIMessage(content="", tool_calls=[
                    {"name": name, "args": args, "id": f"call_{name}"}
                ])

            # report_message() no longer wraps OCR text in [LAB REPORT] tags — it
            # just becomes the patient's message — so detect an uploaded report
            # by its content instead of a marker that doesn't exist any more.
            if "complete blood count" in low and "analyze_lab_report" not in already_ran:
                return call("analyze_lab_report",
                            {"patient_context": "uploaded via offline server"})

            if "treatment plan" in low and "build_treatment_plan" not in already_ran:
                return call("build_treatment_plan", {"symptoms": "tired, short of breath"})

            if any(w in low for w in ("doctor", "specialist", "appointment", "book")) \
                    and "find_specialists" not in already_ran:
                return call("find_specialists", {})

            if any(w in low for w in ("my ", "i have", "my report", "my results")) \
                    and "get_patient_record" not in already_ran \
                    and any(w in low for w in ("result", "report", "level", "come back")):
                return call("get_patient_record", {"query": text[:80]})

            if "?" in text and "medical_lookup" not in already_ran \
                    and any(w in low for w in (
                        "what", "why", "how", "mean", "normal", "range", "ferritin",
                        "haemoglobin", "hemoglobin", "anaemia", "anemia", "iron", "mcv")):
                return call("medical_lookup", {"query": text.strip()[:120]})

            return None

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            from langchain_core.messages import AIMessage as AIMsg
            from langchain_core.messages import ToolMessage
            from langchain_core.outputs import ChatGeneration, ChatResult

            human = next((m for m in reversed(messages)
                          if m.__class__.__name__ == "HumanMessage"), None)
            text = (human.content if human else "") or ""

            already = {
                call["name"]
                for m in messages if isinstance(m, AIMsg)
                for call in (getattr(m, "tool_calls", None) or [])
            }
            tool_output = [m.content for m in messages if isinstance(m, ToolMessage)]

            decision = self._decide(text, already)
            if decision is None:
                if tool_output:
                    summary = " ".join(tool_output)[:700]
                    reply = ("[offline stand-in — the real model would phrase this]\n"
                             + summary)
                else:
                    reply = ("[offline stand-in] I'm here and the plumbing works. "
                             "Ask me a medical question, attach a report, or ask "
                             "for a specialist.")
                decision = AIMessage(content=reply)

            return ChatResult(generations=[ChatGeneration(message=decision)])

        @property
        def _llm_type(self):
            return "offline-stand-in"

    module = types.ModuleType("langchain_groq")
    module.ChatGroq = OfflineChatModel
    sys.modules["langchain_groq"] = module


def _install_fake_pipelines() -> None:
    """Canned Dual_Agent results — the real ones need Chroma + Gemini."""
    import app  # noqa: F401

    def diagnosis(raw_text, doctor_notes=""):
        print(f"{BANNER} Diagnosis_Agent (stub) — {len(raw_text)} chars, "
              f"context={doctor_notes[:60]!r}")
        return dict(SAMPLE_DIAGNOSIS)

    def treatment(diagnosis_result, patient_symptoms=""):
        print(f"{BANNER} Treatment_Agent (stub) — symptoms={patient_symptoms[:60]!r}")
        return dict(SAMPLE_TREATMENT)

    for name, attr, fn in [
        ("app.Dual_Agent.Diagnosis_Agent.agent", "run_diagnosis_agent", diagnosis),
        ("app.Dual_Agent.Treatment_Agent.agent", "run_treatment_agent", treatment),
    ]:
        module = types.ModuleType(name)
        setattr(module, attr, fn)
        sys.modules[name] = module


def _install_fake_ocr() -> None:
    module = types.ModuleType("app.ocr")

    def extract(image_bytes: bytes) -> str:
        print(f"{BANNER} OCR (stub) — {len(image_bytes)} bytes in")
        return SAMPLE_REPORT

    module.extract_text_from_image = extract
    sys.modules["app.ocr"] = module


def _install_fake_retriever() -> None:
    """Canned guideline passages — real retrieval needs Gemini embeddings."""
    import app.tools.knowledge as kb

    class Doc:
        def __init__(self, text):
            self.page_content = text

    class Store:
        def __init__(self, passages):
            self.passages = passages

        def similarity_search_with_relevance_scores(self, query, k=3):
            print(f"{BANNER} Chroma (stub) — query={query[:60]!r}")
            return [(Doc(t), s) for s, t in self.passages][:k]

    kb._stores = [
        ("Lab reference guide", Store(GUIDELINE_PASSAGES[:2])),
        ("Treatment guidelines", Store(GUIDELINE_PASSAGES[2:])),
    ]


def build_app():
    _install_fake_llm()
    _install_fake_pipelines()
    _install_fake_ocr()

    from app.main import app

    _install_fake_retriever()          # after app import, so app.tools is loaded
    return app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    import uvicorn

    print("=" * 66)
    print("  ACDSS backend — OFFLINE MODE")
    print("  LLM, RAG and OCR are stand-ins. Tool choices are keyword rules,")
    print("  not model decisions. Good for UI work; proves nothing about")
    print("  agent judgment — use tests/eval_agent_behaviour.py for that.")
    print("=" * 66)

    uvicorn.run(build_app(), host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
