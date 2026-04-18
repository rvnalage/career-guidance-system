# Career Guidance System — Testing Strategy

## 1. Testing Philosophy

| Principle | Application |
|-----------|-------------|
| **Test behaviour, not implementation** | Tests assert on HTTP status codes, response fields, and logical outcomes — not internal data structures. |
| **Isolated unit tests for logic** | NLP, XAI, agent, and service layer tests use no HTTP client and no live databases. |
| **Integration tests for routes** | Route tests use FastAPI `TestClient` with dependency overrides for auth; databases (MongoDB, PostgreSQL) are bypassed. |
| **Graceful-degradation coverage** | Every optional external dependency (LLM, LIME, MongoDB) has a test proving the system works when it is unavailable. |
| **No test should depend on another** | Tests must be fully independent; they share only the `client` pytest fixture. |

---

## 2. Test Stack

| Tool | Version | Role |
|------|---------|------|
| `pytest` | ≥7.x | Test runner and fixture system |
| `httpx` | **0.27.2** (pinned) | HTTP transport for FastAPI `TestClient` |
| `starlette.testclient.TestClient` | — | Sync test client wrapping the ASGI app |
| `pytest-asyncio` | — | For any future async test helpers |
| `unittest.mock` | stdlib | Patching external calls (Ollama, Remotive, MongoDB) |

> ⚠️ **httpx pinning requirement**: `httpx ≥0.28.0` removed the `app` keyword argument from its `Client`, breaking `starlette.testclient.TestClient`. Always keep `httpx==0.27.2` in `requirements.txt`.

---

## 3. Test Suite Layout

```
backend/tests/
├── conftest.py              # Shared fixtures (TestClient)
├── test_integration.py      # System smoke tests (health, root, cross-cutting)
├── test_auth.py             # Auth guard coverage for all protected endpoints
├── test_chat.py             # Chat route intent-to-reply pipeline
├── test_agents.py           # Agent dispatch, intent routing, confidence scoring
├── test_ml.py               # Recommendation engine (scoring logic, CF blending, sort order)
├── test_rag.py              # RAG status, ingest, search pipeline
├── test_xai_explanations.py # XAI explainer (SHAP/LIME/fallback) over 5-feature set
├── test_recommendations.py  # Recommendation generation, feedback, bandit reranking
├── test_llm_integration.py  # LLM config endpoints, safety filter behavior
├── test_profile_intake.py   # Upload parsing and profile-intake endpoint behavior
├── test_profile_service.py  # Profile merge and summarize (no I/O)
├── test_modeling_status.py  # MLOps endpoint reports CF/Bandit/Safety/Drift/Fine-tuning status
├── test_drift_detection.py  # Drift detector (KS test, baseline generation, CI exit codes)
└── test_nlp.py              # (placeholder — NLP edge cases can be added here)
```

---

## 4. Fixtures

### 4.1 `client` (conftest.py)

```python
@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

The `TestClient` starts the full FastAPI app. MongoDB and PostgreSQL calls inside the app will fail gracefully due to the system's built-in degradation handling (no exceptions leak to the test).

### 4.2 Auth Override Pattern

Protected endpoints are tested using FastAPI's `dependency_overrides` mechanism. This replaces the JWT decoding dependency with a function that returns a hardcoded `User` object.

```python
def _auth_override_user() -> User:
    return User(
        id="test-user-1",
        full_name="Test Student",
        email="test@example.com",
        hashed_password="hashed",
        interests="ai,data",
        target_roles="machine learning engineer",
    )

# Usage in a test:
client.app.dependency_overrides[get_current_user] = _auth_override_user
try:
    response = client.post(...)
    # assertions
finally:
    client.app.dependency_overrides.clear()
