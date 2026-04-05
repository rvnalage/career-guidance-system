# Career Guidance System — Design Document

## 1. Design Goals

| Goal | Rationale |
|------|-----------|
| **Accuracy first** | Career advice errors have real-world consequences; every response must be grounded in retrieved knowledge. |
| **Transparency** | SHAP/LIME XAI makes recommendation scoring human-readable, not a black box. |
| **Graceful degradation** | System remains functional when LLM, LIME, or external APIs are unavailable. |
| **Stateful personalisation** | Multi-turn context via user profile memory improves advice quality over repeated sessions. |
| **Testability** | All decision logic is in service/agent classes, not in route handlers, enabling unit testing without HTTP. |

---

## 2. Core Design Patterns

### 2.1 Agent Pattern (Strategy + Registry)

The agent layer implements the **Strategy pattern**: each intent maps to an interchangeable strategy object (`BaseAgent`). A single `AGENT_REGISTRY` dict dispatches at runtime.

```python
# BaseAgent contract
class BaseAgent(ABC):
    @abstractmethod
    def respond(self, message: str, context: dict | None) -> str: ...
    @abstractmethod
    def suggested_next_step(self, message: str, context: dict | None) -> str: ...
```

Adding a new intent requires three steps total:
1. Create a new `XxxAgent(BaseAgent)` class.
2. Register it in `AGENT_REGISTRY` in `agent_service.py`.
3. Add keywords to `INTENT_KEYWORDS` in `intent_recognizer.py`.

### 2.2 Confidence-Gated Routing

Intent routing includes a confidence floor (`INTENT_MIN_CONFIDENCE = 0.35`). Messages that produce low keyword coverage fall back to `career_assessment` rather than choosing a poorly-matched specialised agent. This prevents the system from confidently giving job-matching advice to a message like "what should I do next?".

```
detect_intent_with_confidence(message)
  →  (intent, score, matched_keywords)
       if score < 0.35  →  override intent = "career_assessment"
```

### 2.3 RAG-Grounded LLM Prompting

When the LLM is enabled, it is constrained by three mechanisms:
- **Prompt grounding**: The LLM system prompt explicitly forbids inventing jobs, certifications, universities, salaries, or timelines.
- **`LLM_REQUIRE_RAG_CONTEXT`**: When `true`, the LLM is instructed to not add claims beyond the retrieved chunks.
- **Fallback behaviour**: If LLM returns `None` or fails (timeout, Ollama unavailable), the agent's rule-based reply is used directly without surfacing an error to the user.

### 2.4 XAI Waterfall

The explainability layer tries three methods in order of fidelity:

| Priority | Method | Condition |
|----------|--------|-----------|
| 1 | SHAP `KernelExplainer` | `shap` importable |
| 2 | LIME `LimeTabularExplainer` | `lime` importable |
| 3 | Weighted dot product | Always available |

All three produce the same output shape: `list[tuple[str, float]]` — one (feature, contribution) pair per feature. This means downstream consumers (`recommendation_service`, the API response schema) do not need to know which method was used.

### 2.5 Profile Memory Design

User profiles are stored in MongoDB `user_profiles` and serve as working memory across chat sessions. The design merges rather than replaces:

- **Skills**: union of known skills from `SKILL_BANK` found in new messages + existing skills in profile.
- **Interests**: union of free-text interests extracted from context + existing.
- **Target role**: extracted from message or context using a role-hint dictionary; newer signal wins.
- **Intent counts**: `dict[intent_name, count]` — tracks usage patterns without storing raw messages.

The in-memory fallback dict (`_profile_fallback`) ensures profile operations never raise an exception when MongoDB is unavailable (e.g., during unit tests).

### 2.6 Per-Intent LLM Prompting

Rather than a single generic prompt, the LLM receives intent-specific guidance and runtime context:

| What | Purpose |
|------|---------|
| `INTENT_PROMPT_GUIDANCE[intent]` | Shapes the format and focus (e.g., phased roadmap for `learning_path`) |
| `intent_confidence` | Lets the LLM weight its response when routing confidence was borderline |
| `keyword_matches` | Exposes matched routing keywords to keep LLM phrasing aligned with classifier signal |
| `user_profile_summary` | Single-line compact profile recap injected into context window |

Implementation note:
- `LLM_REQUIRE_RAG_CONTEXT=true` prevents LLM calls when retrieval returns no context.
- The LLM acts as a post-processor over agent output, and route handlers always fall back safely to deterministic agent responses.

---

## 3. Data Model Design

### 3.1 PostgreSQL — User Table

The User model is minimal by design; it stores only durable, structured identity data. Transient and semi-structured data (skills, interests in their richer form) lives in MongoDB `user_profiles`.

