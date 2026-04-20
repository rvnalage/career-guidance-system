"""Psychometric scoring and persistence helpers for domain recommendations.

Overall purpose:
	Convert user-provided psychometric dimensions into stable, explainable
	domain signals that can personalize career recommendations.

How this module helps the overall system:
	1) Powers psychometric score endpoints (`/psychometric/score`, `/score/me`).
	2) Persists profile memory for future recommendation enrichment.
	3) Provides resilient behavior even when MongoDB/model artifacts are absent.

Primary call flow:
	`score_psychometric` -> `_default_domain_from_traits` -> `_model_primary_domain`
	`save_user_psychometric_profile` -> `score_psychometric` -> Mongo + fallback cache

Main external callers:
	- `app.api.routes.psychometric` (score, save, get, delete endpoints)
	- `app.api.routes.chat` (persists dimensions submitted in chat context)
	- `app.api.routes.recommendations` (reads stored domains for interest enrichment)
"""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from pathlib import Path
import pickle

from app.config import settings
from app.schemas.psychometric import PsychometricRequest
from app.database.mongo_db import get_psychometric_collection
from app.utils.logger import get_logger


logger = get_logger(__name__)


# Deterministic trait-to-domain seed map used when ML model is unavailable.
_DOMAIN_MAP = {
	"investigative": ["Data Science", "AI/ML", "Research"],
	"realistic": ["DevOps", "Embedded Systems", "Cloud Operations"],
	"artistic": ["UI/UX", "Content Design", "Creative Technology"],
	"social": ["Counseling", "Teaching", "People Operations"],
	"enterprising": ["Product Management", "Business Analysis", "Consulting"],
	"conventional": ["Finance Analytics", "Operations", "QA Process"],
}


def _default_domain_from_traits(top_traits: list[str]) -> list[str]:
	"""Build fallback domain recommendations from ranked traits.

	Args:
		top_traits: Traits sorted by score descending.

	Returns:
		A de-duplicated top-5 domain list.

	Significance:
		Round-robin sampling prevents first-trait dominance and lets lower-ranked
		traits still contribute to recommendation diversity.

	Used by:
		`score_psychometric` fallback recommendation path.
	"""
	domains: list[str] = []
	trait_domains = [_DOMAIN_MAP.get(trait, []) for trait in top_traits]
	if not trait_domains:
		return domains

	max_domains = max((len(items) for items in trait_domains), default=0)
	# Interleave domain buckets trait-by-trait for balanced fallback output.
	for domain_index in range(max_domains):
		for items in trait_domains:
			if domain_index >= len(items):
				continue
			domain = items[domain_index]
			if domain not in domains:
				domains.append(domain)
	return domains[:5]


_PSYCHOMETRIC_MODEL_CACHE: dict[str, object] = {"loaded": False, "payload": None}


def _resolve_psychometric_artifact_path() -> Path:
	"""Resolve psychometric model artifact path from config.

	Returns:
		Absolute path to the artifact file.

	Significance:
		Supports both absolute deploy-time paths and repo-relative local paths.

	Used by:
		`_load_psychometric_model` during model bootstrap.
	"""
	configured = Path(settings.psychometric_model_artifact_path.strip())
	if configured.is_absolute():
		return configured
	repo_root = Path(__file__).resolve().parents[3]
	return repo_root / configured