```

**Critical**: Always call `dependency_overrides.clear()` in a `finally` block to prevent override leakage between tests.

### 4.3 `--noconftest` Flag (Legacy)

During early development when `fastapi` was not installed in the test environment, tests in isolated modules were run with:

```
py -m pytest tests/test_agents.py --noconftest -q
```

This flag is no longer needed when all dependencies from `requirements.txt` are installed.

---

## 5. Test Categories and Coverage

### 5.1 Integration / Smoke Tests (`test_integration.py`)

These tests verify that all major route groups are mounted and return expected shapes. They do not assert detailed content — only that the pipeline end-to-end is wired correctly.

| Test | Endpoint | Asserts |
|------|----------|---------|
| `test_root_endpoint` | `GET /` | 200, `message` field present |
| `test_health_endpoint` | `GET /health` | 200, `{"status": "ok"}` |
| `test_chat_route_is_mounted` | `POST /api/v1/chat/message` | 200, `reply` field present |
| `test_market_jobs_endpoint` | `GET /api/v1/market/jobs` | 200, `source` and `results` present |
| `test_llm_status_endpoint` | `GET /api/v1/llm/status` | 200, `enabled`, `provider`, `active_model` present |
| `test_psychometric_scoring_endpoint` | `POST /api/v1/psychometric/score` | 200, `normalized_scores`, `top_traits`, `recommended_domains` present |

### 5.2 Auth Guard Tests (`test_auth.py`)

Every endpoint that requires a JWT is tested in the unauthenticated state. These tests confirm that no protected endpoint can be accessed without a valid token.

| Endpoint | Expected status without token |
|----------|------------------------------|
| `GET /api/v1/history/me` | 401 |
| `DELETE /api/v1/history/me` | 401 |
| `GET /api/v1/dashboard/summary/me` | 401 |
| `GET /api/v1/dashboard/report/me` | 401 |
| `GET /api/v1/recommendations/history/me` | 401 |
| `POST /api/v1/recommendations/feedback/me` | 401 |
| `POST /api/v1/recommendations/explain/me` | 401 |
| `GET /api/v1/recommendations/xai/status` | 401 |
| `DELETE /api/v1/recommendations/history/me` | 401 |
| `POST /api/v1/recommendations/generate` | 401 |

Additionally, a set of **with-auth** tests uses `dependency_overrides` to verify that authenticated requests succeed and return correct shapes.

### 5.3 Chat Route Tests (`test_chat.py`)

Tests exercise the full message pipeline: intent detection → agent dispatch → RAG retrieval → response.

| Test | Input message | Key assertions |
|------|--------------|----------------|
| `test_chat_route_learning_intent` | "learning roadmap for data science" | Reply contains "roadmap" or "skill"; `rag_citations` list non-empty |
| `test_chat_route_interview_intent` | "prepare for technical interview" | Reply contains "interview"; `suggested_next_step` references "role" or "track" |
| `test_chat_message_me_requires_auth` | (no token) | 401 |
| `test_chat_message_me_with_auth` | "Help with interview prep" (with override) | 200, `reply` and `suggested_next_step` present |

**RAG citation contract**: Every chat response that triggers RAG must return at least one citation with `title`, `source`, `source_type`, and `snippet` fields.

### 5.4 Agent and Intent Tests (`test_agents.py`)

These tests call service layer functions directly — no HTTP overhead.

| Test | Input | Expected intent | Additional assertions |
|------|-------|----------------|----------------------|
| `test_agent_service_selects_networking_agent` | "I need linkedin networking strategy" | `networking` | Reply contains "linkedin" or "network" |
| `test_agent_service_defaults_to_career_assessment` | "I am confused about my future" | `career_assessment` | next_step contains "assessment" |
| `test_agent_service_learning_path_uses_timeline_signal` | "roadmap for data science in 6 weeks" | `learning_path` | Reply contains "6 weeks" |
| `test_agent_service_job_matching_uses_context_skills` | "Need role matching" + context with skills | `job_matching` | Reply references "data engineer" and "readiness" |
| `test_agent_service_selects_recommendation_agent` | "recommend best role for my profile" | `recommendation` | Reply contains "recommend", next_step references "skills" |
| `test_agent_service_selects_feedback_agent` | "I want to give feedback and rating" | `feedback` | Reply contains "feedback", next_step references "rating" |
| `test_detect_intent_with_confidence_returns_matches` | "please recommend best role" | `recommendation` | `confidence > 0.35`, `len(matches) >= 1` |
| `test_low_signal_message_falls_back_to_career_assessment` | "hmm" | `career_assessment` | Confidence gate enforced |

### 5.5 Recommendation Engine Tests (`test_ml.py`)

Service layer unit tests — no HTTP, no database.

| Test | Input profile | Expected outcome |
|------|--------------|-----------------|
| `test_generate_career_recommendations_returns_top_three` | AI/Data Science skills, master's | Top role = "Machine Learning Engineer" |
| `test_recommendation_confidence_sorted_descending` | Design skills + Figma | Top role = "UI/UX Designer"; sorted by confidence |

**Coverage gaps to add**:
- Edge case: empty skills list
- Edge case: education_level = "Other"
- Psychometric enrichment integration: verify `personalization_bonus > 0` when domains overlap

### 5.6 RAG Pipeline Tests (`test_rag.py`)

| Test | Description |
|------|-------------|
| `test_rag_status_endpoint` | `GET /rag/status` returns `enabled` and `total_chunks` |
| `test_rag_ingest_and_search_endpoint` | Creates temp `.txt` file → ingests → searches; verifies at least 1 chunk found and returned |

**Coverage gaps to add**:
- Metadata filter search (`source_type`, `topic`)
- Default ingest from `one_note_extract/` at startup
- Noisy chunk filtering (chunks < 50 chars discarded)
- Duplicate chunk deduplication

### 5.7 XAI Explanation Tests (`test_xai_explanations.py`)

Direct unit tests of the `explain_recommendation` function — no HTTP, no database.

| Test | Input | Assertions |
|------|-------|-----------|
| `test_explain_recommendation_returns_expected_shape_and_label` | 5-feature map, weight dict | Returns 5 contributions (skills, interests, education, psychometric, CF); label is one of the three valid strings |
| `test_explain_recommendation_with_cf_score_present` | User with recommendation history | `cf_score` feature contribution non-zero; other 4 features present |
| `test_xai_status_reports_active_mode` | (no input, service call) | `active_mode` in ('shap', 'lime', 'fallback'); `features` list includes 'cf_score' |

**Coverage**:
- All 5 features present in contributions output regardless of active mode (SHAP/LIME/fallback)
- CF score correctly attributed to collaborative filtering model

### 5.8 Recommendation Feedback & Bandit Tests (`test_recommendations.py`)

Tests recommendation generation, feedback recording, and bandit-driven reranking.

| Test | Input / Scenario | Key assertions |
|------|-----------------|----------------|
| `test_generate_recommendations_with_cf_blending` | User with recommendation history | `cf_score` in contribution features; score = (1-alpha)*content + alpha*cf |
| `test_record_feedback_updates_bandit_state` | Submit feedback (helpful=true, rating=5) | Policy state file updated; calculated reward = 0.5*1 + 0.5*1 = 1.0 |
| `test_bandit_reranks_after_multiple_feedback` | Submit 5 feedback events, generate new recs | Top role in new generation differs from previous; bandit Q-values reflect learned preferences |
| `test_bandit_epsilon_greedy_exploration` | Bandit with epsilon=0.15 | Enough exploration to see occasional re-rankings of sub-optimal roles |
| `test_feedback_reward_signal_calculation` | helpful=true, rating=3 | reward = 0.5*1 + 0.5*(3-1)/4 = 0.5 + 0.25 = 0.75 |

**Coverage**:
- Epsilon-greedy exploration-exploitation tradeoff working
- Feedback signal correctly merged (helpful + rating)
- Policy persistence across requests

### 5.9 LLM Configuration & Safety Filter Tests (`test_llm_integration.py`)

Tests LLM runtime configuration, fine-tuned model loading, and safety filter behavior.

| Test | Scenario | Assertions |
|------|----------|-----------|
| `test_llm_status_endpoint` | `GET /llm/status` | Returns `enabled`, `provider`, `active_model`, and provider token settings |
| `test_llm_config_update_endpoint` | `POST /llm/config` with `enabled=false` | Next status reflects change; no HTTP restart required |
| `test_llm_config_reset_endpoint` | `POST /llm/config/reset` | Config reverts to env defaults |
| `test_safety_filter_blocks_harmful_content` | Query with harmful intent, LLM enabled | Reply redirects to system message instead of harmful content |
| `test_safety_filter_redirects_offtopic` | Query about unrelated topic | Reply contains redirect prompt ("Could you rephrase in terms of career goals...") |
| `test_safety_filter_prevents_repetition` | Mock LLM output with token loop | Output truncated and generic closing appended |
| `test_safety_filter_disabled_allows_content` | Query with `SAFETY_FILTER_ENABLED=false` | Harmful/off-topic content passes through (for testing) |
| `test_finetuned_model_loading` | Set `LLM_FINETUNED_MODEL=/path/to/model` | Status shows `is_finetuned_active=true`; active_model points to fine-tuned model |

**Coverage**:
- 3-layer safety mechanism working independently
- Config changes take effect immediately (no restart)
- Fine-tuned model integration path validated

### 5.10 Modeling Status & MLOps Tests (`test_modeling_status.py`)

Tests the `/modeling/status` endpoint and reported model enablement states.

| Test | Scenario | Assertions |
|------|----------|-----------|
| `test_modeling_status_cf_enabled` | CF model artifact exists | `cf_model.enabled=true`, `artifact_exists=true`, `blend_alpha` present |
| `test_modeling_status_bandit_enabled` | Bandit policy file present | `bandit.enabled=true`, `policy_exists=true`, `epsilon` present |
| `test_modeling_status_safety_filter` | Safety filter active | `safety_filter.enabled=true`, 3 layers listed |
| `test_modeling_status_explainability` | SHAP/LIME available | `active_mode` in ('shap', 'lime', 'fallback'); 5-feature list present |
| `test_modeling_status_fine_tuning_ready` | Fine-tuning scripts and dataset present | `fine_tuning.infrastructure_ready=true`, example count = 73 |
| `test_modeling_status_intent_classifier_pending` | Intent model not yet trained | `intent_model.enabled=false`, `status='pending_training'` |

**Coverage**:
- All Phase 2 models correctly reported as enabled/pending
- Feature counts and artifact paths verified
- Fallback graceful when artifacts missing

### 5.11 Drift Detection Tests (`test_drift_detection.py`)

Tests input anomaly detection, baseline generation, and CI exit codes.

| Test | Scenario | Assertions |
|------|----------|-----------|
| `test_drift_detection_no_drift_stable_queries` | 100 stable queries vs baseline | `p_value > 0.05`, exit code 0 |
| `test_drift_detection_major_drift_new_vocab` | Queries with 50% new tokens vs baseline | `p_value < 0.05`, exit code 2 (CI gate signal) |
| `test_drift_report_generation` | Run detector with default config | `drift_report.json` generated with KS-stat, top changing tokens, recommendation |
| `test_drift_baseline_generation` | First-time run / no baseline | Baseline file created at `drift_baseline.json`; next run uses as reference |
| `test_drift_heuristic_fallback` | Very small sample size | Falls back to heuristic (vocab coverage check) instead of KS test |

**Coverage**:
- Statistical test (KS) correctly identifies drift
- Baseline generation and persistence working
- CI-friendly exit codes (0 = ok, 2 = drift detected)
- Heuristic fallback for edge cases

---

## 6. Test Execution & CI/CD Integration

### 6.1 Local Execution

```bash
# Run all tests
cd backend
python -m pytest -v tests/

