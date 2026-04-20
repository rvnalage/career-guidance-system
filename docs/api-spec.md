# Career Guidance System — API Specification

**Base URL**: `http://localhost:8000/api/v1`  
**OpenAPI docs**: `GET /docs` (Swagger UI) | `GET /redoc`  
**Auth scheme**: `Bearer <JWT>` in `Authorization` header

---

## Conventions

- All request and response bodies are `application/json`.
- `POST /profile-intake/upload` uses `multipart/form-data`.
- Authenticated endpoints are marked with 🔒.
- Timestamps follow ISO-8601 format.
- Error responses use FastAPI's default `{ "detail": "<message>" }` shape.
- HTTP 503 is returned when a backing database is temporarily unavailable.

---

## 1. System Endpoints

### `GET /`

Health check — confirms the API is running.

**Response `200`**
```json
{
  "message": "Career Guidance System API is running",
  "version": "0.1.0",
  "environment": "development"
}
```

---

### `GET /health`

Lightweight liveness probe.

**Response `200`**
```json
{ "status": "ok" }
```

---

## 2. Authentication — `/api/v1/auth`

### `POST /auth/register`

Create a new user account.

**Request body**
```json
{
  "full_name": "Rahul Sharma",
  "email": "rahul@example.com",
  "password": "SecurePass123!",
  "interests": ["machine learning", "data analysis"],
  "target_roles": ["Data Scientist", "ML Engineer"]
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `full_name` | string | ✓ | |
| `email` | string | ✓ | Must be unique |
| `password` | string | ✓ | Stored as bcrypt hash |
| `interests` | string[] | — | Defaults to `[]` |
| `target_roles` | string[] | — | Defaults to `[]` |

**Response `200`**
```json
{ "message": "User registered successfully: rahul@example.com" }
```

**Error responses**

| Status | Condition |
|--------|-----------|
| 409 Conflict | Email already registered |
| 503 Service Unavailable | PostgreSQL unavailable |

---

### `POST /auth/login`

Authenticate and receive a JWT.

**Request body**
```json
{
  "email": "rahul@example.com",
  "password": "SecurePass123!"
}
```

**Response `200`**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error responses**

| Status | Condition |
|--------|-----------|
| 401 Unauthorized | Invalid email or password |
| 503 Service Unavailable | PostgreSQL unavailable |

---

## 3. Users — `/api/v1/users` 🔒

### `GET /users/me` 🔒

Retrieve the authenticated user's profile.

**Response `200`**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "Rahul Sharma",
  "email": "rahul@example.com",
  "interests": ["machine learning", "data analysis"],
  "target_roles": ["Data Scientist", "ML Engineer"]
}
```

---

### `PUT /users/me` 🔒

Update the authenticated user's profile.

**Request body** — same shape as `UserProfile` response above.

**Response `200`** — updated `UserProfile` object.

---

## 4. Chat — `/api/v1/chat`

### `POST /chat/message`

Send a chat message as an anonymous user (no JWT required).

