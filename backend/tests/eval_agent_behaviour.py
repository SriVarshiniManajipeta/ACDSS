"""
eval_agent_behaviour.py
=======================
Does the real model actually behave like an agent?

test_agent_flow.py scripts the tool calls, so it proves the wiring works but
says nothing about whether the model *chooses* to call the right tool. That is
the question behind "my chatbot isn't working as an agent", and it can only be
answered by calling the real LLM.

This is not a unit test. It costs Groq tokens and it is non-deterministic — a
case can fail once and pass on retry. Treat the score as a signal, not a gate.

    cd backend
    python tests/eval_agent_behaviour.py            # all cases
    python tests/eval_agent_behaviour.py --repeat 3 # measure flakiness

Needs GROQ_API_KEY in backend/.env.

Reading the results
-------------------
- Tools fired when none were expected  → the model is over-eager; tighten the
  tool descriptions, which are what it actually reads when deciding.
- No tools fired when some were expected → the model is under-calling. Either
  the tool description doesn't match how patients phrase things, or the model
  is too small. Try ACDSS_CHAT_MODEL=llama-3.3-70b-versatile.
- Right tools, robotic wording → the prompt's STYLE section is being ignored,
  or a tool return is dictating the reply.
"""

import argparse
import os
import sys
import types
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

REPORT = """\
COMPLETE BLOOD COUNT
Haemoglobin      9.1 g/dL     (13.0 - 17.0)
Ferritin         8 ng/mL      (30 - 400)
MCV              72 fL        (80 - 100)
"""

CASES = [
    {
        "name": "general medical question — should look it up",
        "input": "What does ferritin actually measure?",
        "expect_any": ["medical_lookup"],
        "forbid": ["analyze_lab_report", "build_treatment_plan",
                   "find_specialists", "book_appointment"],
        "setup": {},
    },
    {
        "name": "reference range question — should look it up",
        "input": "What's a normal haemoglobin level?",
        "expect_any": ["medical_lookup"],
        "forbid": ["analyze_lab_report", "book_appointment"],
        "setup": {},
    },
    {
        "name": "MY results, not general — record not guidelines",
        "input": "What did my ferritin come back as?",
        "expect_any": ["get_patient_record"],
        "forbid": ["analyze_lab_report"],
        "setup": {"diagnosis": True},
    },
    {
        "name": "small talk — no tool",
        "input": "Thanks, that was helpful!",
        "expect_any": [],
        "forbid": ["medical_lookup", "analyze_lab_report", "build_treatment_plan",
                   "find_specialists", "book_appointment"],
        "setup": {},
    },
    {
        "name": "symptom mention — should NOT summon a doctor",
        "input": "I've had a headache since yesterday.",
        "expect_any": [],
        "forbid": ["find_specialists", "book_appointment", "analyze_lab_report"],
        "setup": {},
    },
    {
        "name": "uploaded report — should diagnose",
        "input": None,                    
        "expect_any": ["analyze_lab_report"],
        "forbid": [],
        "setup": {"pending_report": REPORT, "report_note": "tired for weeks"},
    },
    {
        "name": "asks for treatment after diagnosis",
        "input": "Okay, what treatment do I need for this?",
        "expect_any": ["build_treatment_plan"],
        "forbid": [],
        "setup": {"diagnosis": True},
    },
    {
        "name": "asks for treatment with NO diagnosis — must not fabricate",
        "input": "Give me a treatment plan.",
        "expect_any": [],
        "forbid": [],
        "expect_reply_contains_any": ["report", "upload", "don't have", "no diagnosis",
                                      "haven't", "need"],
        "setup": {},
    },
    {
        "name": "explicitly asks for a doctor",
        "input": "Can you find me a specialist I can see for this?",
        "expect_any": ["find_specialists"],
        "forbid": ["book_appointment"],
        "setup": {"diagnosis": True},
    },
    {
        "name": "asks to recall results",
        "input": "Remind me what my report said?",
        "expect_any": ["get_patient_record"],
        "forbid": ["analyze_lab_report"],
        "setup": {"diagnosis": True},
    },
    {
        "name": "everything at once",
        "input": None,
        "compose": "diagnosis",
        "follow": "Diagnose this, tell me the treatment, and find me a doctor.",
        "expect_any": ["analyze_lab_report"],
        "forbid": [],
        "setup": {"pending_report": REPORT},
    },
]

SAMPLE_DIAGNOSIS = {
    "primary_hypothesis": "Iron-deficiency anaemia",
    "simple_explanation": "Your haemoglobin and iron stores are low.",
    "extracted_lab_values": {"Haemoglobin": "9.1", "Ferritin": "8"},
    "detailed_analysis": [],
    "recommended_specialization": "General Physician",
    "confidence_score": 88,
    "key_abnormalities": ["Low haemoglobin", "Low ferritin"],
}


