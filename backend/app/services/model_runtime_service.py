"""Runtime visibility helpers for phase-2 modelized components."""

from __future__ import annotations

from pathlib import Path

from app.config import settings


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[3]


def _resolve(path_text: str) -> Path:
	path = Path(path_text.strip())
	return path if path.is_absolute() else _repo_root() / path


def get_model_runtime_status() -> dict[str, object]:
	"""Return enablement and artifact availability for optional phase-2 models."""
	intent_dir = _resolve(settings.intent_model_artifact_dir)
	intent_model = intent_dir / "intent_model.pkl"
	intent_labels = intent_dir / "labels.json"

	user_pref_path = _resolve(settings.user_preference_model_artifact_path)
	psy_path = _resolve(settings.psychometric_model_artifact_path)

	cf_dir = _resolve(settings.cf_model_artifact_path)
	cf_model = cf_dir / "cf_model.pkl"

	bandit_dir = _resolve(settings.bandit_artifact_path)
	bandit_state = bandit_dir / "bandit_state.json"

	return {
		"intent_model": {
			"enabled": settings.intent_model_enabled,
			"artifact_dir": str(intent_dir),
			"model_exists": intent_model.exists(),
			"labels_exists": intent_labels.exists(),
			"min_confidence": settings.intent_model_min_confidence,
		},
		"user_preference_model": {
			"enabled": settings.user_preference_model_enabled,
			"artifact_path": str(user_pref_path),
			"artifact_exists": user_pref_path.exists(),
			"blend_alpha": settings.user_preference_model_alpha,
		},
		"psychometric_model": {
			"enabled": settings.psychometric_model_enabled,
			"artifact_path": str(psy_path),
			"artifact_exists": psy_path.exists(),
		},
		"cf_model": {
			"enabled": settings.cf_model_enabled,
			"artifact_dir": str(cf_dir),
			"artifact_exists": cf_model.exists(),
			"blend_alpha": settings.cf_model_alpha,
		},
		"bandit": {
			"enabled": settings.bandit_enabled,
			"artifact_dir": str(bandit_dir),
			"state_exists": bandit_state.exists(),
			"epsilon": settings.bandit_epsilon,
		},
		"safety_filter": {
			"enabled": settings.safety_filter_enabled,
		},
	}
