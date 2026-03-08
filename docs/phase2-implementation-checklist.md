# Phase-2 Implementation Checklist

This checklist maps each target agent row to concrete implementation tasks.

## 1) NLP / Query Processing (BERT or DistilBERT)

- Create labeled dataset at `ml-models/datasets/intent_queries.csv` with fields: `query`, `intent`, `entities_json`.
- Add training script: `ml-models/training/train_intent_classifier.py` using DistilBERT.
- Export artifacts: `ml-models/pretrained/intent_model/` and label encoder.
- Add inference service: `backend/app/services/intent_model_service.py`.
- Update router to prefer model inference with fallback to keyword logic.
- Add tests:
  - accuracy sanity test on validation split
  - API-level intent behavior regression tests

## 2) User Modeling (RF/XGBoost + Clustering)

- Build interaction dataset from history/feedback snapshots.
- Add feature engineering script: `ml-models/training/build_user_features.py`.
- Train models:
  - preference predictor (`train_user_preference_xgb.py`)
  - optional user clustering (`train_user_clusters.py`)
- Persist artifacts in `ml-models/pretrained/user_modeling/`.
- Add runtime scorer service and blend with current personalization bonus.
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
- Train candidate models:
  - matrix factorization or implicit CF
  - ranking model (XGBoost/LightGBM)
- Add blending logic: content score + CF score + psychometric score.
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
- Update explanation endpoint payload to include:
  - model name/version
  - top positive/negative features
  - confidence interval if available
- Update Dashboard panel labels from "style" to model-backed explanations.

## 7) MLOps and Governance (Cross-Cutting)

- Add model registry metadata file (`model_name`, `version`, `trained_at`, `metrics`).
- Add data version tags for each training run.
- Add drift checks for input distribution changes.
- Add scheduled retraining workflow (weekly or monthly).
- Add safety filters for generated text responses.

## 8) Acceptance Gates

- Intent model macro-F1 >= 0.85
- Recommendation NDCG@K improves over baseline by >= 10%
- Psychometric suitability accuracy >= agreed threshold
- Hallucination rate <= 5% with RAG enabled
- Full backend suite green, frontend build green

## 9) Suggested Execution Order

1. NLP intent model
2. User modeling features + predictor
3. Psychometric predictor
4. Hybrid recommender with CF
5. True SHAP/LIME integration
6. Bandit adaptation
7. MLOps hardening

## 10) Deliverables For Final Report

- Baseline vs phase-2 metrics table
- Ablation study (with/without RAG, with/without fine-tuned model)
- Error analysis on failure cases
- Demo screenshots and endpoint outputs
