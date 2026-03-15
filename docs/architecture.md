# Career Guidance System — Architecture

## 1. Overview

The Career Guidance System is an AI-powered web application for MTech students that provides personalised career guidance through a conversational interface. It combines rule-based intent routing, Retrieval-Augmented Generation (RAG), a local Large Language Model (LLM), and explainable AI (XAI) to deliver transparent, context-aware career advice.

```
┌────────────────────────────────────────────────────────────┐
│                        Client Layer                        │
│   React / Vite SPA  (localhost:5173 or :3000)              │
└─────────────────────────┬──────────────────────────────────┘
                          │ HTTPS / REST
┌─────────────────────────▼──────────────────────────────────┐
│                  API Gateway Layer                          │
│   FastAPI 0.104  ·  CORS Middleware  ·  JWT Auth Guard     │
│   /api/v1   (Swagger /docs, ReDoc /redoc)                  │
└──────┬──────────┬────────────┬───────────┬─────────────────┘
       │          │            │           │
┌──────▼──┐  ┌───▼────┐  ┌────▼───┐  ┌───▼──────────────────┐
│  Auth   │  │  Chat  │  │  Rec.  │  │  Other Routes        │
│ Routes  │  │ Routes │  │ Routes │  │  (rag, psych, market,│
│         │  │        │  │        │  │   history, dashboard)│
└──────┬──┘  └───┬────┘  └────┬───┘  └───┬──────────────────┘
       │         │             │          │
┌──────▼─────────▼─────────────▼──────────▼──────────────────┐
│                     Service Layer                           │
│  agent_service · recommendation_service · llm_service      │
│  rag_service   · history_service        · profile_service  │
│  psychometric_service · market_service  · user_service     │
└──────┬──────────┬─────────────────┬────────────────────────┘
       │          │                 │
┌──────▼──┐  ┌────▼──────────┐  ┌──▼──────────────────────┐
│   NLP   │  │  Agent Layer  │  │      ML / XAI Layer      │
│ Intent  │  │  7 Agents     │  │  SHAP · LIME · Fallback  │
│ Router  │  │  (BaseAgent)  │  │  interpretability utils  │
└─────────┘  └───────────────┘  └────────────────────────┘
                    │
┌───────────────────▼────────────────────────────────────────┐
│                   RAG Pipeline                             │
│  Ingester → VectorStore (TF-IDF) → Retriever → Reranker   │
│  KnowledgeBase (one_note_extract docs)                     │
└────────────────────────────────────────────────────────────┘
                    │
┌───────────────────▼────────────────────────────────────────┐
│                   Data Layer                               │
│  PostgreSQL (users)  ·  MongoDB (chat, profiles, history)  │
│  Redis (reserved)   ·  In-memory vector store             │
└────────────────────────────────────────────────────────────┘
                    │
┌───────────────────▼────────────────────────────────────────┐
│              External / Optional Services                  │
│  Ollama LLM (localhost:11434, llama3.1:8b)                 │
│  Remotive Job API (https://remotive.com/api/remote-jobs)   │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Layer-by-Layer Description

### 2.1 Client Layer

| Aspect | Detail |
|--------|--------|
| Framework | React + Vite |
| Build target | Static assets served by Nginx (production), Vite dev server (development) |
| Ports | 3000 (Nginx container), 5173 (Vite dev) |
| Auth | JWT Bearer token stored in memory / localStorage; attached via `Authorization` header |
| Container | `frontend/Dockerfile` — multi-stage: `node:18-alpine` build → `nginx:alpine` serve |

### 2.2 API Gateway Layer

| Aspect | Detail |
|--------|--------|
| Framework | FastAPI 0.104.1, Python 3.13 |
| Prefix | `/api/v1` |
| CORS | Configured via `settings.cors_origins`; dev allows `localhost:3000`, `localhost:5173` |
| Auth | HS256 JWT; `get_current_user` dependency injects authenticated `User` model |
| Docs | `/docs` (Swagger UI), `/redoc` (ReDoc), `/openapi.json` |
| Container | `backend/Dockerfile` — `python:3.11-slim` base, `uvicorn` entrypoint |

### 2.3 Route Modules

| Router file | Prefix | Auth required |
|-------------|--------|---------------|
| `auth.py` | `/auth` | No (register/login produce tokens) |
| `chat.py` | `/chat` | Partial — `POST /message` is open; `POST /message/me` requires JWT |
| `recommendations.py` | `/recommendations` | Yes (all endpoints) |
| `psychometric.py` | `/psychometric` | Partial — `/score` is open; `/score/me`, `/profile/me` require JWT |
| `history.py` | `/history` | Yes |
| `dashboard.py` | `/dashboard` | Yes |
| `rag.py` | `/rag` | No |
| `market.py` | `/market` | No |
| `llm.py` | `/llm` | No |
| `users.py` | `/users` | Yes |

### 2.4 Service Layer

Services are async-first (Motor for MongoDB) with synchronous fallback for CPU-only operations.

| Service | Storage | Purpose |
|---------|---------|---------|
| `agent_service` | None (stateless) | Routes messages to agents; returns intent + reply + confidence |
| `llm_service` | None (HTTP to Ollama) | Builds per-intent prompts; calls Ollama `/api/generate` |
| `rag_service` | In-memory VectorStore | Builds RAG context and citation list for a query |
| `history_service` | MongoDB `chat_history` | Append and retrieve chat messages per user |
| `profile_service` | MongoDB `user_profiles` | Persistent multi-turn user profile; extracts skills/interests/role from messages |
| `recommendation_service` | MongoDB `recommendation_history` | Rule-based career recommendations with SHAP/LIME XAI explanations |
| `psychometric_service` | MongoDB `psychometric_profiles` | Scores Big-Five style dimensions; recommends career domains |
| `market_service` | HTTP (Remotive) | Fetches live job listings |
| `user_service` | PostgreSQL `users` | CRUD for registered users |

### 2.5 NLP / Intent Router

File: `app/nlp/intent_recognizer.py`

Intent detection uses **keyword matching with confidence scoring**:

```
score = min(1.0,  0.45  +  keyword_hit_ratio  +  coverage_bonus)
```

- `keyword_hit_ratio` = matched keywords / total keywords for that intent
- `coverage_bonus` = min(0.35, 0.12 × number_of_matches)
- If `score < settings.intent_min_confidence` (default 0.35), falls back to `career_assessment`

**Intent precedence** (ordered to avoid collision):  
`interview_prep → learning_path → recommendation → job_matching → networking → feedback`

Intent keywords:

| Intent | Trigger keywords |
|--------|-----------------|
| `interview_prep` | interview, hr round, technical round, mock |
| `learning_path` | learn, roadmap, course, upskill, study plan |
| `recommendation` | recommend, recommendation, suggest, best role, career option |
| `job_matching` | job, role, match, fit, eligibility |
| `networking` | network, linkedin, referral, mentor, outreach |
| `feedback` | feedback, rate, rating, helpful, not helpful |
| `career_assessment` | *fallback* |

### 2.6 Agent Layer

All agents inherit from `BaseAgent` (abstract class with `respond()` and `suggested_next_step()`).

| Agent class | Intent | Specialisation |
|-------------|--------|----------------|
| `CareerAssessmentAgent` | `career_assessment` | Open-ended career clarification |
| `InterviewPrepAgent` | `interview_prep` | Role-specific technical / behavioural prep |
| `JobMatchingAgent` | `job_matching` | Fit-gap analysis, application strategy |
| `LearningPathAgent` | `learning_path` | Phased roadmaps, weekly milestones |
| `NetworkingAgent` | `networking` | LinkedIn outreach, referral tactics |
| `RecommendationAgent` | `recommendation` | Career role suggestions from skills/interests |
| `FeedbackAgent` | `feedback` | Collects structured rating/tags for personalisation |

### 2.7 RAG Pipeline

Files: `app/rag/`

```
one_note_extract/*.txt
        │
   [Ingester]  — quality filtering, chunking
        │
 [KnowledgeBase]  — in-memory chunk store
        │
  [VectorStore]  — TF-IDF sparse vectors
        │
  [Retriever]   — cosine similarity top-K pool (default K=4, pool=20)
        │  + lexical re-rank + metadata re-rank
        │
[query_rewriter] — expands acronyms, adds synonyms
        │
   top-K chunks → RAG context string + citations list
```

13 domain knowledge files from `one_note_extract/` are ingested at startup. Metadata fields (`source_type`, `topic`, `min_education`) enable filtered retrieval via the `/rag/search` endpoint.

### 2.8 XAI Layer

File: `app/xai/explainer.py`, `app/xai/interpretability.py`

Three-tier waterfall:

```
explain_recommendation(feature_map, weights)
        │
   ① SHAP  ─── import shap → KernelExplainer (nsamples=80)
        │         └── available on Python 3.12 and 3.13
        │
   ② LIME  ─── import lime → LimeTabularExplainer (regression)
        │         └── restricted to Python <3.13 in requirements
        │
   ③ Weighted Fallback  ─── feature × coefficient dot product
                └── always available
```

Feature space (4 dimensions):  
`skill_match`, `interest_match`, `education_fit`, `personalization_bonus`

### 2.9 Data Layer

#### PostgreSQL (via SQLAlchemy 2.x)

Table: `users`

| Column | Type | Notes |
|--------|------|-------|
| `id` | `VARCHAR(36)` | UUID primary key |
| `full_name` | `VARCHAR(120)` | |
| `email` | `VARCHAR(255)` | unique, indexed |
| `hashed_password` | `VARCHAR(255)` | bcrypt |
| `interests` | `VARCHAR(500)` | comma-separated |
| `target_roles` | `VARCHAR(500)` | comma-separated |

#### MongoDB Collections (via Motor async driver)

| Collection | Purpose | Key fields |
|------------|---------|-----------|
| `chat_history` | Per-user message log | `user_id`, `role`, `content`, `timestamp` |
| `recommendation_history` | Snapshot after each generation | `user_id`, `recommendations[]`, `generated_at` |
| `recommendation_feedback` | User ratings of recommendations | `user_id`, `role`, `helpful`, `rating`, `feedback_tags[]` |
| `psychometric_profiles` | Big-Five scores + domain map | `user_id`, `normalized_scores{}`, `top_traits[]`, `recommended_domains[]` |
| `user_profiles` | Active skills/interests/role memory | `user_id`, `skills[]`, `interests[]`, `target_role`, `intent_counts{}`, `updated_at` |

---

## 3. Data Flow: Chat Message (Full Pipeline)

```
Client  POST /api/v1/chat/message/me  { message, context? }
  │
  ├─ JWT guard → resolve current_user
  │
  ├─ history_service.append_message(user_id, "user", message)
  │
  ├─ profile_service.get_user_profile(user_id)          ← MongoDB
  ├─ profile_service.merge_context_with_profile(...)    ← deduplicate skills/interests
  │
  ├─ agent_service.get_agent_response_with_confidence(message, context)
  │     ├─ intent_recognizer.detect_intent_with_confidence(message)
  │     │     └─ returns (intent, confidence, keyword_matches)
  │     ├─ if confidence < 0.35 → override intent = "career_assessment"
  │     └─ agent.respond(message, context) + agent.suggested_next_step(...)
  │
  ├─ rag_service.build_rag_context(message)             ← TF-IDF retrieval + rerank
  ├─ rag_service.get_rag_citations(message)
  │
  ├─ llm_service.generate_llm_reply(...)
  │     ├─ build_prompt: system + intent guidance + few-shot + profile memory
  │     ├─ if LLM_ENABLED=False → return None (agent reply used as-is)
  │     └─ POST http://localhost:11434/api/generate
  │
  ├─ history_service.append_message(user_id, "assistant", reply)
  ├─ profile_service.update_user_profile(user_id, message, context, intent, confidence)
  │
  └─ Response: { reply, suggested_next_step, rag_context, rag_citations[] }
```

---

## 4. Deployment Architecture

### Docker Compose (Development)

```
┌─────────────────────────────────────────┐
│         docker-compose.yml              │
│                                         │
│   frontend   :3000 → :80  (nginx)       │
│   backend    :8000 → :8000 (uvicorn)    │
│   postgres   :5432                      │
│   mongodb    :27017                     │
│   redis      :6379  (reserved)          │
└─────────────────────────────────────────┘
```

### Kubernetes (Production)

Manifests in `kubernetes/`:

| Manifest | Resource |
|----------|---------|
| `backend-deployment.yaml` | Deployment + HPA for backend pods |
| `frontend-deployment.yaml` | Deployment for frontend Nginx pods |
| `postgres-deployment.yaml` | StatefulSet for PostgreSQL |
| `mongodb-deployment.yaml` | StatefulSet for MongoDB |
| `configmap.yaml` | Environment variable configuration |
| `service.yaml` | ClusterIP services for all components |
| `ingress.yaml` | Nginx Ingress controller routing |

---

## 5. Security Architecture

| Control | Implementation |
|---------|---------------|
| Authentication | JWT HS256; `access_token_expire_minutes=60`; `jwt_secret_key` from env |
| Password storage | bcrypt hashing via `passlib` |
| CORS | Strict origin whitelist; `allow_origin_regex` for localhost patterns |
| Input validation | Pydantic v2 models on all request bodies |
| SQL injection | SQLAlchemy ORM (no raw SQL) |
| NoSQL injection | Motor driver with typed insert; never eval user input |
| SSRF | External HTTP calls (Ollama, Remotive) use configured `base_url` from env, not user-controlled |
| Secrets | `jwt_secret_key` defaults documented as insecure; should be overridden in production via env |

---

## 6. Configuration Reference

All settings live in `app/config.py` (Pydantic `BaseSettings`), overridable via environment variables or `.env` file.

| Setting | Env var | Default |
|---------|---------|---------|
| `database_url` | `DATABASE_URL` | `postgresql://postgres:rahulpg@localhost:5432/postgres` |
| `mongodb_url` | `MONGODB_URL` | `mongodb://localhost:27017` |
| `redis_url` | `REDIS_URL` | `redis://localhost:6379/0` |
| `rag_enabled` | `RAG_ENABLED` | `true` |
| `rag_top_k` | `RAG_TOP_K` | `4` |
| `rag_candidate_pool_size` | `RAG_CANDIDATE_POOL_SIZE` | `20` |
| `llm_enabled` | `LLM_ENABLED` | `false` |
| `llm_model` | `LLM_MODEL` | `llama3.1:8b` |
| `llm_finetuned_model` | `LLM_FINETUNED_MODEL` | `""` (use base model) |
| `llm_require_rag_context` | `LLM_REQUIRE_RAG_CONTEXT` | `true` |
| `intent_min_confidence` | `INTENT_MIN_CONFIDENCE` | `0.35` |
| `jwt_secret_key` | `JWT_SECRET_KEY` | `change-me-in-production` |
| `access_token_expire_minutes` | *(code only)* | `60` |
