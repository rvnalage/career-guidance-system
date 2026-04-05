"""Psychometric scoring and persistence helpers for domain recommendations.

The service maps normalized trait scores to a small set of career domains and
supports both durable storage in MongoDB and a lightweight in-memory fallback.
"""

from pathlib import Path
import pickle

from app.config import settings
from app.schemas.psychometric import PsychometricRequest
from app.database.mongo_db import get_psychometric_collection
from app.utils.logger import get_logger


logger = get_logger(__name__)


_DOMAIN_MAP = {
	"investigative": ["Data Science", "AI/ML", "Research"],
	"realistic": ["DevOps", "Embedded Systems", "Cloud Operations"],
	"artistic": ["UI/UX", "Content Design", "Creative Technology"],
	"social": ["Counseling", "Teaching", "People Operations"],
	"enterprising": ["Product Management", "Business Analysis", "Consulting"],
	"conventional": ["Finance Analytics", "Operations", "QA Process"],
}


def _default_domain_from_traits(top_traits: list[str]) -> list[str]:
	"""Resolve recommended domains from deterministic trait mapping."""
	domains: list[str] = []
	for trait in top_traits:
		for domain in _DOMAIN_MAP.get(trait, []):
			if domain not in domains:
				domains.append(domain)
	return domains[:5]


_PSYCHOMETRIC_MODEL_CACHE: dict[str, object] = {"loaded": False, "payload": None}


def _resolve_psychometric_artifact_path() -> Path:
	configured = Path(settings.psychometric_model_artifact_path.strip())
	if configured.is_absolute():
		return configured
	repo_root = Path(__file__).resolve().parents[3]
	return repo_root / configured


def _load_psychometric_model() -> dict | None:
	if _PSYCHOMETRIC_MODEL_CACHE["loaded"]:
		return _PSYCHOMETRIC_MODEL_CACHE["payload"]
	path = _resolve_psychometric_artifact_path()
	if not path.exists():
		logger.warning("Psychometric model artifact not found at %s", path)
		_PSYCHOMETRIC_MODEL_CACHE["loaded"] = True
		return None
	try:
		with path.open("rb") as fp:
			payload = pickle.load(fp)
		if not isinstance(payload, dict) or "model" not in payload or "domains" not in payload:
			raise ValueError("Invalid psychometric model payload")
		_PSYCHOMETRIC_MODEL_CACHE["payload"] = payload
	except Exception:
		logger.exception("Failed to load psychometric model artifact")
		_PSYCHOMETRIC_MODEL_CACHE["payload"] = None
	finally:
		_PSYCHOMETRIC_MODEL_CACHE["loaded"] = True
	return _PSYCHOMETRIC_MODEL_CACHE["payload"]


def _model_primary_domain(normalized_scores: dict[str, float]) -> str | None:
	if not settings.psychometric_model_enabled:
		return None
	payload = _load_psychometric_model()
	if payload is None:
		return None
	feature_order = ["investigative", "realistic", "artistic", "social", "enterprising", "conventional"]
	vector = [float(normalized_scores.get(key, 0.0)) / 100.0 for key in feature_order]
	try:
		model = payload["model"]
		domains = [str(item) for item in payload.get("domains", [])]
		if hasattr(model, "predict_proba"):
			proba = model.predict_proba([vector])[0]
			best_idx = max(range(len(proba)), key=lambda idx: float(proba[idx]))
			if 0 <= best_idx < len(domains):
				return domains[best_idx]
		prediction = model.predict([vector])[0]
		return str(prediction)
	except Exception:
		logger.exception("Psychometric model inference failed")
		return None


def score_psychometric(payload: PsychometricRequest) -> tuple[dict[str, float], list[str], list[str]]:
	"""Normalize trait inputs, rank top traits, and map them to recommended domains."""
	normalized_scores: dict[str, float] = {}
	for key, value in payload.dimensions.items():
		bounded = max(1, min(5, int(value)))
		normalized_scores[key.lower().strip()] = round(((bounded - 1) / 4) * 100, 2)

	if not normalized_scores:
		return {}, [], []

	sorted_traits = sorted(normalized_scores.items(), key=lambda item: item[1], reverse=True)
	top_traits = [trait for trait, _ in sorted_traits[:3]]

	domains = _default_domain_from_traits(top_traits)
	predicted_primary = _model_primary_domain(normalized_scores)
	if predicted_primary:
		domains = [predicted_primary, *[item for item in domains if item != predicted_primary]]

	return normalized_scores, top_traits, domains[:5]


_psychometric_fallback: dict[str, dict] = {}


async def save_user_psychometric_profile(user_id: str, payload: PsychometricRequest) -> dict:
	"""Persist a user's psychometric result for later recommendation enrichment."""
	normalized_scores, top_traits, recommended_domains = score_psychometric(payload)
	document = {
		"user_id": user_id,
		"normalized_scores": normalized_scores,
		"top_traits": top_traits,
		"recommended_domains": recommended_domains,
	}
	try:
		collection = get_psychometric_collection()
		await collection.update_one({"user_id": user_id}, {"$set": document}, upsert=True)
	except Exception:
		_psychometric_fallback[user_id] = document
	return document


async def get_user_psychometric_profile(user_id: str) -> dict | None:
	"""Load a stored psychometric profile from MongoDB or the fallback cache."""
	try:
		collection = get_psychometric_collection()
		document = await collection.find_one({"user_id": user_id})
		if document:
			document.pop("_id", None)
			return document
	except Exception:
		pass

	return _psychometric_fallback.get(user_id)
