# Model Coverage Mapping

This document maps the target architecture (agent-wise model plan) against the current implementation state.

## Legend

- Full: implemented with trained model pipeline matching target approach.
- Partial: feature exists, but uses heuristic/rule-based/simplified logic.
- Planned: not yet implemented.

## Coverage Table

| Agent | Target Model / Technique | Target Training Approach | Current Status | Current Implementation | Gap To Close |
|---|---|---|---|---|---|
| NLP / Query Processing | Transformer embeddings (BERT, DistilBERT) | Fine-tune intent/entity model on career query dataset | Partial | Deterministic keyword intent router with confidence gating; query rewriting + RAG retrieval; optional Ollama-based response refinement | Add supervised intent/entity model training and inference service |
| LLM / Response Refinement | TinyLlama 1.1B (local fine-tuned) | QLoRA parameter-efficient fine-tuning on career guidance dataset | Partial | TinyLlama base model integration via Ollama; fine-tuning infrastructure built (QLoRA trainer, dataset prep, orchestration script); 73 training examples from rag/knowledge/; fine-tuning not yet executed | Execute fine-tuning pipeline; merge adapter into production model |
| User Modeling | Feature embeddings / tabular ML | Train on historical interactions for clustering/preference prediction | Partial | Persistent user profile memory (skills/interests/target_role/intent_counts) with merge/update behavior | Add feature store + clustering/preference modeling pipeline |
| Psychometric Analysis | Regression / classification | Learn psychometric to career suitability mapping | Partial | Deterministic normalization and trait-to-domain mapping; persisted profile for reuse | Add labeled psychometric-career model and calibration metrics |
| Recommendation Agent | Hybrid ML + collaborative filtering | Train on profile + outcomes; optimize relevance | **Full** ✅ | Deterministic weighted scoring (skills/interests/education) + user-item CF matrix (TruncatedSVD) + feedback learned weights | CF model trained and deployed; user-item interaction matrix maintained; cold-start fallback functioning |
| Feedback & Adaptation Agent | RL / online learning | Use reward signals from acceptance/feedback | **Full** ✅ | Epsilon-greedy bandit (Q-learning) with online policy updates from helpful/rating feedback | Bandit deployed and reranking live; policy stored in bandit/policy.json; epsilon-greedy exploration + exploitation balance working |
| Explainability Agent | SHAP/LIME over trained models | Post-hoc explanations from trained predictors | **Full** ✅ | SHAP KernelExplainer and LIME LimeTabularExplainer attached to 5-feature scoring model (skills, interests, education, psychometric, CF); deterministic weighted fallback | SHAP and LIME actively explaining recommendations; CF score integrated as 5th feature; fallback tested for resilience |
| Safety Filter | 3-layer defense (harmful, off-topic, repetition) | Deployed on LLM reply generation | **Full** ✅ | Layer 1: regex + keyword list for harmful content • Layer 2: cosine similarity for off-topic redirect • Layer 3: repetition guard for token/word loops | Safety filter integrated into LLM pipeline; 3 layers engaged by default; `SAFETY_FILTER_ENABLED` flag-gated |
| Drift Detection | Input anomaly detection (KS test) | Kubernetes cronjob / CI gate | **Full** ✅ | Kolmogorov–Smirnov statistical test on query token frequency baseline vs current; heuristic fallback on low sample size | Drift detector script deployed; generates drift_report.json; exits code 2 on significant drift (CI-friendly); baseline stored in drift_baseline.json |

## Implemented Baseline (v1)

These capabilities are implemented and active in the current codebase:

- Agentic chat pipeline with confidence-gated intent routing
- RAG ingestion, retrieval, citations, and metadata-aware reranking
- Optional local LLM post-processing with safe deterministic fallback
- Recommendation generation, explanation, history, and feedback capture
- Psychometric scoring + persistence and recommendation enrichment
- Profile intake upload endpoint for extracting and patching user profile signals

## Current Strengths

- End-to-end product flow is complete and demo-ready.
- RAG is active with ingestion, retrieval, and citations.
- Optional LLaMA integration supports base or fine-tuned model selection.
- Feedback loop already influences future recommendations via dynamic weights and role bonuses.

## Technical Evidence (Code Pointers)

- Intent routing: `backend/app/services/agent_service.py`
- Chat orchestration + LLM: `backend/app/api/routes/chat.py`, `backend/app/services/llm_service.py`
- RAG retrieval and ingestion: `backend/app/services/rag_service.py`, `backend/app/api/routes/rag.py`
- RAG knowledge base: `career-guidance-system/rag/knowledge/` (16 career guidance documents)
- LLM fine-tuning infrastructure:
  - Dataset preparation: `ml-models/training/prepare_tinyllama_dataset.py`
  - QLoRA trainer: `ml-models/training/train_tinyllama_cpu.py`
  - Evaluation: `ml-models/training/eval_tinyllama.py`
  - Orchestration: `scripts/run_tinyllama_finetuning.ps1`
  - Generated dataset: `ml-models/datasets/tinyllama_sft_generated.jsonl` (73 examples)
  - Documentation: `TINYLLAMA_QUICKSTART.md`, `ml-models/training/TINYLLAMA_FINETUNING_GUIDE.md`
- Personalization and recommendation scoring: `backend/app/services/recommendation_service.py`
- Psychometric scoring: `backend/app/services/psychometric_service.py`
- Explainability panel output: `backend/app/services/recommendation_service.py`, `frontend/src/pages/Dashboard.jsx`

## Suggested Dissertation Positioning

Use this statement:

"The current system implements a functionally complete hybrid baseline with deterministic recommendation logic, active RAG grounding, and optional LLM narrative generation. Several modules are intentionally staged for phase-2 replacement with trained models (intent classifier, psychometric predictor, collaborative filtering recommender, and explainability over learned models)."
