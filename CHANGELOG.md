# Changelog

## Agentic refactor — August 2026

Rebuilt the conversational layer so the **agent decides the order of the
consultation**, instead of that order being hardcoded across three files.

**Scope: the outer chatbot agent only.** Nothing inside `Dual_Agent/` changed —
the Diagnosis and Treatment LangGraphs, their nodes, the evaluator nodes, the
meta-evaluator, `ocr.py`, and both Chroma knowledge bases are byte-for-byte
untouched. Those graphs are still invoked exactly as before
(`run_diagnosis_agent(raw_text, doctor_notes)`,
`run_treatment_agent(diagnosis, symptoms)`); what changed is **who decides when
to call them** — previously the React `phase` machine and the URL routing, now
the agent. A second round of fixes from the code review follows in
[`FIXES.md`](FIXES.md).

---

## 1. Why

The flow was hardcoded in three places at once, none of them the agent:

| Where | What it hardcoded |
|---|---|
| `App.jsx` | A 9-state `phase` machine plus `treatmentKeywords = ['treat','medicine','yes',…]` doing literal substring matching to decide which endpoint to call |
| `main.py` | Separate `/diagnose` and `/treatment` routes — the consultation order lived in the URL space, so the frontend had to know diagnosis precedes treatment and drive the sequence |
| `agents.py` | A ~70-line system prompt written as English if/else (`"call X ONLY when the message contains…"`, `"NEVER call Y unless…"`) — the flow, in prose instead of Python |

The agent had seven tools but no real authority: React had already decided what
would happen before the model was consulted.

---

## 2. Architecture now

```
tools  →  prompt  →  agent  →  agent_executor  →  action()
```

Everything above that line is a capability, everything below is transport.
`main.py` doesn't know what a diagnosis is; the tools don't know what HTTP is.

### New files

| File | Lines | Purpose |
|---|---|---|
| `app/agent.py` | 219 | Flat tool list, agent, executor, single `action()` entry point |
| `app/prompt.py` | 69 | System prompt — describes judgment, not triggers |
| `app/messages.py` | 89 | Turns what the patient did into the one string `action()` receives |
| `app/session.py` | 149 | Per-conversation state; contextvar binding; LRU store |
| `app/llm_model.py` | 17 | Shared `ChatGroq` for the conversational agent |
| `app/tools/` | 550 | One module per capability (7 tools) |
| `tests/test_agent_flow.py` | 842 | 30 tests |
| `tests/eval_agent_behaviour.py` | 298 | Live model-behaviour eval (needs a real key) |
| `tests/offline_server.py` | 279 | Runs the whole backend with no keys |

### Removed

- `app/agents.py` (575 lines) — seven tools defined as closures inside one
  function, a hand-rolled tool-calling loop, and the prose if/else prompt.
- `/diagnose`, `/treatment`, `/upload-report`, `/upload`, `/session` routes.
- The `phase` state machine and `treatmentKeywords` from `App.jsx`
  (562 lines changed; the file shrank by roughly a third).

### Tools

All are module-level `@tool` functions — importable and testable without an
agent or a request. They read and write conversation state through a contextvar.

| Tool | Arguments |
|---|---|
| `medical_lookup` | `query` |
| `analyze_lab_report` | `patient_context` |
| `get_patient_record` | `query` |
| `build_treatment_plan` | `symptoms` |
| `find_specialists` | `specialization`, `location` |
| `get_doctor_availability` | `doctor_name` |
| `book_appointment` | `doctor_name`, `slot`, `patient_name` |

---

## 3. Request flow

One endpoint. Every path ends in the same `action(text)` call, and the agent
receives one string with **nothing wrapped around it** — recognising that a page
of lab values wants diagnosing is the agent's job, not the caller's.

`intent=treatment` is the one exception, because the button carries no text of
its own: it sends the conversation so far.

