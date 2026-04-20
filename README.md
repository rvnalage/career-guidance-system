# Career Guidance System (MTech Project)

Agentic AI-driven career guidance platform with secure user accounts, personalized chat guidance, recommendation history, and dashboard reporting.

## Implemented Highlights

- JWT-based authentication (`register`, `login`, protected `/me` routes)
- Agentic chat orchestration with intent routing
- Persistent chat history with clear-history support
- Career recommendation engine (skills + interests + education scoring)
- Feedback-learning personalization (Helpful/Not Helpful + rating/tags)
- Psychometric scoring with persisted user profile (`/psychometric/score/me`, `/psychometric/profile/me`)
- Profile intake from uploaded text files with self/on-behalf persistence modes (`/profile-intake/upload`)
- Recommendation explainability panel (SHAP/LIME with safe fallback)
- Real-time job market API integration with resilient fallback
- Recommendation history with clear-history support
- Dashboard summary + backend-generated report export
- React frontend with auth flow, chat, dashboard continuity panels
- Automated backend test coverage for auth/chat/recommendation/dashboard flows

## Tech Stack

- Backend: FastAPI, SQLAlchemy, PostgreSQL, MongoDB
- Frontend: React (Vite), React Router, Axios
- AI/Logic: Deterministic agent routing + recommendation scoring service
- Infra: Docker Compose (Postgres, MongoDB, Redis, Backend, Frontend)

## Documentation

Core architecture and design:
- [RAG + LLM Integration](docs/rag-llm-integration.md) — How the retrieval-augmented generation system grounds LLM responses in your career knowledge base
- [RAG Ingestion Operations](docs/rag-ingestion-operations.md) — How to run ingestion, verify chunk quality, and troubleshoot indexing issues
- [API Specification](docs/api-spec.md)
- [System Design](docs/design.md)
- [Testing Strategy](docs/testing-strategy.md)

Fine-tuning:
- [TinyLlama Fine-tuning Quick Start](TINYLLAMA_QUICKSTART.md) — One-command fine-tuning for local model optimization

## Project Structure

```text
career-guidance-system/
  backend/
  frontend/
  ml-models/
  config/
  kubernetes/
  docker-compose.yml
```

## Environment Setup

### Backend

1. Copy env template:
`backend/.env.example` -> `backend/.env`

2. Important keys already aligned with code:
- `DATABASE_URL`
- `MONGODB_URL`
- `MONGODB_DATABASE`
- `MONGODB_HISTORY_COLLECTION`
- `MONGODB_RECOMMENDATION_COLLECTION`
- `MONGODB_FEEDBACK_COLLECTION`
- `MONGODB_PSYCHOMETRIC_COLLECTION`
- `MONGODB_USER_PROFILE_COLLECTION`
- `JWT_SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `JOB_MARKET_API_URL`
- `RAG_ENABLED` (default `true`)
- `RAG_TOP_K` (retrieved chunk count)
- `RAG_CANDIDATE_POOL_SIZE` (candidate count before reranking)
- `LLM_ENABLED` (set `true` to enable local LLaMA responses)
- `LLM_PROVIDER` (`ollama`, `openai`, or `groq`)
- `LLM_BASE_URL` (default `http://localhost:11434`)
- `LLM_MODEL` (example `tinyllama:latest` in template, `llama3.1:8b` in code defaults)
- `LLM_FINETUNED_MODEL` (optional, overrides base model when set)
- `LLM_REQUEST_TIMEOUT_SECONDS`
- `CHAT_REPLY_MAX_SENTENCES` (hard cap applied to final reply text; default `8`)
- `LLM_RAG_CONTEXT_MAX_CHARS` (caps retrieved context size included in LLM prompt; default `1400`)
- `LLM_REQUIRE_RAG_CONTEXT` (if `true`, LLM enhancement runs only when RAG context exists)
- `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_MAX_TOKENS`
- `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_MAX_TOKENS`

### Frontend

1. Copy env template:
`frontend/.env.example` -> `frontend/.env`

2. Ensure backend API URL:
- `VITE_API_URL=http://localhost:8000/api/v1`

## Run (Docker)

From repo root:

```bash
docker-compose up --build
```

Access:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Run (Local Development)

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

## API Surface (Current)

Base prefix: `/api/v1`

- System
  - `GET /`
  - `GET /health`
- Auth
  - `POST /auth/register`
  - `POST /auth/login`