def _load_psychometric_model() -> dict | None:
	"""Load and cache optional psychometric model artifact.

	Returns:
		A payload dict containing model + domain labels, or None when unavailable.

	Significance:
		Caching avoids repeated disk I/O and keeps endpoint latency stable.

	Used by:
		`_model_primary_domain` to fetch model + domain metadata.
	"""
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
	"""Predict primary career domain from normalized trait scores.

	Args:
		normalized_scores: Trait scores in 0-100 scale.

	Returns:
		Predicted domain string when model inference succeeds; otherwise None.

	Significance:
		When enabled, model output is treated as a high-priority signal and placed
		first in the recommendation list.

	Used by:
		`score_psychometric` as optional model-based override.
	"""
	if not settings.psychometric_model_enabled:
		return None
	payload = _load_psychometric_model()
	if payload is None:
		return None
	feature_order = ["investigative", "realistic", "artistic", "social", "enterprising", "conventional"]
	# Keep feature order stable so model inputs match training schema.
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
	"""Score psychometric traits and produce recommendation-ready outputs.

	Args:
		payload: Request object containing raw dimension values (expected 1-5).

	Returns:
		Tuple of:
		1) normalized_scores: dict[str, float] in range 0-100
		2) top_traits: top-3 trait names for compact UI display
		3) recommended_domains: top-5 domains derived from all ranked traits

	Significance:
		This function is the single source of truth for psychometric scoring used by
		both anonymous scoring and persisted authenticated profiles.

	Used by:
		- `app.api.routes.psychometric.score_psychometric_test`
		- `save_user_psychometric_profile`
	"""
	normalized_scores: dict[str, float] = {}
	for key, value in payload.dimensions.items():
		# Clamp noisy inputs to scoring range before normalization.
		bounded = max(1, min(5, int(value)))
		normalized_scores[key.lower().strip()] = round(((bounded - 1) / 4) * 100, 2)

	if not normalized_scores:
		return {}, [], []

	sorted_traits = sorted(normalized_scores.items(), key=lambda item: item[1], reverse=True)
	ranked_traits = [trait for trait, _ in sorted_traits]
	top_traits = ranked_traits[:3]

	domains = _default_domain_from_traits(ranked_traits)
	predicted_primary = _model_primary_domain(normalized_scores)
	if predicted_primary:
		# Promote model signal to first rank while preserving fallback diversity.
		domains = [predicted_primary, *[item for item in domains if item != predicted_primary]]

	return normalized_scores, top_traits, domains[:5]


_psychometric_fallback: dict[str, dict] = {}


async def save_user_psychometric_profile(user_id: str, payload: PsychometricRequest) -> dict:
	"""Compute and persist psychometric profile for a user.

	Args:
		user_id: Durable user identifier.
		payload: Raw psychometric dimensions.

	Returns:
		Persisted profile document with normalized scores, top traits, and domains.

	Significance:
		Saved domains are later merged into recommendation interests for
		personalization across sessions.

	Used by:
		- `app.api.routes.psychometric.score_psychometric_test_me`
		- `app.api.routes.chat` when psychometric dimensions are submitted with chat payload
	"""
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
		# Graceful degradation: keep app functional if Mongo is unavailable.
		pass
	_psychometric_fallback[user_id] = document
	return document


async def get_user_psychometric_profile(user_id: str) -> dict | None:
	"""Load psychometric profile from durable store with fallback.

	Args:
		user_id: Durable user identifier.

	Returns:
		Profile document if found, otherwise None.

	Significance:
		Supports resilient reads in local/test environments where Mongo may be down.

	Used by:
		- `app.api.routes.psychometric.psychometric_profile_me`
		- `app.api.routes.recommendations` psychometric interest enrichment path
		- planner/profile-aware flows that read stored psychometric memory
	"""
	try:
		collection = get_psychometric_collection()
		document = await collection.find_one({"user_id": user_id})
		if document:
			document.pop("_id", None)
			return document
	except Exception:
		pass

	return _psychometric_fallback.get(user_id)


async def delete_user_psychometric_profile(user_id: str) -> bool:
	"""Delete psychometric profile from MongoDB and in-memory fallback.

	Args:
		user_id: Durable user identifier.

	Returns:
		True when a profile was removed from either store; otherwise False.

	Significance:
		Keeps deletion semantics consistent across durable and fallback storage.

	Used by:
		`app.api.routes.psychometric.delete_psychometric_profile_me`.
	"""
	deleted = False
	try:
		collection = get_psychometric_collection()
		result = await collection.delete_one({"user_id": user_id})
		deleted = bool(result.deleted_count)
	except Exception:
		pass

	if user_id in _psychometric_fallback:
		_psychometric_fallback.pop(user_id, None)
		deleted = True

	return deleted

