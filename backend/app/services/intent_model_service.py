"""Runtime loader and inference helpers for the phase-2 intent classifier.

This module is optional by design. If artifacts are missing or confidence is low,
callers should fall back to the deterministic keyword router.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import pickle

from app.config import settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class IntentPrediction:
	"""Container for intent prediction output used by the router."""
	intent: str
	confidence: float


class _IntentModelRuntime:
	"""Lazy-loaded intent model runtime for simple predict/predict_proba usage."""
	def __init__(self) -> None:
		self._loaded = False
		self._model = None
		self._labels: list[str] = []

	def _artifact_dir(self) -> Path:
		configured = Path(settings.intent_model_artifact_dir.strip())
		if configured.is_absolute():
			return configured
		# Resolve relative paths from repository root (career-guidance-system/).
		repo_root = Path(__file__).resolve().parents[3]
		return repo_root / configured

	def _load(self) -> None:
		if self._loaded:
			return
		model_path = self._artifact_dir() / "intent_model.pkl"
		labels_path = self._artifact_dir() / "labels.json"
		if not model_path.exists() or not labels_path.exists():
			logger.warning("Intent model artifacts not found at %s", self._artifact_dir())
			self._loaded = True
			return
		try:
			with model_path.open("rb") as fp:
				self._model = pickle.load(fp)
			with labels_path.open("r", encoding="utf-8") as fp:
				data = json.load(fp)
				self._labels = [str(label) for label in data.get("labels", []) if str(label).strip()]
		except Exception:
			logger.exception("Failed to load intent model artifacts")
			self._model = None
			self._labels = []
		finally:
			self._loaded = True

	def predict(self, message: str) -> IntentPrediction | None:
		self._load()
		if self._model is None or not self._labels:
			return None
		text = message.strip()
		if not text:
			return None
		try:
			proba = self._model.predict_proba([text])[0]
			best_index = max(range(len(proba)), key=lambda idx: float(proba[idx]))
			confidence = float(proba[best_index])
			if confidence < settings.intent_model_min_confidence:
				return None
			return IntentPrediction(intent=self._labels[best_index], confidence=round(confidence, 4))
		except Exception:
			logger.exception("Intent model inference failed")
			return None


_RUNTIME = _IntentModelRuntime()


def detect_intent_with_model(message: str) -> IntentPrediction | None:
	"""Predict intent from trained artifacts when the feature is enabled."""
	if not settings.intent_model_enabled:
		return None
	return _RUNTIME.predict(message)
