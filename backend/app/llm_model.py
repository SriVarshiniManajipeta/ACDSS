

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Four credentials, two providers. Ordered by reliability for this app's
# traffic pattern: Groq's free tier is 6000 tokens/minute with no daily cap
# — a burst that trips it recovers within a minute. Gemini's free tier is
# 20 requests/day PER (PROJECT, MODEL) — a hard wall that doesn't recover
# until the next day. So: both Groq keys first, Gemini only as a last
# resort. `.with_fallbacks()` (used below, and in agent.py for the
# tool-calling agent) tries each in order and moves to the next on ANY
# exception — a 429, a timeout, a transient 5xx.
GROQ_CHAT_MODEL = os.getenv("ACDSS_CHAT_MODEL", "llama-3.3-70b-versatile")
GEMINI_CHAT_MODEL = os.getenv("ACDSS_CHAT_MODEL_GEMINI", "gemini-3.5-flash")

# Kept for tests/eval_agent_behaviour.py, which just prints this.
CHAT_MODEL = GROQ_CHAT_MODEL


def _groq(key_env: str) -> ChatGroq:
    return ChatGroq(
        model=GROQ_CHAT_MODEL,
        temperature=0.4,
        max_retries=2,
        api_key=os.getenv(key_env),
    )


def _gemini(key_env: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=GEMINI_CHAT_MODEL,
        temperature=0.4,
        max_retries=6,
        google_api_key=os.getenv(key_env),
    )


# Exposed as a list (not pre-combined with .with_fallbacks()) because the
# outer agent needs tool-calling: create_tool_calling_agent() requires
# llm.bind_tools(), which a fallback-wrapped Runnable doesn't expose. Each
# candidate gets bound to tools individually in agent.py, then THOSE are
# combined with .with_fallbacks(). llm itself stays a single model so
# nothing else that imports it needs to change.
llm_candidates = [
    _groq("GROQ_API_KEY1"),
    _groq("GROQ_API_KEY2"),
    _gemini("GOOGLE_API_KEY1"),
    _gemini("GOOGLE_API_KEY2"),
]
llm = llm_candidates[0]
