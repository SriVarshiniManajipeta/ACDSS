# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

ACDSS — an autonomous clinical decision support system. A patient chats with an
AI assistant, uploads a photo of a lab report, gets a diagnosis and a treatment
plan, and books a specialist.

- `backend/` — FastAPI + LangChain agent + two LangGraph clinical pipelines + Chroma RAG
- `frontend/` — React (Vite), a single chat surface
- `report/` — LaTeX academic report (not code; leave alone unless asked)

---

## 🚫 Do not modify `backend/app/Dual_Agent/`

**This is the hard boundary in this project.** `Dual_Agent/` holds the research
contribution: the Diagnosis and Treatment LangGraphs, their nodes, the evaluator
nodes, the meta-evaluator, and the Chroma knowledge bases. They are finished,
they are what the academic report describes, and they are **not** to be
refactored, "improved", reformatted, or re-architected.

Treat these as a fixed external API:

```python
run_diagnosis_agent(raw_ocr_text: str, doctor_notes: str = "") -> dict
run_treatment_agent(diagnosis_result: dict, patient_symptoms: str = "") -> dict
run_dual_agent_pipeline(raw_ocr_text, doctor_notes, patient_symptoms) -> dict
```

Also leave alone: `app/ocr.py`, `app/models.py`, `app/database.py`, `app/seed.py`,
`*_db/chroma_db/`.

All work happens in the **outer conversational agent** — the layer that decides
*when* to call those graphs.

---

## Architecture

```
tools  →  prompt  →  agent  →  agent_executor  →  action()
                                                     ↑
                                              main.py (transport)
```

Everything above `action()` is a capability. Everything below is transport.
`main.py` does not know what a diagnosis is; the tools do not know what HTTP is.

| File | Role |
|---|---|
| `app/agent.py` | Flat tool list, prompt, `AgentExecutor`, and `action()` — the only entry point |
| `app/prompt.py` | System prompt. Describes judgment, never triggers |
| `app/messages.py` | Turns what the patient did into the one string `action()` receives |
| `app/session.py` | Per-conversation state, contextvar binding, LRU store |
| `app/llm_model.py` | Shared `ChatGroq` (`ACDSS_CHAT_MODEL`, default `llama-3.3-70b-versatile`) |
| `app/tools/` | One module per capability |
| `app/main.py` | FastAPI. Four routes, no business logic |

### Tools

Module-level `@tool` functions. They read/write conversation state via
`app.session.current_session()`, so they are importable and unit-testable
without an agent or a request.

| Tool | Signature |
|---|---|
| `medical_lookup` | `(query: str)` |
| `analyze_lab_report` | `(patient_context: str = "")` |
| `get_patient_record` | `(query: str = "")` |
| `build_treatment_plan` | `(symptoms: str = "")` |
| `find_specialists` | `(specialization: str = "", location: str = "")` |
| `get_doctor_availability` | `(doctor_name: str)` |
| `book_appointment` | `(doctor_name: str, slot: str, patient_name: str = "")` |

### Routes

`GET /` · `POST /chat` · `GET /doctors` · `POST /appointments`

`/chat` accepts **both** `multipart/form-data` and `application/json`.

---

## The one rule: never hardcode the flow

This codebase was refactored specifically to remove hardcoded conversation
flow. It had been hardcoded in three places at once — a `phase` state machine in
React, separate `/diagnose` and `/treatment` routes, and a system prompt written
as English if/else. Do not reintroduce any of it.

**Never write:**

- Keyword/intent matching — `if 'treatment' in message.lower()`, `treatmentKeywords = [...]`
- Prompt rules of the form *"call X ONLY when the message contains…"* / *"NEVER call Y unless…"*
- Instructions wrapped around user input — the OCR text **is** the patient's
  message; do not append "please run the diagnosis on this"
- Stage directions in tool return values — *"keep your reply short and warm"*,
  *"explain this to the patient"*. Tools return **facts**; the prompt owns voice.
  (There is a test that fails if these reappear.)
- Phase/step state in the frontend that decides what happens next

**Instead:**

- The agent decides. If it needs to know something, put it in a **tool
  description** — that is what the model actually reads when choosing.
- Hard preconditions go in the **tool**, enforced against the database, and are
  returned as a plain fact the agent can act on. `build_treatment_plan` says
  "no diagnosis exists"; `book_appointment` says "'03:00' is not one of Dr Rao's
  open slots". Never a value the model can invent.

---

## Invariants — each of these was a real bug

Do not undo these without reading `FIXES.md` first.

