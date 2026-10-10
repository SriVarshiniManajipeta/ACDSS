

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

try:                                                # langchain >= 1.0
    from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
except ImportError:                                 # langchain 0.3.x
    try:
        from langchain.agents import AgentExecutor, create_tool_calling_agent
    except ImportError as exc:                      # neither home has it
        raise ImportError(
            "AgentExecutor / create_tool_calling_agent were not found.\n"
            "LangChain 1.0 moved them out of `langchain.agents` into the "
            "`langchain-classic` package. Install it:\n\n"
            "    pip install langchain-classic\n\n"
            "(or pin langchain<1.0). If you're seeing 422s from /chat, this is "
            "why: the module failed to import and uvicorn kept serving the old "
            "code."
        ) from exc

from app.llm_model import llm, llm_candidates
from app.prompt import SYSTEM_PROMPT
from app.session import Session, collect_events, use_session

from app.tools.knowledge import medical_lookup
from app.tools.lab_report import analyze_lab_report, get_patient_record
from app.tools.treatment import build_treatment_plan
from app.tools.doctors import find_specialists, get_doctor_availability
from app.tools.booking import book_appointment


agent_tools = [
    medical_lookup,
    analyze_lab_report,
    get_patient_record,
    build_treatment_plan,
    find_specialists,
    get_doctor_availability,
    book_appointment,
]


prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("system", "{patient_record}"),    
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])


# A fallback-wrapped Runnable doesn't expose bind_tools(), which
# create_tool_calling_agent() requires — so each candidate LLM is bound to
# the tools and built into its own complete agent chain first, and THOSE
# chains (not the raw LLMs) are what carries the fallback. Every branch
# shares the same prompt and output parser, so falling back mid-chain still
# produces a compatible AgentAction/AgentFinish for AgentExecutor.
_candidate_agents = [
    create_tool_calling_agent(llm=candidate, tools=agent_tools, prompt=prompt)
    for candidate in llm_candidates
]
agent = _candidate_agents[0].with_fallbacks(_candidate_agents[1:])

agent_executor = AgentExecutor(
    agent=agent,
    tools=agent_tools,
    verbose=os.getenv("ACDSS_DEBUG") == "1",
    handle_parsing_errors=True,
    max_iterations=8,
    # A single Gemini call can now legitimately back off for up to ~60s
    # (max_retries=6 in llm_model.py / Dual_Agent's llm_models.py), and a
    # tool like analyze_lab_report makes several such calls in sequence
    # (this agent's own turn, then the diagnosis graph's extract/analyse/
    # evaluate nodes). 90s was cutting that off before the retries had a
    # real chance to land.
    max_execution_time=240,
    return_intermediate_steps=True,
)

STOP_SENTINELS = (
    "Agent stopped due to max iterations.",
    "Agent stopped due to iteration limit or time limit.",
)


@dataclass
class AgentTurn:
    """What one turn of conversation produced."""

    session_id: str
    reply: str
    events: list[dict] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)


NO_RECORD = "No clinical record for this patient yet."


def patient_record(session: Session) -> str:
    """Ground the model in this patient's real record before it answers.

    Without this the model has to trust its own summary of earlier turns, which
    is how a diagnosis quietly mutates over a long conversation.
    """
    facts: list[str] = []

    if session.patient_name():
        facts.append(f"- Name: {session.patient_name()}")
    for key in ("age", "gender"):
        if session.patient.get(key):
            facts.append(f"- {key.capitalize()}: {session.patient[key]}")

    if session.pending_report:
        facts.append("- A lab report has been uploaded and is not yet analysed.")

    diagnosis = session.diagnosis or {}
    if diagnosis.get("primary_hypothesis"):
        facts.append(f"- Diagnosis on record: {diagnosis['primary_hypothesis']}")
    if diagnosis.get("key_abnormalities"):
        facts.append(f"- Key findings: {', '.join(diagnosis['key_abnormalities'])}")
    if diagnosis.get("recommended_specialization"):
        facts.append(f"- Suggested specialist: {diagnosis['recommended_specialization']}")

    treatment = session.treatment or {}
    if treatment.get("disease_explanation"):
        facts.append(f"- Treatment plan on record: {treatment['disease_explanation']}")
    if treatment.get("severity_level"):
        facts.append(f"- Severity: {treatment['severity_level']}")

    if session.booking:
        facts.append(
            f"- Appointment booked: {session.booking['patient_name']} with "
            f"{session.booking['doctor_name']} at {session.booking['slot']}"
        )

    if not facts:
        return NO_RECORD
    return (
        "PATIENT RECORD — ground truth for this conversation. Answer from these "
        "facts; never replace them with different ones:\n" + "\n".join(facts)
    )