```
users
├── id           VARCHAR(36)   UUID (e.g., Python uuid4())
├── full_name    VARCHAR(120)
├── email        VARCHAR(255)  UNIQUE  INDEX
├── hashed_password VARCHAR(255)  bcrypt
├── interests    VARCHAR(500)  comma-separated seed values (from registration)
└── target_roles VARCHAR(500)  comma-separated seed values (from registration)
```

### 3.2 MongoDB Document Schemas

#### chat_history

```json
{
  "_id": "<ObjectId>",
  "user_id": "<uuid>",
  "role": "user | assistant",
  "content": "<message text>",
  "timestamp": "<ISO-8601>"
}
```

#### recommendation_history

```json
{
  "_id": "<ObjectId>",
  "user_id": "<uuid>",
  "generated_at": "<ISO-8601>",
  "recommendations": [
    { "role": "Data Scientist", "confidence": 0.87, "reason": "..." }
  ]
}
```

#### recommendation_feedback

```json
{
  "_id": "<ObjectId>",
  "user_id": "<uuid>",
  "role": "Data Scientist",
  "helpful": true,
  "rating": 4,
  "feedback_tags": ["relevant", "clear"],
  "recorded_at": "<ISO-8601>"
}
```

#### psychometric_profiles

```json
{
  "_id": "<ObjectId>",
  "user_id": "<uuid>",
  "normalized_scores": { "openness": 0.82, "conscientiousness": 0.74, ... },
  "top_traits": ["openness", "conscientiousness"],
  "recommended_domains": ["data science", "research"],
  "updated_at": "<ISO-8601>"
}
```

#### user_profiles

```json
{
  "_id": "<ObjectId>",
  "user_id": "<uuid>",
  "skills": ["python", "sql", "machine learning"],
  "interests": ["data analysis", "ai"],
  "target_role": "data scientist",
  "intent_counts": { "learning_path": 3, "recommendation": 1 },
  "updated_at": "<ISO-8601>"
}
```

---

## 4. Recommendation Engine Design

### 4.1 Scoring Model

Recommendations are scored with a linear confidence model over four features:

| Feature | Source | Weight (default) |
|---------|--------|-----------------|
| `skill_match` | `len(user_skills ∩ role_skills) / len(role_skills)` | 0.50 (profile-adjustable) |
| `interest_match` | `len(user_interests ∩ role_domains) / len(role_domains)` | 0.30 (profile-adjustable) |
| `education_fit` | Tiered fit score derived from user and role minimum education | 0.20 (profile-adjustable) |
| `personalization_bonus` | Role-specific feedback bonus learned from user rating/helpful signals | [-0.20, +0.20] additive |

`confidence = sum(feature_value × weight) + personalization_bonus`, clamped to `[0.0, 1.0]`.

Results are sorted by confidence descending; API currently returns top 3 recommendations by default.

### 4.2 Role Knowledge Base

The system contains an internal role catalogue mapping each career to required skills, related domains, and minimum education tier. Roles covered: Data Scientist, Data Analyst, Data Engineer, ML Engineer, Backend Developer, DevOps Engineer, UI/UX Designer, Product Analyst, Research Scientist.

### 4.3 Psychometric Enrichment

When a user submits `POST /psychometric/score/me`, their `recommended_domains` are stored in `psychometric_profiles`. Before generating recommendations, `_enrich_interests_with_psychometric` merges these domains into the request's `interests` list. This influences `interest_match` indirectly (there is no direct psychometric numeric feature in scoring).

---

## 5. RAG Pipeline Design

### 5.1 Ingestion

Document ingestion reads `.txt` files from `career-guidance-system/rag/knowledge/` (consolidated knowledge base) or a caller-supplied directory path. Each file is split into overlapping chunks. Each ingested chunk currently uses:
- `source_type`: `document`
- `metadata.topic`: `document`
- `metadata.file_name`: source filename
- `metadata.chunk_index`: chunk position within file

The default knowledge base contains 16 curated career guidance documents:
- Career paths (Backend, ML Engineer, Data Analyst, Data Engineer, DevOps, Product Analyst, UI/UX, Research)
- Guidance topics (Interview Prep, Portfolio, Resume Guidelines, Career Framework, Placement Strategy, Soft Skills)
- Special content (ML Roadmap, Higher Studies vs Job decision guide)

Quality filters:
- chunks with normalized length < 80 are dropped
- chunks with alphanumeric ratio < 0.65 are dropped
- near-duplicate chunks are skipped using a token fingerprint

### 5.2 Vector Store

`InMemoryVectorStore` uses **TF-IDF vectorisation** with cosine similarity. Chosen deliberately:
- No GPU or external embedding service required.
- Sufficient for the domain corpus size (~200–500 chunks).
- Deterministic — same query always returns same ranked results.

