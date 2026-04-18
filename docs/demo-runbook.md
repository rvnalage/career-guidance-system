# Demo Runbook

## 1. Start Services

### Backend

Default command:

```bash
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

PowerShell alternative:

```powershell
cd career-guidance-system
python -m pip install -r backend/requirements.txt
powershell -ExecutionPolicy Bypass -File scripts/start_backend.ps1 -HostName 127.0.0.1 -Port 8000
```

### Frontend

Default command:

```bash
cd frontend
npm install
npm run dev
```

PowerShell alternative:

```powershell
cd career-guidance-system/frontend
npm install
cd ..
powershell -ExecutionPolicy Bypass -File scripts/start_frontend.ps1 -HostName 127.0.0.1 -Port 5173
```

## 2. Quick Health Checks

1. Open `http://localhost:8000/health` and confirm `{"status": "ok"}`.
2. Open `http://localhost:8000/docs` and verify API docs load.
3. Open `http://localhost:5173/` and login.
4. Check modeling status: `http://localhost:8000/api/v1/modeling/status` — shows ML model enablement and artifacts.

## 2.1 Windows Quick Ops (Ports + Ollama)

Use these when a port is already in use, a stale process is running, or you need to verify local model runtime.

### Check and free backend/frontend ports

```powershell
# Check who is using backend/frontend ports
netstat -ano | findstr :8000
netstat -ano | findstr :5173

# Kill by PID (replace <PID>)
taskkill /PID <PID> /F

# Optional: confirm process name before killing
tasklist /FI "PID eq <PID>"

# One-liner: kill all listeners on 8000 and 5173
for /f "tokens=5" %a in ('netstat -ano ^| findstr :8000') do taskkill /PID %a /F
for /f "tokens=5" %a in ('netstat -ano ^| findstr :5173') do taskkill /PID %a /F
```

### Check and free Ollama port

```powershell
netstat -ano | findstr :11434
taskkill /PID <PID> /F
```

### Ollama runtime commands

```powershell
# Show installed local models
ollama list

# Pull model (first-time)
ollama pull tinyllama:latest

# Run model in terminal for quick sanity check
ollama run tinyllama:latest

# Optional: run project default model
ollama run llama3.1:8b

# Show locally available command help
ollama --help
```

## 3. API Quick Reference

### Authentication

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name":"User","email":"user@example.com","password":"pass","interests":"AI,ML","target_roles":"Data Scientist"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass"}'
```

### Chat & Message Routing

```bash
# Send message (authenticated)
curl -X POST http://localhost:8000/api/v1/chat/message/me \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"message":"How do I become a data scientist?"}'

# Get chat history
curl -H "Authorization: Bearer <JWT_TOKEN>" \
  http://localhost:8000/api/v1/chat/history/me

# Clear chat history
curl -X DELETE -H "Authorization: Bearer <JWT_TOKEN>" \
  http://localhost:8000/api/v1/chat/history/me
```

### Recommendations & Explainability

```bash
# Generate recommendations
curl -X POST http://localhost:8000/api/v1/recommendations/generate \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"interests":["AI","Data Analysis"],"skills":["Python","SQL"]}'

# Explain recommendations (SHAP/LIME/fallback)
curl -X POST http://localhost:8000/api/v1/recommendations/explain/me \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"roles":["Data Scientist","ML Engineer"]}'

# Record feedback (helpful + rating + tags)
curl -X POST http://localhost:8000/api/v1/recommendations/feedback/me \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"role":"Data Scientist","helpful":true,"rating":5,"feedback_tags":["relevant","practical"]}'

# Get recommendation history
curl -H "Authorization: Bearer <JWT_TOKEN>" \
  http://localhost:8000/api/v1/recommendations/history/me

# Get XAI status (SHAP/LIME/fallback mode)
curl http://localhost:8000/api/v1/recommendations/xai/status
```

### Dashboard

```bash
# Get dashboard summary
curl -H "Authorization: Bearer <JWT_TOKEN>" \
  http://localhost:8000/api/v1/dashboard/summary/me

# Get dashboard report (JSON export)
curl -H "Authorization: Bearer <JWT_TOKEN>" \
  http://localhost:8000/api/v1/dashboard/report/me
```

### Psychometric Scoring

```bash
# Score with traits
curl -X POST http://localhost:8000/api/v1/psychometric/score/me \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"openness":8,"conscientiousness":7,"extraversion":6,"agreeableness":7,"neuroticism":4}'

# Get persisted profile
curl -H "Authorization: Bearer <JWT_TOKEN>" \
  http://localhost:8000/api/v1/psychometric/profile/me
```

### Profile Intake

```bash
# Upload profile files
curl -X POST http://localhost:8000/api/v1/profile-intake/upload \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -F "owner_type=self" \
  -F "files=@path/to/file.txt"

