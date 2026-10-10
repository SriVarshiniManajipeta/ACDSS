import os
import time 
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from dotenv import load_dotenv
load_dotenv()

_THIS_DIR = Path(__file__).resolve().parent
CHROMA_TREATMENT_DB_PATH = os.getenv(
    "CHROMA_TREATMENT_DB_PATH",
    str(_THIS_DIR / "chroma_db"),
)

def create_vector_database_from_pdf(pdf_path: str):
    print(f"[ChromaDB] Will be saved to: {CHROMA_TREATMENT_DB_PATH}")
    print("Initializing Gemini embedding model...")

    embeddings = GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2-preview"
    )

    print(f"Loading clinical guidelines from {pdf_path}...")
    loader = PyPDFLoader(pdf_path)
    raw_documents = loader.load()
    
    print(f"Successfully loaded {len(raw_documents)} pages.")

    print("Chunking documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,   
        chunk_overlap=150, 
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunked_docs = text_splitter.split_documents(raw_documents)

    total_docs = len(chunked_docs)
    print(f"Total chunks to embed: {total_docs}")
    print("Initializing ChromaDB...")
    
    vectorstore = Chroma(
        persist_directory=CHROMA_TREATMENT_DB_PATH,
        embedding_function=embeddings,
        collection_name="Treatment_guidelines",
    )
    
    batch_size = 50 

    for i in range(0, total_docs, batch_size):
        batch = chunked_docs[i : i + batch_size]
        print(f"Embedding chunk {i} to {min(i + batch_size, total_docs)} out of {total_docs}...")

        vectorstore.add_documents(batch)
        
        if i + batch_size < total_docs:
            print("Taking a 60-second nap to respect Google's free tier rate limits...")
            time.sleep(60)
            
    print("Success! The local RAG database is ready.")

if __name__ == "__main__":

    PATH_TO_YOUR_PDF = str(_THIS_DIR / "treatment_guidelines.pdf") 
    
    if os.path.exists(PATH_TO_YOUR_PDF):
        create_vector_database_from_pdf(PATH_TO_YOUR_PDF)
    else:
        print(f"Error: Could not find the file at {PATH_TO_YOUR_PDF}")

