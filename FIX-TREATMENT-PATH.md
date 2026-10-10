# Removing the last hardcoded path: the Treatment button

**Status: applied and verified.** 31 tests pass.

Companion to [`CHANGELOG.md`](CHANGELOG.md) (the refactor) and
[`FIXES.md`](FIXES.md) (the code-review findings).

---

## The concern

> `elif fields["intent"] == "treatment": text = treatment_request(...)`
> — then why is this treatment agent called as hardcode?

Correct. After the upload path was fixed to pass OCR text verbatim, this was the
**one remaining branch** where the transport layer decided what the agent should
do. It was wrong in two separate ways.

### 1. It injected an instruction

```python
TREATMENT_REQUEST = """\
Here is our conversation so far:

[CONVERSATION]
{transcript}
[END CONVERSATION]

Based on all of that, please build my treatment plan."""
```

*"Based on all of that, please build my treatment plan"* is `main.py` telling
the agent what to do — the same mistake as the earlier
*"Please run the diagnosis on this report"*, which had already been removed from
the upload path. Deciding that a treatment plan is wanted is the agent's job.

### 2. It sent the conversation to the model twice

This is the part that made it a bug rather than a style problem.

`agent.py` already passes the transcript to the model on its own channel:

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("system", "{patient_record}"),
    MessagesPlaceholder("chat_history"),     # ← the conversation, already here
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])
```

So `treatment_request(session.transcript)` embedded the *same transcript* a
second time, inside `{input}`. The model received the conversation twice on
every press.

### Why that compounded

Each composed string was then stored as a transcript entry, so the next press
embedded the previous press's copy. That is the root cause of FIX-1 in
`FIXES.md` — the growth measured at the time:

| Press | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---:|---:|---:|---:|---:|---:|
| Chars sent to model | 683 | 1,404 | 2,846 | 5,730 | 11,498 | **23,034** |

FIX-1 treated the symptom with a `remember_as` override, so the transcript
stored `"[Pressed Get Treatment Plan]"` instead of the composed prompt. That
flattened the growth but left the duplication and the injected instruction in
place. **Deleting the branch removes the cause.**

---

## The change

### Deleted

| Where | What |
|---|---|
| `app/messages.py` | `TREATMENT_REQUEST`, `treatment_request()`, `render_transcript()`, `SPEAKER`, `MAX_RENDERED_TRANSCRIPT` |
| `app/main.py` | the `elif fields["intent"] == "treatment"` branch, the `remember_as` local, and `intent` from both branches of `_read_turn()` |
| `app/agent.py` | the `remember_as` parameter on `action()` — nothing composes any more, so there is nothing to override |
| `frontend/src/App.jsx` | the `intent` and `echo` parameters on `send()` |

### `app/main.py` — before and after

```python
# before
remember_as = None
if upload is not None:
    ...
    text = report_message(raw_text, message)
elif fields["intent"] == "treatment":
    text = treatment_request(session.transcript)
    remember_as = "[Pressed Get Treatment Plan]"
else:
    text = general_request(message)

turn = await run_in_threadpool(action, text, session.id, parsed_patient, remember_as)
```

```python
# after
if upload is not None:
    raw_text = await run_in_threadpool(_ocr, upload)
    session.pending_report = raw_text          # authoritative copy for the tool
    session.report_note = message.strip()
    text = report_message(raw_text, message)
else:
    text = general_request(message)

turn = await run_in_threadpool(action, text, session.id, parsed_patient)
```

### `frontend/src/App.jsx` — the button types a message

```js
// before
function requestTreatment() {
  return send({ intent: 'treatment', echo: 'Please build my treatment plan.' });
}

// after
function requestTreatment() {
  return send({ message: 'Please build my treatment plan.' });
}
```

The button is now a shortcut for typing, nothing more. It goes through the exact
same path as the text box.

---

## Result

There are now **two** ways to build the agent's input, and neither adds anything:

| Trigger | What `action()` receives |
|---|---|
| Typed a message | that message |
| Attached an image | the text OCR read off it (preceded by the typed note, if any) |

No `intent`. No third case. No injected instruction anywhere in the request path.

### Verified end to end

```
POST /chat  {"message": "Please build my treatment plan."}

input to agent  : 'Please build my treatment plan.'
history to agent: ['HB 9.1 g/dL', 'You have anaemia.']
tools           : ['build_treatment_plan']   events: ['treatment']
```

The input is the plain message. The conversation arrives **once**, via
`chat_history`. The agent still chose `build_treatment_plan` and produced the
card, with nothing telling it to.

### Prompt size across repeated presses

| | press 1 | 5 | 10 |
|---|---:|---:|---:|
| Original | 683 | 11,498 | ~370,000 |
| After FIX-1 (`remember_as`) | 163 | 427 | 517 |
| **Now** | **31** | **31** | **31** |

Constant, because the input no longer depends on the transcript at all.

---

## Tests

Two added, one rewritten. `cd backend && python -m pytest tests/ -q` → **31 passed**.

| Test | Protects |
|---|---|
| `test_treatment_button_is_not_a_special_path` | `treatment_request` / `render_transcript` are gone; `_read_turn` carries no `intent`; `action()` has no `remember_as` |
| `test_conversation_reaches_the_model_once_not_twice` | `chat_history` carries the transcript, and the input for the next turn does not repeat it |
| `test_repeated_treatment_presses_do_not_grow_the_prompt` | rewritten — now asserts the input is *constant* across ten presses, not merely bounded |

---

## What remains, deliberately

One thing in the request path still references the report without the agent
asking. `app/agent.py:108`:

```python
if session.pending_report:
    facts.append("- A lab report has been uploaded and is not yet analysed.")
```

This is a **statement of session state** in the `patient_record` system message,
not an instruction and not a call. The agent is still free to ignore it — proven
by running a model that calls no tools at all: the diagnosis graph ran 0 times
and `pending_report` stayed unconsumed.

Remove it if you want the agent to work purely from the raw text. It is the last
line in the codebase that could be argued either way.