| Trigger | What `action()` receives |
|---|---|
| Image attached | the text OCR read off it, verbatim (preceded by the patient's typed note, if any) |
| Treatment button | `[CONVERSATION] Patient: … ACDSS: … [END]` + *"build my treatment plan"* |
| Typed question | The question, unchanged |

`POST /chat` accepts **both** `multipart/form-data` and `application/json`, so a
cached frontend bundle or a plain API client both work.

The response is a reply plus zero or more **UI events** (`diagnosis`,
`treatment`, `doctors`, `booking`). Tools emit these; the frontend renders
whatever arrives, in order. Adding a card type no longer touches the flow.

---

## 4. Guardrails moved from prompt to code

Preconditions the prompt used to assert are now enforced in the tools, which
return a fact the agent can act on instead of a value it can invent.

- **`analyze_lab_report` takes no report text.** It reads the authoritative OCR
  copy from the session. The OCR text also reaches the model as the patient's
  message, so it can discuss the report — but that copy is not what gets
  analysed, so a paraphrased or fabricated value can't change the diagnosis.
- **`build_treatment_plan`** reports that no diagnosis exists rather than
  inventing one.
- **`book_appointment`** validates doctor, slot, and patient name against the
  database. The previous version gated booking by scanning the patient's text
  for the words *"book"*, *"appointment"*, *"schedule"* — intent classification
  by keyword, the exact pattern being removed everywhere else.
- **Tool returns carry facts only.** An earlier revision embedded instructions
  like *"keep your reply short and warm"* in return values — the prompt's
  if/else tree relocated one level down. A test now fails if any reappear.

---

## 5. Bugs found and fixed

### Security (found in review)

| Issue | Detail |
|---|---|
| **Session hijacking** | `store.get()` honoured any client-supplied `session_id` verbatim, returning the *same Session object*. Verified: a forged id read back another patient's diagnosis, name, and phone. Ids are now server-issued only (`secrets.token_urlsafe(24)`); an unrecognised id yields a fresh session. |
| **Unbounded session store** | Sessions were evicted by age but never by count. 50,000 fabricated ids were all retained. Now LRU-capped at 5,000. |

### Correctness

| Issue | Detail |
|---|---|
| **Patient context silently dropped** | `analyze_lab_report` read `patient.get("notes")`, which nothing ever set. Everything the patient said ("dizzy for three weeks") was discarded before reaching the diagnosis agent. Regression test asserts both the upload note and the model-supplied context arrive. |
| **Cross-turn event bleed** | UI events were buffered on the Session, so two concurrent requests could drain each other's cards. Now buffered per turn in a contextvar. |
| **Cap off by one** | `SessionStore.create()` evicted before inserting, so the store could sit one over its limit. |
| **Duplicate patient rows** | Every booking wrote a new `Patient`. First fixed by matching on name + phone — which, with phone usually `NULL`, degenerated to name-only and **merged unrelated patients**. Superseded by FIX-2 in [`FIXES.md`](FIXES.md): reuse within a session, or on a real identifier, never on name alone. |

### Found by running the server

| Issue | Detail |
|---|---|
| **`422 Unprocessable Entity` on `/chat`** | The backend was serving the old JSON-body `/chat` while the browser sent `FormData` — FastAPI rejected the body before any application code ran, so nothing appeared in the logs. Root cause: `agent.py` now imports `langchain_classic`, which wasn't installed, so the module failed to import and uvicorn kept the old worker alive. `/chat` now accepts both content types; the missing dependency raises a message naming the package, the install command, and this symptom; and `GET /` reports `{"api": "agent-v2"}` so "is the server running my new code?" is one curl. |
| **`"Agent stopped due to max iterations."` shown to the patient** | Hit on the very first live query. `AgentExecutor` returns this string as `output` and **does not raise**, so the existing `try/except` never fired. Models loop on tools regularly. Now detected, logged with the tool sequence, and replaced — and if a card was produced before the agent lost the thread, the reply points at it. Added `max_execution_time=90`. |

---

## 6. Dependency change — action required

**LangChain 1.0 removed `AgentExecutor` and `create_react_agent` from
`langchain.agents`** and moved them to the `langchain-classic` package.
`requirements.txt` pinned `langchain>=0.3.0`, which resolves to 1.3 today — so a
fresh install would have broken.

`agent.py` tries the new home first and falls back to the old one, so both work.

```bash
cd backend
pip install langchain-classic     # or: pip install -r requirements.txt
```

Then **restart uvicorn** — a reload will not pick this up if the module is
currently failing to import.

### Agent constructor

Uses `create_tool_calling_agent`, not `create_react_agent`. ReAct's
`Action Input:` is a single string, and `book_appointment` takes three
arguments — ReAct would collapse them into one blob and booking would break.
Same constructor shape, same `AgentExecutor`, same `action()`; swap one line to
change it.

---

## 7. Testing

```bash
cd backend
python -m pytest tests/ -q              # 21 tests, no keys needed
```

Covers: the three entry-point compositions, a full consultation in one turn,
every guardrail, session security, the multipart/JSON contract, retrieval
behaviour, and both runtime bugs above.

**These tests script the tool calls.** They prove the wiring works. They prove
nothing about whether the real model *chooses* the right tool — which is the
question behind "it isn't behaving like an agent".

```bash
python tests/eval_agent_behaviour.py --repeat 3     # needs GROQ_API_KEY
```

11 cases against the live model, scoring whether it reaches for the right tool
and abstains when it should. Non-deterministic — read the score as a signal, not
a gate. `--no-rag` stubs the vector store if `GOOGLE_API_KEY` isn't set.

```bash
python tests/offline_server.py          # port 8000, no keys, no network
```

The real routes, session store, tool loop, and DB with the LLM, RAG, and OCR
stubbed. For frontend work without spending tokens. Tool choices there are
keyword rules, **not** model decisions.

---

## 8. Outstanding

- **The live eval has not been run.** It needs a real Groq key; the development
  sandbox could not reach `api.groq.com`. Until it runs, whether the model
  reliably picks the right tool is unverified.
- **`medical_lookup` has not been exercised against real Chroma** — only against
  a stub. The collections are populated (147 and 107 embeddings) but retrieval
  quality and the `MIN_RELEVANCE = 0.15` threshold are untuned.
- **Clicking a doctor slot bypasses the agent**, posting straight to
  `/appointments`. Deliberate — a click is unambiguous and shouldn't wait on an
  LLM — but it means two code paths write bookings.
- **`app/ocr.py` still hardcodes a Windows Tesseract path** as its default.
- **Sessions are in-memory**, so a restart drops every conversation. `SessionStore`
  is the only thing that needs replacing to move to Redis.
