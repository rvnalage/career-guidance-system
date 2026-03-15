from __future__ import annotations

from typing import Callable


FEATURE_ORDER = [
	"skill_match",
	"interest_match",
	"education_fit",
	"personalization_bonus",
]


def get_model_coefficients(weights: dict[str, float]) -> list[float]:
	# personalization bonus is already a direct additive adjustment in the score.
	return [
		float(weights.get("skill", 0.5)),
		float(weights.get("interest", 0.3)),
		float(weights.get("education", 0.2)),
		1.0,
	]


def bounded_linear_score(feature_vector: list[float], coefficients: list[float]) -> float:
	raw = sum(value * coef for value, coef in zip(feature_vector, coefficients))
	return max(0.0, min(1.0, raw))


def prediction_fn(coefficients: list[float]) -> Callable[[list[list[float]]], list[float]]:
	def _predict(rows: list[list[float]]) -> list[float]:
		return [bounded_linear_score(row, coefficients) for row in rows]

	return _predict


def feature_vector_from_map(feature_map: dict[str, float]) -> list[float]:
	return [float(feature_map.get(name, 0.0)) for name in FEATURE_ORDER]