1. **`analyze_lab_report` takes no report text.** It reads the authoritative OCR
   copy from `session.pending_report`. If the model could pass text in, it could
   invent a lab report and diagnose a condition the patient doesn't have.

2. **Session ids are server-issued only.** `store.get_or_create()` never adopts a
   client-supplied id — an unknown id yields a *new* session. Honouring client ids
   let a forged id read back another patient's diagnosis, name and phone.

3. **Never store a composed prompt in the transcript.** `action(text, ...,
   remember_as=...)` exists so the Treatment button remembers
   `"[Pressed Get Treatment Plan]"`, not the transcript it just embedded.
   Remembering the composed string made each press embed the previous one —
   683 → 23,034 chars over six presses.

4. **Patient dedup never matches on name alone.** Reuse within a session
   (`session.patient_id`), or on a real identifier (phone). Name-only matching
   merged a 34F and a 71M who shared a name and filed one's appointment under the
   other's record.

5. **`AgentExecutor` returns `"Agent stopped due to max iterations."` as `output`
   and does not raise.** `STOP_SENTINELS` catches it. Without that, a patient
   reads that string.

6. **UI events are buffered per turn**, in a contextvar — not on the Session.
   Otherwise two concurrent requests drain each other's cards.

7. **`verbose` is off unless `ACDSS_DEBUG=1`.** `AgentExecutor` verbose output
   puts diagnoses and lab values on stdout, i.e. PHI into your logs.

---

## Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload            # needs GROQ_API_KEY + GOOGLE_API_KEY in .env
ACDSS_DEBUG=1 uvicorn app.main:app --reload   # show the agent's reasoning

# Frontend
cd frontend && npm install && npm run dev

# Tests — no API keys needed, ~1s
cd backend && python -m pytest tests/ -q          # 30 tests

# Whole backend with NO keys and no network (stubbed LLM/RAG/OCR)
cd backend && python tests/offline_server.py

# Does the real model actually reach for the right tools? Costs Groq tokens.
cd backend && python tests/eval_agent_behaviour.py --repeat 3
cd backend && python tests/eval_agent_behaviour.py --no-rag   # if no GOOGLE_API_KEY
```

Check which code is running: `curl http://localhost:8000/` → `{"api": "agent-v2"}`.

---

## Gotchas

- **`langchain-classic` is required.** LangChain 1.0 removed `AgentExecutor` and
  `create_tool_calling_agent` from `langchain.agents`. `agent.py` tries the new
  home then falls back. If it's missing, the module fails to import, `uvicorn
  --reload` keeps serving the *old* worker, and `/chat` returns a bare **422**
  with nothing in the logs.
- **Not `create_react_agent`.** ReAct's `Action Input:` is a single string;
  `book_appointment` takes three arguments. Use `create_tool_calling_agent`.
- **`action()` blocks on the LLM.** `/chat` is `async`, so it must stay wrapped in
  `run_in_threadpool`.
- **Tools must run inside `use_session(...)`.** `current_session()` raises
  otherwise — that's a wiring bug, not a runtime condition.
- **Heavy imports stay deferred.** `analyze_lab_report` / `build_treatment_plan`
  import `Dual_Agent` *inside* the function so a plain "hello" turn doesn't load
  LangGraph, Chroma and the embedding model.
- **Tests write to `tempfile.gettempdir()/acdss_test.db`**, which is not always
  `/tmp`. Delete that file if patient rows accumulate between runs.
- **Prompt injection is not solved.** OCR text reaches the agent verbatim, so
  text printed on an uploaded image is indistinguishable from patient speech.
  The defence is that irreversible tools validate against the DB — keep it that
  way. Never let a tool take an action based purely on model-supplied strings.

---

## Conventions

- Comments explain **why**, never what. If a line looks odd, say what it prevents.
- Tests are named for the behaviour they protect, and regression tests state the
  bug in the docstring.
- New tool → add to `app/tools/`, export in `app/tools/__init__.py`, add to
  `agent_tools` in `agent.py`, mention it in `prompt.py`'s capability list, and
  add an eval case in `tests/eval_agent_behaviour.py`.
- New card type → tool calls `emit(kind, data)`; add a branch in `App.jsx`'s
  message renderer. The flow doesn't change.
- Don't add a route to express a step in the consultation. There is one
  conversational endpoint on purpose.

---

## Further reading

- [`CHANGELOG.md`](CHANGELOG.md) — what the refactor changed and why
- [`FIXES.md`](FIXES.md) — the code-review findings, with evidence and patches