For production scale, this can be swapped out for a persistent vector DB (e.g., Qdrant, Weaviate) behind the same `VectorStore` interface.

### 5.3 Retrieval and Re-ranking

Two-phase retrieval:
1. **Vector pass**: retrieve `candidate_pool_size` (default 20) candidates by cosine similarity.
2. **Re-rank**: combine vector score + lexical overlap score (0.1 per token match) + metadata overlap score (0.15 per metadata token match).

Optional metadata filters (`source_type`, `topic`, `min_education`) are applied when provided by API callers. The system can also infer coarse filters from query text (for example, interview/learning hints).

Return top `RAG_TOP_K` (default 4) after re-ranking.

### 5.4 Query Rewriting

Before retrieval, queries are rewritten using deterministic synonym replacement (for example, `ml → machine learning`, `mtech → master`, `cv → portfolio`, `job prep → interview preparation`). This improves recall for informal student queries while keeping retrieval behavior predictable.

---

## 5.5 LLM Response Refinement & Fine-Tuning

The system supports optional LLM-based response refinement using TinyLlama 1.1B (local via Ollama):

**Gating**: LLM is only invoked when:
- `LLM_ENABLED=true`
- `LLM_REQUIRE_RAG_CONTEXT=true` AND RAG retrieval returns context
- This prevents hallucinations by ensuring LLM always receives grounded knowledge

**Fine-Tuning Infrastructure** (available for optimization):
- **Dataset generation**: `ml-models/training/prepare_tinyllama_dataset.py` converts 16 knowledge base documents → 73 JSONL training examples
- **QLoRA trainer**: `ml-models/training/train_tinyllama_cpu.py` implements parameter-efficient fine-tuning (batch size 1, gradient accumulation 4)
- **Orchestration**: `scripts/run_tinyllama_finetuning.ps1` stages prepare → train → evaluate
- **Training time**: 1-2 hours per epoch on CPU (no GPU required)
- **Deployment**: Fine-tuned adapter can be loaded via `LLM_FINETUNED_MODEL` env var or exported as Ollama custom model

See [RAG + LLM Integration](rag-llm-integration.md) for code-level flow: user message → RAG retrieval → prompt injection → LLM call → response.

---

## 6. Authentication and Session Design

### 6.1 Token Lifecycle

```
POST /api/v1/auth/register  →  user created, no token
POST /api/v1/auth/login     →  JWT issued (exp = now + 60 min)
All /me endpoints            →  Bearer <token> required in Authorization header
Token expires               →  client must re-login
```

### 6.2 JWT Claims

```json
{ "sub": "<user_id_uuid>", "exp": <unix_timestamp> }
```

`get_current_user` dependency: decodes token → looks up user in PostgreSQL → raises 401 if not found or expired.

### 6.3 Open vs Protected Endpoints

Endpoints with `/me` suffix always require authentication. Some endpoints without `/me` are still protected by design (notably `POST /profile-intake/upload`). Anonymous endpoints such as `POST /chat/message`, `GET /market/jobs`, RAG read/admin endpoints, and `POST /psychometric/score` allow exploration without an account.

---

## 7. Error Handling Strategy

| Scenario | HTTP Status | Handling |
|----------|-------------|---------|
| Email already registered | 409 Conflict | `user_service.create_user` detects duplicate |
| Invalid login credentials | 401 Unauthorized | `authenticate_user` returns None |
| PostgreSQL unavailable | 503 Service Unavailable | `SQLAlchemyError` caught in auth routes |
| Expired / invalid JWT | 401 Unauthorized | FastAPI `HTTPBearer` dependency |
| MongoDB unavailable | Graceful degradation | `_profile_fallback` dict used; no 500 raised |
| LLM unavailable / timeout | Graceful degradation | `generate_llm_reply` returns `None`; agent reply used |
| External job API failure | Graceful degradation | `market_service` returns deterministic fallback jobs with `source="fallback"` |
| RAG store empty | Returns empty citations | `rag_service` returns `""` / `[]` safely |

---

## 8. Extensibility Points

| Extension | Where to add |
|-----------|-------------|
| New career intent | `INTENT_KEYWORDS` + new `Agent` class + `AGENT_REGISTRY` entry |
| New LLM provider | `llm_service.py` — add branch in `generate_llm_reply` for `settings.llm_provider` |
| Persistent vector DB | Replace `InMemoryVectorStore` with adapter implementing same interface |
| Redis caching | `redis_url` already in config; add cache layer in service functions |
| Profile memory TTL | `profile_service.get_user_profile` — add `updated_at + ttl_days < now` purge |
| Webhook / notifications | New route module + service; no core changes needed |
| New psychometric model | `psychometric_service.score_psychometric` — swap scoring logic; schema unchanged |
