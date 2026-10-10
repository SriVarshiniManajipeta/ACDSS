
import os
from pathlib import Path
from langchain_groq import ChatGroq
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Four credentials, two providers, tried in order on ANY error (429, 5xx,
# timeout) via .with_fallbacks(). Groq's free tier is 6000 tokens/minute
# with no daily cap — a burst that trips it recovers within a minute.
# Gemini's free tier is 20 requests/day PER (PROJECT, MODEL) — a hard wall
# that doesn't recover until the next day. So: both Groq keys first, Gemini
# only as a last resort. Gemini fallback order is KEY2-then-KEY1 (reversed
# from Diagnosis_Agent's KEY1-then-KEY2) so if both graphs fall all the way
# through to Gemini at once, they land on different keys first.
GROQ_MODEL = os.getenv("ACDSS_TREATMENT_GROQ_MODEL", "llama-3.1-8b-instant")
GEMINI_MODEL = os.getenv("ACDSS_TREATMENT_CHAT_MODEL", "gemini-3.5-flash")
CHAT_MODEL = GROQ_MODEL


def _groq(key_env: str) -> ChatGroq:
    return ChatGroq(
        model=GROQ_MODEL,
        temperature=0,
        max_tokens=2048,
        max_retries=2,
        api_key=os.getenv(key_env),
    )


def _gemini(key_env: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0.4,
        max_retries=6,
        google_api_key=os.getenv(key_env),
    )


_primary, *_fallbacks = [
    _groq("GROQ_API_KEY1"),
    _groq("GROQ_API_KEY2"),
    _gemini("GOOGLE_API_KEY2"),
    _gemini("GOOGLE_API_KEY1"),
]
llm = _primary.with_fallbacks(_fallbacks)

_DEFAULT_CHROMA_PATH = str(Path(__file__).resolve().parent.parent / "Treatment_db" / "chroma_db")
_CHROMA_PATH = os.getenv("CHROMA_TREATMENT_DB_PATH", _DEFAULT_CHROMA_PATH)

print(f"[TreatmentAgent] Connecting to Treatment knowledge base at: {_CHROMA_PATH}")

# Without an explicit key this defaults to reading the plain GOOGLE_API_KEY
# env var, which no longer exists now that it's split into KEY1/KEY2 — that
# would 401 the moment a plan needs retrieval.
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview",
    google_api_key=os.getenv("GOOGLE_API_KEY2"),
)
vectorstore = Chroma(
    persist_directory=_CHROMA_PATH,
    embedding_function=embeddings,
    collection_name="Treatment_guidelines",
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
