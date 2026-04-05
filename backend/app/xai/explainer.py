"""Explain recommendation scores using SHAP, LIME, or a deterministic fallback.

All explainers return the same feature-contribution structure so downstream API
code does not need to care which runtime mode is currently active.
"""

from __future__ import annotations

from typing import Tuple

from app.xai.interpretability import FEATURE_ORDER, feature_vector_from_map, get_model_coefficients, prediction_fn


def _fallback_weighted_contributions(feature_map: dict[str, float], weights: dict[str, float]) -> list[tuple[str, float]]:
	"""Compute feature contributions directly from the linear scoring coefficients."""
	# This deterministic fallback mirrors the linear recommendation score and guarantees explainability output.
	coefficients = get_model_coefficients(weights)
	vector = feature_vector_from_map(feature_map)
	contributions: list[tuple[str, float]] = []
	for feature, value, coef in zip(FEATURE_ORDER, vector, coefficients):
		contributions.append((feature, round(value * coef, 4)))
	return contributions


def _try_shap(feature_map: dict[str, float], weights: dict[str, float]) -> list[tuple[str, float]] | None:
	"""Attempt SHAP-based explanation and return None if SHAP is unavailable or fails."""
	try:
		import numpy as np
		import shap

		# A single zero vector is enough as the background because the recommendation model is linear and low-dimensional.
		coefficients = get_model_coefficients(weights)
		vector = feature_vector_from_map(feature_map)
		background = np.zeros((1, len(FEATURE_ORDER)))
		x = np.array([vector], dtype=float)
		model = prediction_fn(coefficients)
		explainer = shap.KernelExplainer(model, background)
		shap_values = explainer.shap_values(x, nsamples=80)

		values = np.asarray(shap_values, dtype=float)
		if values.ndim == 3:
			values = values[0]
		if values.ndim == 2:
			values = values[0]

		return [(feature, round(float(value), 4)) for feature, value in zip(FEATURE_ORDER, values.tolist())]
	except Exception:
		return None


def _try_lime(feature_map: dict[str, float], weights: dict[str, float]) -> list[tuple[str, float]] | None:
	"""Attempt LIME-based explanation and return None if LIME is unavailable or fails."""
	try:
		import numpy as np
		from lime.lime_tabular import LimeTabularExplainer

		# LIME needs a small synthetic training matrix even though the underlying model is hand-crafted.
		coefficients = get_model_coefficients(weights)
		vector = np.array(feature_vector_from_map(feature_map), dtype=float)
		n_features = len(FEATURE_ORDER)
		training = np.array(
			[
				[0.0, 0.0, 0.0, 0.0, 0.5],
				[1.0, 1.0, 1.0, 0.1, 0.8],
				[0.5, 0.3, 1.0, 0.0, 0.5],
				[0.8, 0.2, 0.6, -0.1, 0.3],
			],
			dtype=float,
		)[:, :n_features]
		explainer = LimeTabularExplainer(
			training_data=training,
			feature_names=FEATURE_ORDER,
			mode="regression",
			discretize_continuous=False,
		)

		def _predict(arr: np.ndarray) -> np.ndarray:
			rows = arr.tolist()
			return np.array(prediction_fn(coefficients)(rows), dtype=float)

		explanation = explainer.explain_instance(vector, _predict, num_features=len(FEATURE_ORDER))
		pairs = explanation.as_list()
		resolved: list[tuple[str, float]] = []
		for feature in FEATURE_ORDER:
			match = next((value for name, value in pairs if feature in name), None)
			resolved.append((feature, round(float(match or 0.0), 4)))
		return resolved
	except Exception:
		return None


def explain_recommendation(
	feature_map: dict[str, float],
	weights: dict[str, float],
) -> Tuple[list[tuple[str, float]], str]:
	"""Return explanation contributions and a label describing the active explainer mode."""
	# Prefer higher-fidelity explainers first, but never fail the endpoint if optional libraries are missing.
	shap_contribs = _try_shap(feature_map, weights)
	if shap_contribs is not None:
		return shap_contribs, "SHAP contribution summary"

	lime_contribs = _try_lime(feature_map, weights)
	if lime_contribs is not None:
		return lime_contribs, "LIME contribution summary"

	return _fallback_weighted_contributions(feature_map, weights), "Weighted fallback contribution summary"


def get_explainer_runtime_status() -> dict[str, object]:
	"""Report which explainer libraries are importable and which mode will be used."""
	shap_available = False
	lime_available = False

	try:
		import shap  # noqa: F401

		shap_available = True
	except Exception:
		shap_available = False

	try:
		from lime import lime_tabular  # noqa: F401

		lime_available = True
	except Exception:
		lime_available = False

	if shap_available:
		active_mode = "shap"
	elif lime_available:
		active_mode = "lime"
	else:
		active_mode = "fallback"

	return {
		"active_mode": active_mode,
		"shap_available": shap_available,
		"lime_available": lime_available,
		"fallback_enabled": True,
	}
