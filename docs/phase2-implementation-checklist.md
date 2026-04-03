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

## 4) Recommendation Agent (Hybrid + Collaborative Filtering)

- Prepare user-item interaction matrix from recommendation history + feedback.
- Train candidate CF model (matrix factorization or implicit CF).
- Train ranking model (XGBoost/LightGBM).
- Add blending logic: baseline content score + CF score + psychometric score.
- Add calibration and top-k evaluation pipeline.
- Track metrics: Recall@K, NDCG@K, MAP@K.

## 5) Feedback & Adaptation Agent (Bandit/RL-lite)

- Define reward signal from `helpful`, `rating`, and downstream actions.
- Implement contextual bandit policy (epsilon-greedy or LinUCB).
- Store policy state and update online after feedback events.
- Add guardrails: min exploration, bounded score shifts.
- Add offline replay evaluation script.

## 6) Explainability Agent (True SHAP/LIME)

- Attach SHAP/LIME over trained ranking model inputs.
- Return feature attributions for each recommended role.
- Update explanation endpoint payload to include `model_name`, `model_version`, top positive/negative features, and confidence interval (if available).
- Keep current deterministic fallback path for runtime resilience.

## 7) MLOps and Governance (Cross-Cutting)

- Add model registry metadata file (`model_name`, `version`, `trained_at`, `metrics`).
- Add data version tags for each training run.
- Add drift checks for input distribution changes.
- Add scheduled retraining workflow (weekly or monthly).
- Add safety filters for generated text responses.

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
