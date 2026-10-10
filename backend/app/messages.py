"""
messages.py
===========
Turns what the patient did into the one string `action()` receives.

The agent takes a single string. There are only two things that string can be:

    what the patient typed        →  passed through untouched
    what OCR read off their image →  passed through untouched

Nothing is added. An earlier version wrapped the report in
"Please run the diagnosis on this report and tell me what it means" — which is
the caller telling the agent what to do, i.e. the flow hardcoded one level up.
The extracted text simply *becomes* the patient's message, and the agent works
out what it is and what to do about it.

The one exception is the Treatment button, which has no text of its own: it
sends the conversation so far, because that is literally what the patient is
pointing at when they press it.
"""

# Bounds, not instructions. A 40-page PDF would blow the context window; these
# cap the input without telling the agent anything.
MAX_REPORT_CHARS = 6_000
MAX_NOTE_CHARS = 500


# ── 1. Lab report uploaded ───────────────────────────────────────────────────

# What the patient is asking for right now — read the report. Not an
# instruction about which tools to use or avoid: naming tools here (or
# forbidding them, "do not build a treatment plan until asked") is the
# caller deciding the flow again, and it doesn't even work reliably — a
# model that wants to chain diagnosis -> plan -> doctors -> booking off one
# upload isn't stopped by asking it not to in prose. That chaining is
# actually prevented by session.blocked_after(), enforced in the tools.
SCOPE_LINE = "I'd like to know what this report shows."


def report_message(report_text: str, note: str = "") -> str:
    """The OCR text, as the patient's message.

    If they typed something alongside the image it goes first, the way a person
    would say "I've been tired lately" and then hand over the paper.

    Note: `analyze_lab_report` does not read this string — it reads the
    authoritative copy parked on the session — so a model that paraphrases what
    it sees here cannot change what actually gets diagnosed.
    """
    body = (report_text or "").strip()[:MAX_REPORT_CHARS]
    note = (note or "").strip()[:MAX_NOTE_CHARS]
    text = f"{note}\n\n{body}" if note else body
    return f"{text}\n\n{SCOPE_LINE}"


# ── 2. Anything typed ────────────────────────────────────────────────────────

def general_request(message: str) -> str:
    return (message or "").strip()