# Clear profile memory
curl -X DELETE -H "Authorization: Bearer <JWT_TOKEN>" \
  http://localhost:8000/api/v1/profile-intake/me
```

### RAG & LLM Management

```bash
# RAG ingest (download + chunk knowledge base)
curl -X POST http://localhost:8000/api/v1/rag/ingest/default

# RAG status
curl http://localhost:8000/api/v1/rag/status

# LLM runtime status (enabled, model, safety filter)
curl http://localhost:8000/api/v1/llm/status

# Update LLM config
curl -X POST http://localhost:8000/api/v1/llm/config \
  -H "Content-Type: application/json" \
  -d '{"llm_enabled":true,"rag_enabled":true,"cache_enabled":false}'

# Reset LLM config to defaults
curl -X POST http://localhost:8000/api/v1/llm/config/reset
```

### Modeling & MLOps

```bash
# Get modeling status (model enablement + artifact status)
curl http://localhost:8000/api/v1/modeling/status

# Job market integration
curl 'http://localhost:8000/api/v1/market/jobs?search=data&limit=10'
```

## 4. RAG Setup For Demo

1. Trigger default ingestion:

```bash
curl -X POST http://localhost:8000/api/v1/rag/ingest/default
```

   This reads career guidance documents from `career-guidance-system/rag/knowledge/` (consolidated knowledge base).

2. Check status:

```bash
curl "http://localhost:8000/api/v1/rag/status"
```

Expected highlights:
- `enabled: true`
- `document_chunks > 0` after successful ingest
- `ingested_files` includes 16 txt files from `rag/knowledge/` (backend_developer_path.txt, ml_engineer_path.txt, etc.)

## 5. LLM & Explainability Features

### Check LLM Runtime Status

```bash
curl "http://localhost:8000/api/v1/llm/status"
```

Expected output includes:
- `llm_enabled`: `true` if Ollama is running, `false` otherwise
- `llm_provider`: `"ollama"`
- `llm_model`: Current model (e.g., `"tinyllama:latest"`)
- `llm_finetuned_model`: Optional fine-tuned model path if set
- `rag_context_max_chars`: Retrieval context size cap (default `1400`)
- `safety_filter_enabled`: `true` — applies 3-layer safety (harmful block → off-topic redirect → repetition guard)

### Update LLM Config (Runtime)

```bash
curl -X POST http://localhost:8000/api/v1/llm/config \
  -H "Content-Type: application/json" \
  -d '{"llm_enabled": true, "rag_enabled": true}'
