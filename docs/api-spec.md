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
    "openness": 4,
    "conscientiousness": 5,
    "extraversion": 3,
    "agreeableness": 4,
    "neuroticism": 2
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
| `psychometric_dimensions` | object | — | Optional Big Five-style numeric map |

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

### `GET /recommendations/xai/status` 🔒

Check which XAI method is active at runtime.

**Response `200`**
```json
{
  "active_mode": "shap",
  "shap_available": true,
  "lime_available": false,
  "fallback_enabled": true,
  "user_id": "550e8400-..."
}
```

| Field | Values | Notes |
|-------|--------|-------|
| `active_mode` | `"shap"` \| `"lime"` \| `"fallback"` | |
| `shap_available` | bool | False if import fails |
| `lime_available` | bool | False on Python 3.13+ |
| `fallback_enabled` | bool | Always `true` |

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
    "openness": 4,
    "conscientiousness": 5,
    "extraversion": 3,
    "agreeableness": 4,
    "neuroticism": 2
  }
}
```

Each dimension value should be an integer in the range **1–5**.

**Response `200`**
```json
{
  "normalized_scores": {
    "openness": 0.82,
    "conscientiousness": 0.95,
    "extraversion": 0.60,
    "agreeableness": 0.78,
    "neuroticism": 0.35
  },
  "top_traits": ["conscientiousness", "openness"],
  "recommended_domains": ["research", "data science", "machine learning"]
}
```

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
      "openness": 4,
      "conscientiousness": 5,
      "extraversion": 3,
      "agreeableness": 4,
      "neuroticism": 2
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

`directory_path` may be `null` to use the default `one_note_extract/` directory.

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

Ingest from the default `one_note_extract/` directory. No request body needed.

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

## 11. Market Data — `/api/v1/market`

### `GET /market/jobs`

Fetch live remote job listings from the Remotive API.

**Query parameters**

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `search` | string | — | `"data"` | Job search keyword |
| `limit` | int | — | `10` | Max results to return |

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

---

## 12. LLM Status — `/api/v1/llm`

### `GET /llm/status`

Inspect LLM runtime configuration.

**Response `200`**
```json
{
  "enabled": true,
  "require_rag_context": true,
  "provider": "ollama",
  "base_url": "http://localhost:11434",
  "base_model": "tinyllama:latest",
  "finetuned_model": "",
  "active_model": "tinyllama:latest",
  "is_finetuned_active": false
}
```

---

## 13. Modeling Status — `/api/v1/modeling`

### `GET /modeling/status`

Inspect which phase-2 ML models are enabled and whether their artifact files are present on disk.  No authentication required.

**Response `200`**
```json
{
  "intent_model": {
    "enabled": false,
    "artifact_dir": "ml-models/pretrained/intent_model",
    "model_exists": false,
    "labels_exists": false,
    "min_confidence": 0.5
  },
  "user_preference_model": {
    "enabled": false,
    "artifact_path": "ml-models/pretrained/user_modeling/user_preference_model.pkl",
    "artifact_exists": false,
    "blend_alpha": 0.35
  },
  "psychometric_model": {
    "enabled": false,
    "artifact_path": "ml-models/pretrained/psychometric_model/psychometric_model.pkl",
    "artifact_exists": false
  },
  "cf_model": {
    "enabled": false,
    "artifact_dir": "ml-models/pretrained/cf_model",
    "artifact_exists": false,
    "blend_alpha": 0.25
  },
  "bandit": {
    "enabled": false,
    "artifact_dir": "ml-models/pretrained/bandit",
    "state_exists": false,
    "epsilon": 0.1
  }
}
```

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
