"""Runtime scoring helpers for optional phase-2 user preference model.

The model predicts role affinity from historical feedback-derived features.
When disabled or unavailable, callers should proceed without model scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pickle

from app.config import settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class UserPreferenceModelArtifacts:
	"""In-memory representation of persisted model artifacts."""
	model: object
	feature_names: list[str]


def _normalized_tags(raw_tags: list[object]) -> list[str]:
	"""Normalize feedback tag values to lowercase strings."""
	result: list[str] = []
	for item in raw_tags:
		text = str(item).strip().lower()
		if text:
			result.append(text)
	return result


def _safe_mean(values: list[float]) -> float:
	"""Compute mean for non-empty lists, else return zero."""
	if not values:
		return 0.0
	return float(sum(values) / len(values))


def build_role_feature_vector(feedback_items: list[dict], role: str) -> dict[str, float]:
	"""Build deterministic per-role features from feedback history."""
	role_text = role.strip().lower()
	role_items = [
		item
		for item in feedback_items
		if str(item.get("role", "")).strip().lower() == role_text
	]
	all_count = len(feedback_items)
	role_count = len(role_items)
	if role_count == 0:
		return {
			"role_feedback_count": 0.0,
			"role_feedback_ratio": 0.0,
			"role_helpful_rate": 0.0,
			"role_avg_rating_norm": 0.5,
			"tag_skills_rate": 0.0,
			"tag_interests_rate": 0.0,
			"tag_education_rate": 0.0,
		}

	helpful_values = [1.0 if bool(item.get("helpful", False)) else 0.0 for item in role_items]
	rating_values = [max(1, min(5, int(item.get("rating", 3)))) for item in role_items]
	rating_norm = [float((value - 1) / 4) for value in rating_values]

	tag_skills = 0
	tag_interests = 0
	tag_education = 0
	for item in role_items:
		tags = _normalized_tags(item.get("feedback_tags", []))
		if "skills" in tags:
			tag_skills += 1
		if "interests" in tags:
			tag_interests += 1
		if "education" in tags:
			tag_education += 1

	return {
		"role_feedback_count": float(role_count),
		"role_feedback_ratio": float(role_count / max(1, all_count)),
		"role_helpful_rate": _safe_mean(helpful_values),
		"role_avg_rating_norm": _safe_mean(rating_norm),
		"tag_skills_rate": float(tag_skills / role_count),
		"tag_interests_rate": float(tag_interests / role_count),
		"tag_education_rate": float(tag_education / role_count),
	}


class _UserPreferenceRuntime:
	"""Lazy artifact loader and scorer for user preference predictions."""
	def __init__(self) -> None:
		self._loaded = False
		self._artifacts: UserPreferenceModelArtifacts | None = None

	def _artifact_path(self) -> Path:
		configured = Path(settings.user_preference_model_artifact_path.strip())
		if configured.is_absolute():
			return configured
		repo_root = Path(__file__).resolve().parents[3]
		return repo_root / configured

	def _load(self) -> None:
		if self._loaded:
			return
		path = self._artifact_path()
		if not path.exists():
			logger.warning("User preference model artifact not found at %s", path)
			self._loaded = True
			return
		try:
			with path.open("rb") as fp:
				payload = pickle.load(fp)
			model = payload.get("model")
			feature_names = [str(item) for item in payload.get("feature_names", [])]
			if model is None or not feature_names:
				raise ValueError("Invalid user preference artifact payload")
			self._artifacts = UserPreferenceModelArtifacts(model=model, feature_names=feature_names)
		except Exception:
			logger.exception("Failed to load user preference model artifacts")
			self._artifacts = None
		finally:
			self._loaded = True

	def score_roles(self, feedback_items: list[dict], roles: list[str]) -> dict[str, float]:
		self._load()
		if self._artifacts is None:
			return {}
		scores: dict[str, float] = {}
		for role in roles:
			features = build_role_feature_vector(feedback_items, role)
			vector = [float(features.get(name, 0.0)) for name in self._artifacts.feature_names]
			try:
				proba = self._artifacts.model.predict_proba([vector])[0]
				scores[role] = float(proba[1]) if len(proba) > 1 else float(proba[0])
			except Exception:
				logger.exception("User preference model inference failed for role=%s", role)
		return scores


_RUNTIME = _UserPreferenceRuntime()


def score_role_preferences(feedback_items: list[dict], roles: list[str]) -> dict[str, float]:
	"""Score candidate roles using user preference model if enabled."""
	if not settings.user_preference_model_enabled:
		return {}
	if not feedback_items:
		return {}
	return _RUNTIME.score_roles(feedback_items, roles)
