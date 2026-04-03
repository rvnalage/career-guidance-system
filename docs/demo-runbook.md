# Demo Runbook

## 1. Start Services

### Backend

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 2. Quick Health Checks

1. Open `http://localhost:8000/health` and confirm `{"status": "ok"}`.
2. Open `http://localhost:8000/docs` and verify API docs load.
3. Open the exact Vite URL shown in terminal (usually `http://localhost:5173` or `http://localhost:5174`) and login.

## 3. RAG Setup For Demo

1. Trigger default ingestion:

```bash
curl -X POST http://localhost:8000/api/v1/rag/ingest/default
```

2. Check status:

```bash
curl "http://localhost:8000/api/v1/rag/status"
```

Expected highlights:
- `enabled: true`
- `document_chunks > 0` after successful ingest
- `ingested_files` includes txt files from `one_note_extract`

## 4. Live Demo Script

1. In Chat page ask: `Give me a data science career roadmap for MTech student`.
2. Show response contains practical guidance plus source citations.
3. Open Dashboard and show summary, recommendation, and explanation panels.
4. Run psychometric scoring and show top traits.
5. Show market jobs panel and report export.
6. Trigger profile intake upload with JWT auth:

```bash
curl -X POST http://localhost:8000/api/v1/profile-intake/upload \\
	-H "Authorization: Bearer <JWT_TOKEN>" \\
	-F "owner_type=self" \\
	-F "files=@../one_note_extract/ml_roadmap.txt"
```

7. Open Chat again and show profile-aware response continuity.
8. Optional: clear chat/recommendation history and show lifecycle controls.

## 5. Backend Validation Command

```bash
cd backend
python -m pytest -q tests/test_auth.py tests/test_integration.py tests/test_ml.py tests/test_agents.py tests/test_chat.py tests/test_rag.py
```