- Users
  - `GET /users/me`
  - `PUT /users/me`
- Chat
  - `POST /chat/message` (guest/public payload includes `user_id`)
  - `POST /chat/message/me` (authenticated)
  - Responses include `rag_context`, `rag_citations`, `response_source`, `llm_used`, and `response_time_ms`
- History
  - `GET /history/me`
  - `DELETE /history/me`
- Recommendations
  - `POST /recommendations/generate`
  - `POST /recommendations/explain/me`
  - `POST /recommendations/feedback/me`
  - `GET /recommendations/feedback/me`
  - `GET /recommendations/xai/status`
  - `GET /recommendations/history/me`
  - `DELETE /recommendations/history/me`
- Psychometric
  - `POST /psychometric/score` (public scoring)
  - `POST /psychometric/score/me` (authenticated + persisted)
  - `GET /psychometric/profile/me`
- Profile Intake
  - `POST /profile-intake/upload` (multipart upload; authenticated)
- Market
  - `GET /market/jobs`
- LLM
  - `GET /llm/status`
- RAG
  - `GET /rag/status`
  - `POST /rag/ingest`
  - `POST /rag/ingest/default`
  - `GET /rag/search?query=...`
  - `POST /rag/evaluate`
  - `GET /rag/telemetry`
  - `GET /rag/telemetry/trends`
  - `GET /rag/telemetry/trends/series`
  - `GET /rag/telemetry/trends/combined`
- Dashboard
  - `GET /dashboard/summary/me`
  - `GET /dashboard/report/me`

## Frontend Features (Current)

- Home: register + login
- Chat: sends messages, loads history for authenticated users, clear history button
- Dashboard:
  - progress summary
  - recommendation generation form
  - recommendation explanation panel
  - recommendation feedback capture
  - psychometric scoring and profile persistence
  - real-time market jobs panel
  - recommendation timeline panel
  - chat continuity panel
  - export JSON report button

## Testing

From `backend/`:

```bash
python -m pytest -q tests/test_auth.py tests/test_chat.py tests/test_rag.py tests/test_profile_intake.py
```

Full focused suite used during implementation:

```bash
python -m pytest -q tests/test_auth.py tests/test_integration.py tests/test_ml.py tests/test_agents.py tests/test_chat.py tests/test_rag.py tests/test_profile_intake.py tests/test_xai_explanations.py
```

## XAI Runtime Matrix

- Python `3.12` (recommended): SHAP + LIME available in most setups.
- Python `3.13`: SHAP is supported in this project; LIME may be unavailable depending on dependency constraints.
- Fallback mode: if SHAP/LIME cannot load, the backend still returns deterministic weighted contributions.

Check runtime mode:

```bash
GET /api/v1/recommendations/xai/status
```

Example response fields:
- `active_mode`: `shap` | `lime` | `fallback`
- `shap_available`: `true/false`
- `lime_available`: `true/false`

Demo runbook: `docs/demo-runbook.md`

Architecture coverage docs:
- `docs/model-coverage.md`
- `docs/phase2-implementation-checklist.md`

RAG evaluation assets:
- `ml-models/datasets/rag_eval_dataset_template.jsonl`
- `ml-models/evaluation/evaluate_rag_scorecard.py`

Run retrieval scorecard:

```bash
python ml-models/evaluation/evaluate_rag_scorecard.py --api-url http://localhost:8000/api/v1
```

LLaMA customization starter files:
- `ml-models/training/llama_customization.md`
- `ml-models/training/prepare_llama_dataset.py`
- `ml-models/training/train_llama_qlora.py`
- `ml-models/evaluation/llama_eval_checklist.md`
- `ml-models/evaluation/benchmark_llama.py`
- `scripts/run_llama_customization.ps1`

## Build Frontend

From `frontend/`:

```bash
npm run build
```

## Suggested Demo Flow

1. Register and login
2. Trigger ingestion: `POST /api/v1/rag/ingest/default`
2. Open Chat, send guidance queries
3. Show retrieved references/citations from chat response
4. Open Dashboard, score psychometric profile
5. Generate recommendations and review explanation panel
6. Submit feedback on recommendations and regenerate
7. Search live job market results
8. Show continuity panels (recent chat + recommendation snapshot)
9. Export report JSON from dashboard
10. Clear chat/recommendation history to demonstrate lifecycle controls

## License

MIT
