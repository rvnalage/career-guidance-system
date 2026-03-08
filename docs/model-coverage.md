# Model Coverage Mapping

This document maps the target architecture (agent-wise model plan) against the current implementation state.

## Legend

- Full: implemented with trained model pipeline matching target approach.
- Partial: feature exists, but uses heuristic/rule-based/simplified logic.
- Planned: not yet implemented.

## Coverage Table

| Agent | Target Model / Technique | Target Training Approach | Current Status | Current Implementation | Gap To Close |
|---|---|---|---|---|---|
| NLP / Query Processing | Transformer embeddings (BERT, DistilBERT) | Fine-tune intent/entity model on career query dataset | Partial | Rule-based intent router + RAG + optional LLaMA response generation | Add supervised intent classifier training and inference service |
| User Modeling | Feature embeddings / tabular ML | Train on historical interactions for clustering/preference prediction | Partial | Feedback-weighted personalization profile | Add user feature store + RF/XGBoost/clustering pipeline |
| Psychometric Analysis | Regression / classification | Learn psychometric to career suitability mapping | Partial | Deterministic trait normalization and domain mapping | Add labeled psychometric-career dataset and trained model endpoint |
| Recommendation Agent | Hybrid ML + collaborative filtering | Train on profile + outcomes; optimize relevance | Partial | Weighted skills/interests/education scoring + feedback bonus | Add collaborative filtering and offline ranking model training |
| Feedback & Adaptation Agent | RL / online learning | Use reward signals from acceptance/feedback | Partial | Online weight updates from helpful/rating tags | Add contextual bandit or policy optimization loop |
| Explainability Agent | SHAP/LIME over trained models | Post-hoc explanations from trained predictors | Partial | SHAP/LIME-style contribution summaries over deterministic scores | Integrate true SHAP/LIME against trained recommendation model |

## Current Strengths

- End-to-end product flow is complete and demo-ready.
- RAG is active with ingestion, retrieval, and citations.
- Optional LLaMA integration supports base or fine-tuned model selection.
- Feedback loop already influences future recommendations.

## Technical Evidence (Code Pointers)

- Intent routing: `backend/app/services/agent_service.py`
- Chat orchestration + LLM: `backend/app/api/routes/chat.py`, `backend/app/services/llm_service.py`
- RAG retrieval and ingestion: `backend/app/services/rag_service.py`, `backend/app/api/routes/rag.py`
- Personalization and recommendation scoring: `backend/app/services/recommendation_service.py`
- Psychometric scoring: `backend/app/services/psychometric_service.py`
- Explainability panel output: `backend/app/services/recommendation_service.py`, `frontend/src/pages/Dashboard.jsx`

## Suggested Dissertation Positioning

Use this statement:

"The current system implements a functionally complete hybrid baseline with deterministic recommendation logic, active RAG grounding, and optional LLM narrative generation. Several modules are intentionally staged for phase-2 replacement with trained models (intent classifier, psychometric predictor, collaborative filtering recommender, and true SHAP/LIME explainability over learned models)."