# Run specific test file
python -m pytest -v tests/test_chat.py

# Run tests matching pattern
python -m pytest -v tests/ -k "test_llm or test_bandit"

# Run with coverage
python -m pytest --cov=app --cov-report=html tests/
```

### 6.2 CI Pipeline Gates

Expected test metrics for pipeline pass:

| Metric | Threshold | Tools |
|--------|-----------|-------|
| Test pass rate | 100% | pytest exit code 0 |
| Coverage | ≥ 80% on core services | pytest-cov |
| Drift detection | p-value > 0.05 (no major shifts) | ml-models/evaluation/detect_input_drift.py (exit code < 2) |
| Linting | All messages as errors | flake8 / black |
| Type checking | No errors | mypy |

### 6.3 Test Environment Variables

Recommended for test runs (conftest.py setup):

```python
os.environ['RAG_ENABLED'] = 'false'        # Skip knowledge base init in tests
os.environ['LLM_ENABLED'] = 'false'        # Mock LLM calls
os.environ['SAFETY_FILTER_ENABLED'] = 'true'  # Test safety layer
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/test_db'  # Test DB
os.environ['MONGODB_URL'] = 'mongodb://localhost:27017'  # Test MongoDB (optional)
```

Tests should work even when actual databases are unavailable (graceful degradation).
- `get_explainer_runtime_status()` returns correct `active_mode` string
- Fallback waterfall used when SHAP import is patched to fail

### 5.8 Profile Service Tests (`test_profile_service.py`)

Pure function tests — no I/O.

| Test | Description |
|------|-------------|
| `test_merge_context_with_profile_combines_skills_and_role` | Skills merged, deduplicated, lowercased; target_role from profile preserved |
| `test_summarize_profile_contains_key_fields` | Summary string contains `target_role`, `skills`, `last_intent` |

**Coverage gaps to add**:
- New message skills extracted from `SKILL_BANK` override empty profile
- Role extraction from message via `ROLE_HINTS`
- Profile fully serialises to MongoDB upsert dict

---

## 6. Running Tests

### Full suite

```bash
cd backend
py -m pytest -q
```

Note: total passed test count and warning count may vary as the suite evolves.

### Single module

```bash
py -m pytest tests/test_agents.py -v
```

### With coverage report

```bash
py -m pytest --cov=app --cov-report=term-missing -q
```

### Exclude integration tests (faster)

```bash
py -m pytest --ignore=tests/test_integration.py -q
```

### Filter by keyword

```bash
py -m pytest -k "xai or profile" -v
```

---

## 7. What Each Layer Tests

```
┌──────────────────────────────────────────────────────────────┐
│ Layer              │ Test file(s)              │ Uses DB?    │
├────────────────────┼───────────────────────────┼─────────────┤
│ Route handlers     │ test_integration.py       │ No (mock)   │
│                    │ test_auth.py              │             │
│                    │ test_chat.py              │             │
│                    │ test_rag.py               │             │
│                    │ test_profile_intake.py    │             │
├────────────────────┼───────────────────────────┼─────────────┤
│ Service layer      │ test_ml.py                │ No          │
│                    │ test_profile_service.py   │             │
├────────────────────┼───────────────────────────┼─────────────┤
│ Agent layer        │ test_agents.py            │ No          │
├────────────────────┼───────────────────────────┼─────────────┤
│ NLP / intent       │ test_agents.py            │ No          │
│                    │ test_nlp.py (placeholder) │             │
├────────────────────┼───────────────────────────┼─────────────┤
│ XAI layer          │ test_xai_explanations.py  │ No          │
└──────────────────────────────────────────────────────────────┘
```

---

## 8. Planned / Recommended Test Extensions

### 8.1 Registration and Login Flow (end-to-end)

Currently blocked by PostgreSQL being unavailable in CI. Add a test fixture that:
1. Creates an in-memory SQLite DB using `create_engine("sqlite:///:memory:")`.
2. Runs `init_db()` to create tables.
3. Overrides `get_database_session` dependency to use SQLite.

```python
@pytest.fixture
def sqlite_client():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    app.dependency_overrides[get_database_session] = lambda: TestingSession()
    yield TestClient(app)
    app.dependency_overrides.clear()
