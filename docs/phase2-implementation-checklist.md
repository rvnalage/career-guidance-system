# Phase-2 Implementation Checklist

This checklist tracks net-new phase-2 work on top of the currently implemented v1 baseline.

## 0) Implemented Baseline (Do Not Rebuild)

- Deterministic intent routing with confidence gating and agent registry
- RAG ingestion, retrieval, reranking, and citation responses
- Optional Ollama LLM post-processing with deterministic fallback
- Recommendation generation, explanation, history, and feedback capture
- Psychometric scoring and profile persistence
- Profile memory merge/update and profile-intake upload flow

Use this baseline as the comparison point for all phase-2 improvements.

## 0.5) TinyLlama Fine-Tuning Infrastructure ✅

**Status: Infrastructure Complete, Training Pending**

- ✅ Consolidated RAG knowledge base: 16 career guidance documents moved to `rag/knowledge/` (source of truth for both RAG and training).
- ✅ Dataset preparation: `ml-models/training/prepare_tinyllama_dataset.py` generates 73 JSONL training examples from knowledge base.
- ✅ QLoRA trainer: `ml-models/training/train_tinyllama_cpu.py` implements parameter-efficient fine-tuning (batch size 1, gradient accumulation 4, 1-2 hours per epoch on CPU).
- ✅ Evaluation: `ml-models/training/eval_tinyllama.py` tests fine-tuned model on 5 career guidance prompts.
- ✅ Orchestration: `scripts/run_tinyllama_finetuning.ps1` PowerShell script stages prepare → train → evaluate pipeline.
- ✅ Documentation: `TINYLLAMA_QUICKSTART.md` and `TINYLLAMA_FINETUNING_GUIDE.md` with integration paths.
- Generated artifacts: `ml-models/datasets/tinyllama_sft_generated.jsonl` (73 examples, 76 KB ready).
- **Next steps**: Execute pipeline → merge adapter → deploy fine-tuned model to production.
- **Integration**: Fine-tuned model can be loaded via `LLM_FINETUNED_MODEL` env var or exported as Ollama custom model.

## 1) NLP / Query Processing (BERT or DistilBERT)

- Build labeled dataset at `ml-models/datasets/intent_queries.csv` with `query,intent,entities_json`.
- Add training pipeline at `ml-models/training/train_intent_classifier.py`.
- Save model artifacts under `ml-models/pretrained/intent_model/`.
- Add runtime inference service at `backend/app/services/intent_model_service.py`.
- Integrate model-first routing with current keyword fallback retained.
- Add tests for validation metrics and API-level intent regression.

## 2) User Modeling (RF/XGBoost + Clustering)

- Build interaction dataset from history/feedback snapshots.
- Add feature engineering script: `ml-models/training/build_user_features.py`.
- Train preference predictor (`train_user_preference_xgb.py`).
- Train optional user clustering (`train_user_clusters.py`).
- Persist artifacts in `ml-models/pretrained/user_modeling/`.
- Add runtime scorer service and blend outputs with current heuristic personalization profile.
- Add offline evaluation: AUC/F1 (classification) and silhouette score (clustering).

## 3) Psychometric Analysis (Trained Predictor)

- Create labeled psychometric-career suitability dataset.
- Add training script: `ml-models/training/train_psychometric_model.py`.
- Persist model and scaler at `ml-models/pretrained/psychometric_model/`.
- Update `backend/app/services/psychometric_service.py` to call model inference.
- Keep deterministic mapping as fallback.
- Add tests for model I/O and endpoint correctness.

## 4) Recommendation Agent (Hybrid + Collaborative Filtering) ✅

- ✅ Prepare user-item interaction matrix from recommendation history + feedback.
- ✅ Train candidate CF model (TruncatedSVD matrix factorization) — `ml-models/training/train_cf_recommender.py`.
- ✅ Runtime CF service at `backend/app/services/cf_service.py` with cold-start fallback to column means.
- ✅ Add blending logic: baseline content score + CF additive term (cf_model_alpha) + psychometric score.
- ✅ CF scores stored separately in personalization profile so they appear as explicit `cf_score` feature in XAI output.
- ✅ Track metrics: Recall@K, NDCG@K, MAP@K via `ml-models/evaluation/evaluate_recommendation_ranking.py`.
- Config flags: `CF_MODEL_ENABLED`, `CF_MODEL_ARTIFACT_PATH`, `CF_MODEL_ALPHA`.

