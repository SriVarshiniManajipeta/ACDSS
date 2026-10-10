# ACDSS Full Stack Starter

## Backend
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows
uvicorn app.main:app --reload --port 8000
```

## Frontend
```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:5173
Backend docs: http://localhost:8000/docs

## What it includes
- ChatGPT-like React UI
- FastAPI backend
- SQLite database
- Doctor list table
- Patient table
- Appointment booking table
- Rule-based ACDSS referral agent

You can later replace `backend/app/agents.py` with your LangGraph + RAG diagnosis/treatment workflow.