```

Tests to add:
- `POST /auth/register` → 200
- `POST /auth/register` (duplicate email) → 409
- `POST /auth/login` (valid credentials) → 200, token returned
- `POST /auth/login` (wrong password) → 401

### 8.2 Recommendation Explain with Auth

```python
def test_recommendation_explain_me_with_auth(client):
    client.app.dependency_overrides[get_current_user] = _auth_override_user
    try:
        payload = {"interests": ["AI"], "skills": ["Python", "SQL"], "education_level": "Masters"}
        response = client.post("/api/v1/recommendations/explain/me", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert "explanations" in body
        for exp in body["explanations"]:
            assert "contributions" in exp
            assert "label" in exp
    finally:
        client.app.dependency_overrides.clear()
```

### 8.3 Intent Confidence Edge Cases

```python
@pytest.mark.parametrize("message,expected_intent", [
    ("I want to learn Python",             "learning_path"),
    ("Tell me about interviews",           "interview_prep"),
    ("Can you recommend a role",           "recommendation"),
    ("Find me a job",                      "job_matching"),
    ("Connect me with mentors",            "networking"),
    ("I want to give feedback",            "feedback"),
    ("",                                   "career_assessment"),   # empty message
    ("   ",                                "career_assessment"),   # whitespace only
    ("!!!", "career_assessment"),                                  # no keywords
])
def test_intent_detection_parametrized(message, expected_intent):
    intent, _, _ = detect_intent_with_confidence(message)
    assert intent == expected_intent
```

### 8.4 XAI Fallback Test (SHAP patched out)

```python
from unittest.mock import patch

def test_explain_recommendation_uses_fallback_when_shap_absent():
    feature_map = {"skill_match": 0.6, "interest_match": 0.5,
                   "education_fit": 0.8, "personalization_bonus": 0.0}
    weights = {"skill": 0.4, "interest": 0.3, "education": 0.3}
    with patch.dict("sys.modules", {"shap": None}):
        contributions, label = explain_recommendation(feature_map, weights)
    assert label == "Weighted fallback contribution summary"
    assert len(contributions) == 4
```

### 8.5 Profile Service Async Tests

```python
import pytest, asyncio
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_user_profile_uses_fallback_when_mongo_unavailable():
    with patch("app.services.profile_service.get_user_profile_collection",
               side_effect=Exception("Mongo down")):
        profile = await get_user_profile("user-x")
    assert isinstance(profile, dict)

@pytest.mark.asyncio
async def test_update_user_profile_extracts_skill_from_message():
    with patch("app.services.profile_service.get_user_profile_collection",
               side_effect=Exception("Mongo down")):
        await update_user_profile("user-x", "I know python and sql", {}, "learning_path", 0.7)
        profile = await get_user_profile("user-x")
    assert "python" in profile.get("skills", [])
    assert "sql" in profile.get("skills", [])
```

### 8.6 RAG Metadata Filter Test

```python
def test_rag_search_with_source_type_filter(client, tmp_path):
    # Ingest one file, then search with a filter that should not match
    doc = tmp_path / "test_notes.txt"
    doc.write_text("Python is used for machine learning pipelines.", encoding="utf-8")
    client.post("/api/v1/rag/ingest", json={"directory_path": str(tmp_path)})
    response = client.get("/api/v1/rag/search?query=python&source_type=nonexistent_type")
    assert response.status_code == 200
    # Filter should narrow or not crash
    assert isinstance(response.json()["results"], list)
```

---

## 9. Performance and Load Testing (Recommended for Production)

Use `locust` or `k6` for load testing. Key scenarios:

| Scenario | Target | Tool |
|----------|--------|------|
| Chat message throughput | ≥100 concurrent users | locust |
| Recommendation generation latency | p95 < 200 ms (LLM disabled) | k6 |
| RAG search under load | p95 < 100 ms | k6 |
| Full pipeline with LLM enabled | p95 < 5 s | locust |

---

## 10. CI / CD Integration Checklist

```yaml
# Suggested GitHub Actions steps
- name: Install dependencies
  run: pip install -r requirements.txt

- name: Run tests
  run: pytest -q --tb=short
  env:
    ENV: testing
    LLM_ENABLED: "false"
    RAG_ENABLED: "true"
    DATABASE_URL: "sqlite:///:memory:"   # use sqlite adapter once added
    MONGODB_URL: ""                       # triggers in-memory fallback

- name: Coverage report
  run: pytest --cov=app --cov-report=xml -q

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

Key CI environment considerations:
- Set `LLM_ENABLED=false` to avoid requiring Ollama in CI.
- MongoDB absence triggers profile fallback dict — tests still pass.
- PostgreSQL absence is caught and returns 503 in auth routes (auth route tests use mocks, so they pass).

---

## 11. Known Test Gaps and Mitigations

| Gap | Risk | Mitigation |
|-----|------|-----------|
| No database integration tests (PostgreSQL, MongoDB) | Register/login flows and history persistence untested | Add SQLite fixtures (§8.1); add MongoDB mock with `mongomock` or `pytest-mongodb` |
| `test_nlp.py` is empty | NLP edge cases not covered | Add parametrised intent tests (§8.3) |
| No LLM-enabled test path | LLM prompt building and fallback untested | Add test with `unittest.mock.patch` on `requests.post` returning synthetic LLM JSON |
| Market API (`Remotive`) calls real external service | Test is environment-dependent | Mock `requests.get` in `market_service` for isolated testing |
| No end-to-end authenticated recommendation test | Explain + feedback cycle not validated | Add §8.2 test |
| XAI SHAP import failure not tested | Fallback correctness unverified | Add §8.4 test |
| Profile async tests use real MongoDB path | `update_user_profile` side effects invisible in tests | Add §8.5 async tests with mock |

---

## 12. Test Naming Conventions

| Convention | Example |
|-----------|---------|
| Intent tests | `test_agent_service_selects_<intent>_agent` |
| Auth guard tests | `test_<endpoint>_requires_auth` |
| With-auth success tests | `test_<endpoint>_with_auth` |
| Service unit tests | `test_<function_name>_<scenario>` |
| Parametrised tests | Use `@pytest.mark.parametrize` with descriptive IDs |
| Edge case tests | `test_<function_name>_<edge_case>` (e.g., `_empty_input`, `_missing_field`) |
