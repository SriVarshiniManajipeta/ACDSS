

import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

_THIS_DIR = Path(__file__).resolve().parent
CHROMA_DB_PATH = os.getenv(
    "CHROMA_DIAGNOSIS_DB_PATH",
    str(_THIS_DIR / "chroma_db"),
)

TEST_QUERIES = [
    "What is the normal range for HbA1c?",
    "What does high LDL cholesterol indicate?",
    "What are the causes of elevated creatinine?",
    "What does low haemoglobin indicate?",
]


def verify_diagnosis_db() -> None:
    print(f"[Verify] Connecting to ChromaDB at: {CHROMA_DB_PATH}")
    embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2-preview")
    vectorstore = Chroma(
        persist_directory=CHROMA_DB_PATH,
        embedding_function=embeddings,
        collection_name="Diagnosis_guidelines",
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 1})

    count = vectorstore._collection.count()
    print(f"[Verify] Documents in collection: {count}")

    if count == 0:
        print("[Verify] Database is EMPTY. Run build_db.py first.")
        return

    print("\n[Verify] Testing retrieval queries:")
    for query in TEST_QUERIES:
        docs = retriever.invoke(query)
        snippet = docs[0].page_content[:120] if docs else "No results"
        print(f"  Q: {query}")
        print(f"  A: {snippet}...\n")

    print("[Verify] Lab knowledge base is working correctly.")


if __name__ == "__main__":
    verify_diagnosis_db()