**Request body**
```json
{
  "user_id": "anonymous-session-abc123",
  "message": "I want to become a data scientist, what should I learn?",
  "context_owner_type": "self",
  "context": {
    "target_role": "data scientist",
    "skills": ["python", "sql"],
    "interests": ["machine learning"]
  },
  "skills": ["python", "sql"],
  "interests": ["machine learning"],
  "education_level": "Masters",
  "psychometric_dimensions": {
    "investigative": 4,
    "realistic": 3,
    "artistic": 2,
    "social": 4,
    "enterprising": 5,
    "conventional": 3
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `user_id` | string | ✓ | Any string identifier for the session |
| `message` | string | ✓ | The user's question or message |
| `context_owner_type` | string | — | `self` or `on_behalf` (default `self`) |
| `context` | object | — | Optional structured context |
| `skills` | string[] | — | Optional shortcut list merged into context |
| `interests` | string[] | — | Optional shortcut list merged into context |
| `education_level` | string | — | Optional education signal |
| `psychometric_dimensions` | object | — | Optional psychometric numeric map (UI defaults to six RIASEC-style dimensions) |

**Context object fields** (all optional)

| Field | Type | Description |
|-------|------|-------------|
| `target_role` | string | Desired career role |
| `skills` | string[] | Known skills |
| `interests` | string[] | Career interests |

**Response `200`**
```json
{
  "reply": "To become a data scientist, start with Python basics and statistics...",
  "suggested_next_step": "Share your current skills and preferred domain to get a personalised roadmap.",
  "rag_context": "From ml_roadmap.txt: Python, SQL and statistics form the core foundation...",
  "response_source": "agent_rag_llm",
  "llm_used": true,
  "response_time_ms": 143,
  "rag_citations": [
    {
      "title": "ML Roadmap",
      "source": "ml_roadmap.txt",
      "source_type": "career_path",
      "snippet": "Python, SQL and statistics form the core foundation...",
      "metadata": { "topic": "ml_roadmap", "min_education": "BTech" }
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `reply` | string | The agent (and optionally LLM-enhanced) response |
| `suggested_next_step` | string | Prompt to guide the user's next action |
| `rag_context` | string | Raw retrieved context appended to reply (may be `""`) |
| `response_source` | string | One of: `agent`, `agent_rag`, `agent_rag_llm` |
| `llm_used` | boolean | Whether LLM refinement contributed to final response |
| `response_time_ms` | int | End-to-end route processing time in milliseconds |
| `rag_citations` | object[] | List of source chunks used for retrieval |

---

### `POST /chat/message/me` 🔒

Send a chat message as the authenticated user. User ID is derived from the JWT; the user profile is loaded and updated automatically.

**Request body**
```json
{
  "message": "Suggest me the best career path given my background.",
  "context_owner_type": "self",
  "context": {
    "skills": ["python", "machine learning"],
    "interests": ["nlp", "research"]
  },
  "education_level": "Masters"
}
```

**Response `200`** — same `ChatResponse` shape as above.

---

## 5. Recommendations — `/api/v1/recommendations` 🔒

### `POST /recommendations/generate` 🔒

Generate career recommendations from skills, interests, and education.

**Request body**
```json
{
  "user_id": "",
  "interests": ["data analysis", "visualisation"],
  "skills": ["python", "sql", "tableau"],
  "education_level": "Masters"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `user_id` | string | Overridden with authenticated user's ID |
| `interests` | string[] | |
| `skills` | string[] | |
| `education_level` | string | One of: `PhD`, `Masters`, `Bachelors`, `Other` |

**Response `200`**
```json
{
  "recommendations": [
    {
      "role": "Data Analyst",
      "confidence": 0.87,
      "reason": "Strong SQL, Python, and Tableau skills align with data analyst requirements."
    },
    {
      "role": "Data Scientist",
      "confidence": 0.74,
      "reason": "Python and ML interest align; consider strengthening statistics background."
    }
  ]
}
```

**Notes**
- The `interests` list is enriched with psychometric domain recommendations if the user has a stored psychometric profile.
- Results are sorted by `confidence` descending; maximum 5 roles returned.

---

### `POST /recommendations/explain/me` 🔒

Generate recommendations with SHAP/LIME XAI feature contribution explanations.

**Request body** — same as `generate` (without `user_id`):
```json
{
  "interests": ["data analysis"],
  "skills": ["python", "sql"],
  "education_level": "Masters"
}
```

**Response `200`**
```json
{
  "explanations": [
    {
      "role": "Data Analyst",
      "confidence": 0.87,
      "contributions": [
        { "feature": "skill_match",           "value":  0.3480 },
        { "feature": "interest_match",        "value":  0.1200 },
        { "feature": "education_fit",         "value":  0.1600 },
        { "feature": "personalization_bonus", "value":  0.0500 }
      ],
      "label": "SHAP contribution summary"
    }
  ]
}
```

Feature descriptions:

| Feature | Meaning |
|---------|---------|
| `skill_match` | Fraction of role's required skills the user has |
| `interest_match` | Fraction of role's target domains matching user interests |
| `education_fit` | Ordinal score for education tier fit |
| `personalization_bonus` | Boost from psychometric domain overlap |

---

### `POST /recommendations/feedback/me` 🔒

Submit feedback on a given recommendation.

**Request body**
```json
{
  "role": "Data Scientist",
  "helpful": true,
  "rating": 4,
  "feedback_tags": ["relevant", "clear"]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `role` | string | The role being rated |
| `helpful` | boolean | |
| `rating` | int | 1–5, defaults to 3 |
| `feedback_tags` | string[] | Defaults to `[]` |

**Response `200`**
```json
{
  "user_id": "550e8400-...",
  "message": "Feedback recorded"
}
```

---

### `GET /recommendations/feedback/me` 🔒

Retrieve stored recommendation feedback entries for the authenticated user (newest first).

**Response `200`**
```json
{
  "user_id": "550e8400-...",
  "feedback": [
    {
      "user_id": "550e8400-...",
      "role": "Data Scientist",
      "helpful": false,
      "rating": 2,
      "feedback_tags": ["clarity", "relevance"],
      "created_at": "2026-04-19T11:32:10Z"
    }
  ]
}
```

---

### `GET /recommendations/xai/status` 🔒

Check which XAI method is active at runtime and feature set details.

**Response `200`**
```json
{
  "active_mode": "shap",
  "shap_available": true,
  "lime_available": false,
  "fallback_enabled": true,
  "features": [
    "skills_score",
    "interests_score", 
    "education_score",
    "psychometric_score",
    "cf_score"
  ],
  "notes": "Collaborative filtering (CF) enabled with TruncatedSVD model"
}
```

| Field | Values | Notes |
|-------|--------|-------|
| `active_mode` | `"shap"` \| `"lime"` \| `"fallback"` | SHAP is priority 1, LIME is priority 2 |
| `shap_available` | bool | False if `shap` package not installed |
| `lime_available` | bool | False on Python 3.13+ |
| `fallback_enabled` | bool | Always `true` — deterministic weighted fallback |
| `features` | string[] | 5-feature set: content scores + psychometric + CF (collaborative filtering) |
| `notes` | string | Status of additional modeling features |

---

### `GET /recommendations/history/me` 🔒

Retrieve the authenticated user's recommendation history.

**Response `200`**
```json
{
  "history": [
    {
      "user_id": "550e8400-...",
      "recommendations": [
        { "role": "Data Analyst", "confidence": 0.87, "reason": "..." }
      ],
      "generated_at": "2026-03-15T10:23:44Z"
    }
  ]
}
```

---

### `DELETE /recommendations/history/me` 🔒

Clear the authenticated user's recommendation history.

**Response `200`**
```json
{
  "user_id": "550e8400-...",
  "deleted_count": 3,
  "message": "Recommendation history cleared"
}
```

---

## 6. Psychometric — `/api/v1/psychometric`

### `POST /psychometric/score`

Score psychometric dimensions anonymously.

**Request body**
```json
{
  "dimensions": {
    "investigative": 4,
    "realistic": 3,
    "artistic": 2,
    "social": 4,
    "enterprising": 5,
    "conventional": 3
  }
}
```

Each dimension value should be an integer in the range **1–5**.

**Response `200`**
```json
{
  "normalized_scores": {
    "investigative": 75.0,
    "realistic": 50.0,
    "artistic": 25.0,
    "social": 75.0,
    "enterprising": 100.0,
    "conventional": 50.0
  },
  "top_traits": ["enterprising", "investigative", "social"],
  "recommended_domains": ["Product Management", "Data Science", "Counseling", "AI/ML", "Teaching"]
}
```

Notes:

- `top_traits` is a concise top-3 summary for UI display.
- `recommended_domains` is computed using all provided psychometric dimensions (not only top-3).
- `normalized_scores` are percentage-style values in range 0-100.

---

### `POST /psychometric/score/me` 🔒

Score and **persist** the psychometric profile for the authenticated user.

**Request body** — same as `/score`.

**Response `200`** — same as `/score`. Result is stored in `psychometric_profiles` collection and used to enrich future recommendation requests.

---

### `GET /psychometric/profile/me` 🔒

Retrieve the stored psychometric profile.

**Response `200`** — same shape as score response. Returns empty values if no profile exists:
```json
{ "normalized_scores": {}, "top_traits": [], "recommended_domains": [] }
```

---

## 7. Profile Intake — `/api/v1/profile-intake` 🔒

### `POST /profile-intake/upload` 🔒

Upload text files and extract profile signals (skills, interests, target role, education, psychometric dimensions).

This endpoint uses `multipart/form-data`.

**Form fields**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `files` | file[] | ✓ | Supported extensions are plain-text formats handled by backend parser |
| `owner_type` | string | — | `self` (default) persists to caller profile; `on_behalf` returns extracted data without saving |

**Response `200`**
```json
{
  "owner_type": "self",
  "files_processed": 2,
  "skipped_files": ["resume.pdf"],
  "extracted_profile": {
    "skills": ["python", "sql"],
    "interests": ["data analysis"],
    "target_role": "data scientist",
    "education_level": "Masters",
    "psychometric_dimensions": {
      "investigative": 4,
      "realistic": 3,
      "artistic": 2,
      "social": 4,
      "enterprising": 5,
      "conventional": 3
    }
  },
  "persisted_to_user_profile": true,
  "message": "Profile updated from uploaded files"
}
```

---

## 8. History — `/api/v1/history` 🔒

### `GET /history/me` 🔒

Retrieve the authenticated user's full chat history.

**Response `200`**
```json
{
  "user_id": "550e8400-...",
  "messages": [
    {
      "role": "user",
      "content": "I want to become a data scientist.",
      "timestamp": "2026-03-15T09:00:00Z"
    },
    {
      "role": "assistant",
      "content": "[learning_path] Here is your roadmap...",
      "timestamp": "2026-03-15T09:00:01Z"
    }
  ]
}
```

---

### `DELETE /history/me` 🔒

Clear the authenticated user's chat history.

**Response `200`**
```json
{
  "user_id": "550e8400-...",
  "deleted_count": 12,
  "message": "Chat history cleared"
}
```

---

## 9. Dashboard — `/api/v1/dashboard` 🔒

### `GET /dashboard/summary/me` 🔒

Quick profile completion and next-action summary.

**Response `200`**
```json
{
  "user_id": "550e8400-...",
  "profile_completion": 75,
  "top_roles": ["Data Analyst", "Data Scientist", "ML Engineer"],
  "next_action": "Start learning path for top role"
}
```

| Field | Notes |
|-------|-------|
| `profile_completion` | Computed: `30 + 5×(top_roles_count) + min(40, chat_messages_count)`, capped at 100 |
| `next_action` | `"Generate new recommendations"` if no recommendations yet; otherwise `"Start learning path for top role"` |

---

### `GET /dashboard/report/me` 🔒

Full dashboard report including recent chat and recommendations.

**Response `200`**
```json
{
  "generated_at": "2026-03-15T10:30:00Z",
  "summary": { ... },
  "recent_chat_messages": [ ... ],
  "recommendation_history": [ ... ],
  "latest_recommendations": [
    { "role": "Data Analyst", "confidence": 0.87, "reason": "..." }
  ]
}
```

`recent_chat_messages` — last 10 messages from `chat_history`.  
`recommendation_history` — last 10 recommendation snapshots.  
`latest_recommendations` — top recommendations from the most recent snapshot.

---

## 10. RAG (Knowledge Base) — `/api/v1/rag`

### `GET /rag/status`

Check RAG pipeline status and chunk inventory.

**Response `200`**
```json
{
  "enabled": true,
  "top_k": 4,
  "candidate_pool_size": 20,
  "base_chunks": 180,
  "document_chunks": 0,
  "total_chunks": 180,
  "last_ingested_at": "2026-03-15T08:00:00Z",
  "ingested_files": ["ml_roadmap.txt", "interview_preparation.txt", "..."],
  "skipped_noisy_chunks": 3,
  "skipped_duplicate_chunks": 1
}
```

---

### `POST /rag/ingest`

Ingest knowledge documents from a custom directory path.

**Request body**
```json
{ "directory_path": "/path/to/my/docs" }
```

`directory_path` may be `null` to use the default ingest resolution order:
1) `rag/knowledge/`
2) `one_note_extract/`

**Response `200`**
```json
{
  "target_path": "/path/to/my/docs",
  "ingested_files": ["career_tips.txt"],
  "ingested_chunks": 24,
  "skipped_files": [],
  "skipped_noisy_chunks": 2,
  "skipped_duplicate_chunks": 0
}
```

---

### `POST /rag/ingest/default`

Ingest from default path resolution (`rag/knowledge/` then `one_note_extract/`). No request body needed.

**Response `200`** — same as `/rag/ingest`.

---

### `GET /rag/search`

Semantic search over the knowledge base with optional metadata filters.

**Query parameters**

| Parameter | Type | Required | Example |
|-----------|------|----------|---------|
| `query` | string | ✓ (min 2 chars) | `machine learning roadmap` |
| `source_type` | string | — | `career_path` |
| `topic` | string | — | `ml_engineer` |
| `min_education` | string | — | `BTech` |
| `intent` | string | — | `interview_prep` |
| `target_role` | string | — | `ml engineer` |

**Response `200`**
```json
{
  "query": "machine learning roadmap",
  "results": [
    {
      "title": "ML Engineer Path",
      "source": "ml_engineer_path.txt",
      "source_type": "career_path",
      "snippet": "Start with Python and linear algebra. Build 2 end-to-end projects...",
      "metadata": { "topic": "ml_engineer", "min_education": "BTech" }
    }
  ]
}
```

---

### `POST /rag/evaluate`

Evaluate retrieval quality for a query against expected terms/sources.

**Request body**
```json
{
  "query": "ml engineer interview prep",
  "top_k": 4,
  "expected_terms": ["interview", "practice"],
  "expected_source_contains": ["interview"],
  "metadata_filters": {"topic": "interview"},
  "intent": "interview_prep",
  "target_role": "ml engineer",
  "skill_gaps": ["system design"]
}
```

**Response `200`**
```json
{
  "query": "ml engineer interview prep",
  "retrieved_count": 4,
  "term_coverage": 1.0,
  "source_recall_at_k": 1.0,
  "matched_terms": ["interview", "practice"],
  "matched_sources": ["interview_preparation"],
  "results": [
    {
      "title": "Interview Preparation",
      "source": "rag/knowledge/interview_preparation.txt",
      "source_type": "document",
      "snippet": "Practice role-specific interview loops...",
      "metadata": {"topic": "interview", "role": "ml engineer"}
    }
  ]
}
```

---

### `GET /rag/telemetry`

Return per-user aggregate retrieval telemetry from assistant message metadata.

**Query parameters**

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `user_id` | string | — | `frontend-session-user` |
| `limit` | int | — | `100` |

---

### `GET /rag/telemetry/trends`

Return windowed aggregate buckets (for example last 10/50/100 turns).

**Query parameters**

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `user_id` | string | — | `frontend-session-user` |
| `windows` | csv string | — | `10,50,100` |
| `limit` | int | — | auto (max window) |

---

### `GET /rag/telemetry/trends/series`

Return frontend-ready chart series payload (`labels`, aligned metric arrays).

---

### `GET /rag/telemetry/trends/combined`

Return both bucket windows and series arrays in one response.

---

### Authenticated telemetry variants

These endpoints are also available in authenticated `.../me` form:

- `GET /rag/telemetry/me`
- `GET /rag/telemetry/trends/me`
- `GET /rag/telemetry/trends/series/me`
- `GET /rag/telemetry/trends/combined/me`

---

## 11. Market Data — `/api/v1/market`

### `GET /market/jobs`

Fetch remote job listings via async HTTP calls with a short in-memory TTL cache and graceful fallback.

**Query parameters**

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `search` | string | — | `"data"` | Job search keyword |
| `limit` | int | — | `10` | Max results to return (clamped to 1..50) |

**Response `200`**
```json
{
  "source": "remotive",
  "query": "data",
  "results": [
    {
      "job_title": "Senior Data Engineer",
      "company": "Acme Corp",
      "location": "Remote",
      "category": "Data",
      "url": "https://remotive.com/...",
      "published_at": "2026-03-14"
    }
  ]
}
```

`source` is `"remotive"` when live API data is returned and `"fallback"` when deterministic sample jobs are used.

---

## 12. LLM Runtime — `/api/v1/llm`

### `GET /llm/status`

Inspect effective LLM runtime configuration for provider, model selection, and runtime overrides.

**Response `200`**
```json
{
  "enabled": true,
  "require_rag_context": true,
  "provider": "ollama",
  "base_url": "http://localhost:11434",
  "base_model": "tinyllama:latest",
  "finetuned_model": "tinyllama:finetuned",
  "active_model": "tinyllama:finetuned",
  "is_finetuned_active": true,
  "request_timeout_seconds": 15,
  "ollama_num_predict": 128,
  "rag_context_max_chars": 1400,
  "chat_reply_max_sentences": 8,
  "auto_fallback_to_openai": true,
  "openai_base_url": "https://api.openai.com/v1",
  "openai_model": "gpt-4o-mini",
  "openai_max_tokens": 260,
  "openai_api_key_configured": false,
  "groq_model": "llama-3.1-8b-instant",
  "groq_max_tokens": 512,
  "groq_api_key_configured": false,
  "runtime_override_active": false
}
```

| Field | Notes |
|-------|-------|
| `provider` | `ollama`, `openai`, or `groq` |
| `active_model` | Provider-aware resolved model used for calls |
| `is_finetuned_active` | True only when provider is `ollama` and `finetuned_model` is set |
| `runtime_override_active` | True when runtime config has in-memory overrides via `/llm/config` |

### `POST /llm/config`

Update LLM runtime configuration at runtime (no restart required).

**Request body**
```json
{
  "enabled": true,
  "provider": "groq",
  "request_timeout_seconds": 20,
  "rag_context_max_chars": 1200,
  "chat_reply_max_sentences": 8,
  "openai_model": "gpt-4o-mini",
  "openai_max_tokens": 260,
  "groq_model": "llama-3.1-8b-instant",
  "groq_max_tokens": 512
}
```

Validation notes:
- Unsupported providers/models return `422`.
- Numeric fields are clamped to safe ranges (`request_timeout_seconds`, `ollama_num_predict`, `openai_max_tokens`, `groq_max_tokens`, `chat_reply_max_sentences`).

**Response `200`** — same as `/llm/status`.

### `POST /llm/config/reset`

Reset LLM config to environment defaults.

**Response `200`** — same as `/llm/status`.

---

## 13. MLOps & Modeling — `/api/v1/modeling`

### `GET /modeling/status`

Inspect MLOps models, explainability, and feature gates. No authentication required.

**Response `200`**
```json
{
  "intent_model": {
    "enabled": false,
    "status": "pending_training",
    "artifact_dir": "ml-models/pretrained/intent_model",
    "model_exists": false
  },
  "cf_model": {
    "enabled": true,
    "status": "active",
    "artifact_dir": "ml-models/pretrained/cf_model",
    "artifact_exists": true,
    "algorithm": "TruncatedSVD",
    "blend_alpha": 0.25
  },
  "bandit": {
    "enabled": true,
    "status": "active",
    "policy_path": "ml-models/pretrained/bandit/policy.json",
    "policy_exists": true,
    "epsilon": 0.1,
    "algorithm": "epsilon_greedy"
  },
  "safety_filter": {
    "enabled": true,
    "status": "active",
    "layers": ["harmful_content_block", "off_topic_redirect", "repetition_guard"]
  },
  "explainability": {
    "active_mode": "shap",
    "shap_available": true,
    "lime_available": false,
    "fallback_enabled": true,
    "features": ["skills_score", "interests_score", "education_score", "psychometric_score", "cf_score"]
  },
  "fine_tuning": {
    "infrastructure_ready": true,
    "dataset_path": "ml-models/datasets/tinyllama_sft_generated.jsonl",
    "dataset_examples": 73,
    "training_script": "ml-models/training/train_tinyllama_cpu.py",
    "status": "infrastructure_complete_awaiting_execution"
  }
}
```

**Key Features:**

| Feature | Status | Details |
|---------|--------|----------|
| **Collaborative Filtering** | ✅ Full | TruncatedSVD trained on user-item interactions; blends score with content-based |
| **Bandit Adaptation** | ✅ Full | Epsilon-greedy policy learns from feedback (helpful + rating); reranks top-K |
| **Safety Filter** | ✅ Full | 3-layer: blocks harmful → redirects off-topic → prevents repetition |
| **Explainability (XAI)** |  ✅ Full | SHAP/LIME over 5-feature set; deterministic fallback always available |
| **Fine-Tuning Infrastructure** | ✅ Ready | QLoRA trainer, dataset (73 examples from knowledge base), evaluation pipeline |
| **Drift Detection** | ✅ Full | KS test on query patterns; outputs drift_report.json; CI-friendly |
| **Intent Classifier** | 🔲 Pending | BERT/DistilBERT training framework staged for phase 2 |

**Training Artifact Paths:**
- CF: `ml-models/pretrained/cf_model/cf_model.pkl`
- Bandit: `ml-models/pretrained/bandit/policy.json`
- Fine-tuned TinyLlama: Merge into Ollama custom model or set `LLM_FINETUNED_MODEL` env var

Training commands to produce artifacts for each model:

```bash
# Intent classifier (TF-IDF + LogReg)
python ml-models/training/train_intent_classifier.py \
  --dataset ml-models/datasets/intent_queries.csv \
  --output-dir ml-models/pretrained/intent_model

# User preference model (XGBoost / RF fallback)
python ml-models/training/build_user_features.py \
  --dataset ml-models/datasets/user_feedback_events.jsonl
python ml-models/training/train_user_preference_xgb.py \
  --dataset ml-models/datasets/user_features.csv \
  --output-dir ml-models/pretrained/user_modeling

# CF hybrid recommender (TruncatedSVD)
python ml-models/training/train_cf_recommender.py \
  --dataset ml-models/datasets/user_feedback_events.jsonl \
  --output-dir ml-models/pretrained/cf_model

# Psychometric domain predictor (RandomForest)
python ml-models/training/train_psychometric_model.py \
  --output-dir ml-models/pretrained/psychometric_model
```

Enable each model by setting the corresponding flag in `.env`:

```
INTENT_MODEL_ENABLED=true
USER_PREFERENCE_MODEL_ENABLED=true
CF_MODEL_ENABLED=true
PSYCHOMETRIC_MODEL_ENABLED=true
BANDIT_ENABLED=true
```

---

## 14. Error Response Reference

All errors use the standard FastAPI error body:

```json
{ "detail": "<human-readable message>" }
```

| HTTP Status | Common causes |
|-------------|--------------|
| 400 Bad Request | Pydantic validation failure on request body or query params |
| 401 Unauthorized | Missing/expired JWT; invalid login credentials |
| 403 Forbidden | Valid JWT but accessing another user's resource |
| 404 Not Found | Route does not exist |
| 409 Conflict | Email already registered |
| 422 Unprocessable Entity | Pydantic schema mismatch (wrong field types) |
| 503 Service Unavailable | PostgreSQL unavailable |

---

## 15. Intent Reference

The `reply` field in chat responses is prefixed with the detected intent name when stored in history. The following intent names may appear:

| Intent name | Triggered by |
|-------------|-------------|
| `career_assessment` | Fallback; low-confidence or general messages |
| `interview_prep` | "interview", "mock", "hr round", "technical round" |
| `learning_path` | "learn", "roadmap", "course", "upskill", "study plan" |
| `recommendation` | "recommend", "suggest", "best role", "career option" |
| `job_matching` | "job", "role", "match", "fit", "eligibility" |
| `networking` | "network", "linkedin", "referral", "mentor", "outreach" |
| `feedback` | "feedback", "rate", "rating", "helpful", "not helpful" |