## 5) Feedback & Adaptation Agent (Bandit/RL-lite) ✅

- ✅ Define reward signal from `helpful`, `rating`: `reward = 0.5*helpful + 0.5*(rating-1)/4`.
- ✅ Implement epsilon-greedy bandit policy — `backend/app/services/bandit_service.py`.
- ✅ Store policy state in JSON file; update online after each feedback event via `record_feedback()`.
- ✅ Bandit reranks top-K recommendations post content scoring via `rerank_recommendations()`.
- ✅ Guardrails: configurable epsilon, bounded score shifts, flag-gated (disabled by default).
- Config flags: `BANDIT_ENABLED`, `BANDIT_ARTIFACT_PATH`, `BANDIT_EPSILON`.
- Pending: offline replay evaluation script.

## 6) Explainability Agent (True SHAP/LIME) ✅

- ✅ SHAP KernelExplainer and LIME LimeTabularExplainer attached to full 5-feature scoring model.
- ✅ `cf_score` added as 5th feature in `FEATURE_ORDER`; SHAP background and LIME training matrix updated.
- ✅ Each recommendation response includes `cf_score` as named `FeatureContribution`.
- ✅ Deterministic weighted fallback retained for resilience when SHAP/LIME not installed.
- ✅ `get_explainer_runtime_status()` reports active explainer mode.

## 7) MLOps and Governance (Cross-Cutting) ✅

- ✅ Model registry metadata (`model_registry.json`) output by all five training scripts.
- ✅ `--model-version` and `--data-version` CLI args on all training scripts.
- ✅ `GET /api/v1/modeling/status` endpoint reports enablement + artifact presence for all 5 models + safety filter.
- ✅ `backend/app/services/model_runtime_service.py` covers intent, user-pref, psychometric, CF, bandit, safety filter.
- ✅ Input drift detection — `ml-models/evaluation/detect_input_drift.py` (KS test + heuristic fallback); baseline at `drift_baseline.json`; `drift_report.json` output; exits with code 2 if drift detected (CI-friendly).
- ✅ Bandit offline replay evaluator — `ml-models/evaluation/evaluate_bandit_replay.py`; computes Recall@1 and mean reward vs random baseline per user; writes `bandit_replay_results.json`.
- ✅ LLM reply safety filter — `backend/app/services/safety_filter.py`; 3-layer (harmful block → off-topic redirect → repetition guard); applied in `generate_llm_reply()`; flag-gated via `SAFETY_FILTER_ENABLED` (default True).
- 🔲 Scheduled retraining workflow (weekly/monthly cron — out of scope for local dev setup).

## 8) Acceptance Gates

- Intent model macro-F1 >= 0.85 on held-out set.
- Recommendation NDCG@K improves over v1 baseline by >= 10%.
- Psychometric suitability accuracy reaches agreed threshold.
- Hallucination rate <= 5% with RAG enabled.
- Full backend suite green and frontend build green.

## 9) Suggested Execution Order

1. NLP intent model
2. User modeling features + predictor
3. Psychometric predictor
4. Hybrid recommender with CF
5. Explainability on trained recommender
6. Bandit adaptation
7. MLOps hardening

## 10) Deliverables For Final Report

- Baseline (v1) vs phase-2 metrics table
- Ablation study (with/without RAG, with/without fine-tuned model)
- Error analysis on failure cases
- Demo screenshots and endpoint outputs

## 11) Change Control Notes

- Keep deterministic services available behind feature flags until trained-model parity is proven.
- Add one rollback switch per modelized component (`intent`, `recommendation`, `psychometric`, `xai`).
- Record all phase-2 metric runs with dataset version and model version for reproducibility.