def _stub_pipelines(stub_retrieval: bool = False) -> None:
    """Stub the Chroma/Gemini pipelines. The agent LLM stays real.

    `medical_lookup` hits the real vector store by default — it's cheap and
    it's the whole point of the retrieval cases. Pass --no-rag to stub it too,
    e.g. when GOOGLE_API_KEY isn't set for the embeddings.
    """
    import app  # noqa: F401

    if stub_retrieval:
        import app.tools.knowledge as kb

        class _Store:
            def similarity_search_with_relevance_scores(self, query, k=3):
                class D:
                    page_content = ("Ferritin is the storage form of iron; "
                                    "reference range 30-400 ng/mL.")
                return [(D(), 0.9)]

        kb._stores = [("Lab reference guide", _Store())]

    def fake_diagnosis(raw_text, doctor_notes=""):
        return dict(SAMPLE_DIAGNOSIS)

    def fake_treatment(diagnosis, symptoms=""):
        return {
            "disease_explanation": "Anaemia from low iron.",
            "treatment_plan": [{"medication_or_action": "Ferrous sulfate",
                                "dosage_or_detail": "325 mg daily",
                                "rationale": "replaces iron"}],
            "prognosis": "Good.", "follow_up": "Recheck in 8 weeks.",
            "severity_level": "moderate", "follow_up_question": "Any dizziness?",
        }

    for name, attr, fn in [
        ("app.Dual_Agent.Diagnosis_Agent.agent", "run_diagnosis_agent", fake_diagnosis),
        ("app.Dual_Agent.Treatment_Agent.agent", "run_treatment_agent", fake_treatment),
    ]:
        module = types.ModuleType(name)
        setattr(module, attr, fn)
        sys.modules[name] = module


def run_case(case: dict) -> dict:
    from app.agent import action
    from app.messages import report_message
    from app.session import store

    session = store.create()
    session.patient = {"name": "Priya Sharma", "age": 34, "gender": "Female"}

    setup = case.get("setup", {})
    if setup.get("pending_report"):
        session.pending_report = setup["pending_report"]
        session.report_note = setup.get("report_note", "")
    if setup.get("diagnosis"):
        session.diagnosis = dict(SAMPLE_DIAGNOSIS)
        session.remember("user", "here is my lab report")
        session.remember("assistant", "You have iron-deficiency anaemia.")

    if case["input"] is None:
        text = report_message(setup["pending_report"], case.get("follow", ""))
    else:
        text = case["input"]

    turn = action(text, session_id=session.id)

    fired = set(turn.tools_used)
    expect_any = set(case.get("expect_any", []))
    forbid = set(case.get("forbid", []))

    problems = []
    if expect_any and not (fired & expect_any):
        problems.append(f"expected one of {sorted(expect_any)}, got {sorted(fired) or 'none'}")
    if fired & forbid:
        problems.append(f"called forbidden {sorted(fired & forbid)}")
    if not expect_any and not forbid and not fired:
        pass
    wanted = case.get("expect_reply_contains_any")
    if wanted and not any(w.lower() in turn.reply.lower() for w in wanted):
        problems.append(f"reply mentioned none of {wanted}")

    return {
        "name": case["name"],
        "ok": not problems,
        "problems": problems,
        "tools": sorted(fired),
        "reply": turn.reply,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=1,
                        help="run each case N times to measure flakiness")
    parser.add_argument("--quiet", action="store_true", help="hide replies")
    parser.add_argument("--no-rag", action="store_true",
                        help="stub the vector store (no GOOGLE_API_KEY needed)")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env")

    if not os.getenv("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set. Put it in backend/.env and rerun.")
        return 2

    _stub_pipelines(stub_retrieval=args.no_rag)

    from app.llm_model import CHAT_MODEL
    print(f"Model: {CHAT_MODEL}   cases: {len(CASES)}   repeats: {args.repeat}"
          f"   retrieval: {'stubbed' if args.no_rag else 'live Chroma'}\n")

    passes = defaultdict(int)
    total = 0
    failures = []

    for run in range(args.repeat):
        for case in CASES:
            try:
                result = run_case(case)
            except Exception as exc:                    # noqa: BLE001
                result = {"name": case["name"], "ok": False,
                          "problems": [f"{type(exc).__name__}: {exc}"],
                          "tools": [], "reply": ""}
            total += 1
            passes[case["name"]] += int(result["ok"])

            mark = "PASS" if result["ok"] else "FAIL"
            print(f"[{mark}] {result['name']}")
            print(f"       tools: {result['tools'] or 'none'}")
            if not args.quiet and result["reply"]:
                snippet = result["reply"].replace("\n", " ")[:150]
                print(f"       reply: {snippet}")
            for problem in result["problems"]:
                print(f"       ↳ {problem}")
                failures.append((result["name"], problem))
            print()

    print("─" * 68)
    scored = sum(passes.values())
    print(f"Agentic behaviour: {scored}/{total} "
          f"({100 * scored // total if total else 0}%)")
    if args.repeat > 1:
        flaky = [n for n, p in passes.items() if 0 < p < args.repeat]
        if flaky:
            print(f"Flaky (passed some runs, failed others): {', '.join(flaky)}")
    if failures:
        print("\nSee the module docstring for how to read these failures.")
    return 0 if scored == total else 1


if __name__ == "__main__":
    sys.exit(main())