```

### Check Recommendation Explainability Status

```bash
curl "http://localhost:8000/api/v1/recommendations/xai/status"
```

Expected output:
- `active_mode`: `"shap"`, `"lime"`, or `"fallback"` depending on installed libraries
- `features`: Lists 5 features used: `skills_score`, `interests_score`, `education_score`, `psychometric_score`, `cf_score` (collaborative filtering)
- SHAP/LIME provides `[(feature, contribution), ...]` for each recommendation

## 6. MLOps & Modeling Status

```bash
curl "http://localhost:8000/api/v1/modeling/status"
```

Expected output includes:
- `cf_enabled`: Collaborative filtering for recommendations
- `bandit_enabled`: Multi-armed bandit for feedback-driven reranking
- `safety_filter_enabled`: Content safety filter for LLM replies
- `fine_tuning_status`: Infrastructure complete, awaiting training execution
- Artifact paths for each model

### Run Drift Detection

```bash
cd ml-models/evaluation
python detect_input_drift.py --baseline-file drift_baseline.json
```

Outputs `drift_report.json` and exits with code 2 if input drift detected (CI-friendly).

## 7. Live Demo Script

### Core Walkthrough

1. **Chat with RAG + LLM Integration**
   - Ask: `Give me a data science career roadmap for MTech student`
   - Show response contains practical guidance plus source citations
   - Mention: Response is grounded in `rag/knowledge/` documents, not raw LLM hallucination

2. **Dashboard Panels**
   - Open Dashboard and show:
     - **Summary**: User profile, top skills, interests extracted from chat
     - **Recommendation**: Suggested careers with confidence scores and SHAP/LIME feature contributions
     - **Explanation**: Interactive breakdown of which signals (skills, education, interests, psychometric, CF) influenced each recommendation
     - **Psychometric**: Trait scores (openness, conscientiousness, etc.) linked to career suitability

3. **Psychometric Scoring**
   - Call: `POST /api/v1/psychometric/score/me` with custom or template traits
   - Show persisted profile: `GET /api/v1/psychometric/profile/me`

4. **Recommendation Feedback Loop (Bandit-Driven)**
   - Generate recommendations: `POST /api/v1/recommendations/generate`
   - Record feedback with helpful/rating: `POST /api/v1/recommendations/feedback/me`
   - Show updated recommendations next call (bandit policy reranks based on feedback history)
   - Mention: Epsilon-greedy bandit adjusts future ranking based on accumulated reward

5. **Market Jobs Integration**
   - `GET /api/v1/market/jobs?search=data&limit=10` shows live job market data for selected role
   - Fallback behavior if API unavailable (resilient design)

6. **Profile Intake with JWT Auth**
   - Upload profile context:
   ```bash
   curl -X POST http://localhost:8000/api/v1/profile-intake/upload \
     -H "Authorization: Bearer <JWT_TOKEN>" \
     -F "owner_type=self" \
     -F "files=@../one_note_extract/ml_roadmap.txt"
   ```
   - Return to Chat and show profile-aware recommendations (system remembers uploaded context)

7. **Lifecycle Controls**
   - Clear chat: `DELETE /api/v1/chat/history/me`
   - Clear recommendations: `DELETE /api/v1/recommendations/history/me`
   - Clear profile memory: `DELETE /api/v1/profile-intake/me`
   - Show fresh state on next interaction

### Advanced Demo (ML/Modeling Features)

8. **Model Runtime Management**
   - Show modeling status: `GET /api/v1/modeling/status` (CF enabled, Bandit enabled, Safety filter on)
   - Toggle LLM: `POST /api/v1/llm/config` with `llm_enabled: false/true` and observe chat quality difference
   - Show safety filter active: Post harmful query and observe system redirect to on-topic response

9. **Recommendation Ranking Under Bandit**
   - Submit multiple recommendations feedback sessions
   - Show bandit model learns preference patterns
   - Next `POST /api/v1/recommendations/generate` returns reranked results reflecting learned preferences

10. **Export & Report**
    - Generate report: `GET /api/v1/dashboard/report/me`
    - Download structured JSON with all profile, recommendation, and feedback aggregations

## 8. Notes

- **RAG Knowledge Base**: Located at `career-guidance-system/rag/knowledge/` — 16 curated career guidance documents (consolidated from extraction). Source of truth for both RAG retrieval and fine-tuning training data.

- **LLM Integration**: TinyLlama via Ollama enhances agent responses using RAG context when enabled. Prompt is grounded (explicit forbid hallucination), constrained by `LLM_REQUIRE_RAG_CONTEXT` flag, and falls back to deterministic agent response if LLM fails/times out. See [RAG + LLM Integration](rag-llm-integration.md) for code-level details.

- **Explainability (XAI)**: Recommendations include SHAP (priority 1) or LIME (priority 2) feature contributions for each role. Deterministic weighted fallback always available for resilience. 5-feature set: `skills_score`, `interests_score`, `education_score`, `psychometric_score`, `cf_score` (collaborative filtering).

- **Collaborative Filtering**: User-item interaction matrix from recommendation history + feedback. TruncatedSVD model trained offline, runtime service provides cold-start fallback. CF scores blended with content scores and psychometric; appears as explicit feature in XAI output.

- **Feedback & Bandit Adaptation**: Multi-armed bandit (epsilon-greedy) learns from `helpful` + `rating` feedback. Reranks top-K recommendations post content scoring. Policy state persisted in JSON. Configurable epsilon; disabled by default (flag-gated).

- **Safety Filter**: 3-layer defense on LLM replies: (1) block harmful content, (2) redirect off-topic, (3) guard against repetition. Always enabled by default; can be toggled via config.

- **Fine-Tuning Infrastructure**: QLoRA trainer for TinyLlama at `ml-models/training/train_tinyllama_cpu.py`. Dataset (73 JSONL examples) auto-generated from knowledge base. Orchestrated via `scripts/run_tinyllama_finetuning.ps1`. Integration path: set `LLM_FINETUNED_MODEL` env var or export to Ollama custom model.

- **Drift Detection**: `ml-models/evaluation/detect_input_drift.py` runs KS test on user query patterns vs baseline. Outputs `drift_report.json` and exits code 2 on detected drift (CI-friendly).

- **Profile Memory**: User profiles in MongoDB merge (never replace) new signals: skills, interests, target role. Tracks intent usage counts. Fallback in-memory dict ensures operations never fail if MongoDB unavailable.

## 9. Backend Validation Command

Run full test suite:

```bash
cd backend
python -m pytest -v tests/
```

Or individual test modules:

```bash
python -m pytest -v tests/test_auth.py tests/test_integration.py tests/test_ml.py tests/test_agents.py tests/test_chat.py tests/test_rag.py tests/test_recommendations.py tests/test_dashboard.py
```

Expected: All tests pass; includes coverage for:
- Auth flow (register, login, JWT verification)
- Chat orchestration (intent routing, RAG context, LLM fallback)
- Recommendation generation + explainability (SHAP/LIME/fallback)
- Psychometric scoring + profile persistence
- Bandit feedback adaptation
- Dashboard summary + report export
- Profile intake (upload + memory merge)
- Safety filter on LLM replies
