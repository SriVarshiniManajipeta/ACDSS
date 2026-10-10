

from __future__ import annotations

import os
import secrets
import time
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

SESSION_TTL_SECONDS = 60 * 60 * 6      
MAX_SESSIONS = 5_000                  
MAX_TRANSCRIPT_TURNS = 12            
MAX_TRANSCRIPT_CHARS = 2_000     


@dataclass
class Session:
    """Everything the agent knows about one patient conversation."""

    id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    patient: dict = field(default_factory=dict)
    patient_id: Optional[int] = None

    diagnosis: Optional[dict] = None
    treatment: Optional[dict] = None
    booking: Optional[dict] = None

    pending_report: Optional[str] = None
    report_note: str = ""    
    analysed_reports: int = 0

    transcript: list[dict] = field(default_factory=list)

    def remember(self, role: str, content: str) -> None:
        if not content:
            return
        self.transcript.append({
            "role": role, "content": content[:MAX_TRANSCRIPT_CHARS],
        })
        if len(self.transcript) > MAX_TRANSCRIPT_TURNS:
            del self.transcript[:-MAX_TRANSCRIPT_TURNS]

    def patient_name(self) -> str:
        """The patient's real name, or "" if we genuinely don't know it."""
        name = (self.patient.get("name") or "").strip()
        return "" if name.lower() in ("", "guest", "unknown") else name

    def has_diagnosis(self) -> bool:
        d = self.diagnosis or {}
        return bool(d.get("primary_hypothesis") or d.get("extracted_lab_values"))

    def touch(self) -> None:
        self.updated_at = time.time()


class SessionStore:
    """In-memory store, LRU-capped, with lazy TTL eviction.

    Swap this for Redis and nothing else in the codebase changes.
    """

    def __init__(self, ttl: int = SESSION_TTL_SECONDS, max_sessions: int = MAX_SESSIONS):
        self._sessions: "OrderedDict[str, Session]" = OrderedDict()
        self._ttl = ttl
        self._max = max_sessions

    def create(self) -> Session:
        session = Session(id=secrets.token_urlsafe(24))
        self._sessions[session.id] = session
        self._evict()
        return session

    def get(self, session_id: Optional[str]) -> Optional[Session]:
        """Return an existing session, or None. Never creates."""
        self._evict()
        session = self._sessions.get(session_id or "")
        if session is not None:
            self._sessions.move_to_end(session.id)
            session.touch()
        return session

    def get_or_create(self, session_id: Optional[str]) -> Session:
        """Resolve a session id, issuing a fresh one if it isn't ours.

        An unrecognised id is NOT adopted — the caller gets a new session with
        a new server-generated id, which it learns from the response. This is
        what stops a client from naming (and so reading) someone else's session.
        """
        return self.get(session_id) or self.create()

    def _evict(self) -> None:
        cutoff = time.time() - self._ttl
        for sid in [s.id for s in self._sessions.values() if s.updated_at < cutoff]:
            self._sessions.pop(sid, None)
        while len(self._sessions) > self._max:
            self._sessions.popitem(last=False)


store = SessionStore()

_current: ContextVar[Optional[Session]] = ContextVar("acdss_session", default=None)
_events: ContextVar[Optional[list]] = ContextVar("acdss_events", default=None)


@contextmanager
def use_session(session_id: Optional[str]) -> Iterator[Session]:
    """Bind a session and a fresh event buffer for one agent turn."""
    session = store.get_or_create(session_id)
    session_token = _current.set(session)
    events_token = _events.set([])
    try:
        yield session
    finally:
        session.touch()
        _current.reset(session_token)
        _events.reset(events_token)


def current_session() -> Session:
    """The session the calling tool belongs to.

    Raises rather than returning a blank session — a tool running outside a
    bound session is a wiring bug, not a runtime condition.
    """
    session = _current.get()
    if session is None:
        raise RuntimeError(
            "No active ACDSS session. Tools must run inside `use_session(...)`."
        )
    return session


def emit(kind: str, data: Any) -> None:
    """Queue a card for the frontend. `kind` maps 1:1 to a React component."""
    buffer = _events.get()
    if buffer is None:
        raise RuntimeError("emit() called outside `use_session(...)`.")
    buffer.append({"kind": kind, "data": data})


def collect_events() -> list[dict]:
    """Take this turn's cards. Call once, at the end of the turn."""
    return list(_events.get() or [])


# One clinical step per turn.
#
# The model was chaining diagnosis -> treatment -> doctors -> booking off a
# single uploaded image, because after `find_specialists` it holds a doctor, a
# slot and (from the sidebar) a name, so every guardrail is satisfied and it
# just keeps going. Asking it not to, in the prompt, did not hold.
#
# This is enforcement, not flow: a tool that would produce a *second* clinical
# card in the same turn declines and says why. The agent still chooses what to
# call and in what order — it simply cannot stack four irreversible steps onto
# one message the patient never expanded on.
#
# Set ACDSS_ONE_STEP_PER_TURN=0 to allow "diagnose this, plan it, and find me
# a doctor" to complete in a single turn.
ONE_STEP_PER_TURN = os.getenv("ACDSS_ONE_STEP_PER_TURN", "1") == "1"


def blocked_after(*kinds: str) -> Optional[str]:
    """The first of `kinds` already shown this turn, if that should stop a
    second clinical step. None when nothing blocks.

    The toggle is read here, at call time, rather than captured by each tool at
    import — otherwise it could never be flipped in a test or at runtime.
    """
    if not ONE_STEP_PER_TURN:
        return None
    done = {event["kind"] for event in (_events.get() or [])}
    return next((kind for kind in kinds if kind in done), None)