def _stopped_reply(events: list[dict]) -> str:
    """What to say when the agent ran out of steps.

    If it produced a card before losing the thread, point at that — the work is
    on screen and it would be strange to ignore it. Otherwise, say plainly that
    it didn't get there rather than pretending it did.
    """
    kinds = {event["kind"] for event in events}
    if "diagnosis" in kinds or "treatment" in kinds:
        return ("I've put what I found on screen above. I lost the thread before "
                "I could summarise it properly — ask me about any part of it and "
                "I'll explain.")
    return ("Sorry — I went round in circles on that one and didn't get to an "
            "answer. Could you try asking it a different way?")


def _reply_text(output) -> str:
    """Flatten AgentExecutor's `output` into plain text.

    Usually a string, but some providers return message content as a list of
    blocks (e.g. `[{"type": "text", "text": "..."}]`) instead of a flat string
    — seen from Groq under certain response shapes. A bare `.strip()` on that
    raised `AttributeError: 'list' object has no attribute 'strip'` and the
    whole turn was lost even though every tool call had already succeeded.
    """
    if isinstance(output, str):
        return output.strip()
    if isinstance(output, list):
        parts = [
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in output
        ]
        return " ".join(p for p in parts if p).strip()
    return str(output or "").strip()


def chat_history(session: Session) -> list:
    """The stored transcript as LangChain messages."""
    return [
        HumanMessage(content=turn["content"]) if turn["role"] == "user"
        else AIMessage(content=turn["content"])
        for turn in session.transcript
    ]


def action(
    text: str,
    session_id: Optional[str] = None,
    patient: Optional[dict] = None,
) -> AgentTurn:
    """Run one turn of conversation.

    The only entry point into the agent. Give it one string — whatever the
    patient said, or what app/messages.py composed on their behalf — and get
    back what to say and what to draw.
    """
    with use_session(session_id) as session:
        if patient:
            session.patient.update({k: v for k, v in patient.items() if v})

        history = chat_history(session)

        try:
            response = agent_executor.invoke({
                "input": text,
                "chat_history": history,
                "patient_record": patient_record(session),
            })
            reply = _reply_text(response.get("output"))
            steps = response.get("intermediate_steps") or []
            tools_used = [
                getattr(step[0], "tool", "?") for step in steps if step
            ]
            events = collect_events()

            if reply in STOP_SENTINELS:
                print(f"[ACDSS] agent hit its limit. tools={tools_used}")
                reply = _stopped_reply(events)
        except Exception as exc:
            print(f"[ACDSS] agent error: {type(exc).__name__}: {exc}")
            failure_events = collect_events()
            return AgentTurn(
                session_id=session.id,
                reply="Sorry — I hit a problem working through that. "
                      "Could you say it again?",
                events=failure_events,
                tools_used=[],
            )

        if not reply:
            reply = "I'm here — could you tell me a bit more about what you need?"
        session.remember("user", text)
        session.remember("assistant", reply)

        return AgentTurn(
            session_id=session.id,
            reply=reply,
            events=events,
            tools_used=tools_used,
        )
