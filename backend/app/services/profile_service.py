"""Profile-memory helpers used to persist and reuse user context across chat turns.

The stored profile is intentionally lightweight: skills, interests, target role,
and routing history. MongoDB is preferred, but an in-memory fallback keeps the
chat flow usable during tests and local development.
"""

# Developer Onboarding Notes:
# - Layer: profile memory service
# - Role in system: Persists lightweight user context used to personalize planner/chat behavior.
# - Main callers: chat routes, planner service, and profile-intake flow.
# - Reading tip: Start from update_user_profile/get_user_profile, then merge_context_with_profile.


from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.database.mongo_db import get_user_profile_collection
from app.utils.logger import get_logger


logger = get_logger(__name__)

# In-memory fallback keeps chat personalization alive in tests or when MongoDB is temporarily unavailable.
_profile_fallback: dict[str, dict[str, Any]] = {}

SKILL_BANK = {
	"python",
	"sql",
	"excel",
	"power bi",
	"tableau",
	"statistics",
	"machine learning",
	"deep learning",
	"nlp",
	"docker",
	"kubernetes",
	"aws",
	"fastapi",
	"figma",
}

ROLE_HINTS = {
	"data scientist": ["data scientist", "data science"],
	"data analyst": ["data analyst", "analytics"],
	"data engineer": ["data engineer", "etl", "pipeline"],
	"ml engineer": ["ml engineer", "machine learning engineer", "mle"],
	"backend developer": ["backend", "api developer", "fastapi"],
	"devops engineer": ["devops", "sre", "site reliability"],
	"ui/ux designer": ["ui/ux", "ux designer", "product designer"],
}


def _normalized_set(items: list[str]) -> list[str]:
	"""Normalize text items to lowercase unique values while preserving insertion order."""
	# Normalize to lowercase while preserving first-seen order for cleaner prompts and stable tests.
	seen: set[str] = set()
	result: list[str] = []
	for item in items:
		text = str(item).strip().lower()
		if text and text not in seen:
			seen.add(text)
			result.append(text)
	return result


def _extract_role(message: str, context: dict[str, Any] | None = None) -> str | None:
	"""Infer the user's target role from structured context first, then message text."""
	if context and isinstance(context.get("target_role"), str):
		role = context["target_role"].strip().lower()
		if role:
			return role
	# Message parsing acts as a fallback when the client does not send structured context.
	text = message.lower()
	for role, hints in ROLE_HINTS.items():
		if any(hint in text for hint in hints):
			return role
	return None


def _extract_skills(message: str, context: dict[str, Any] | None = None) -> list[str]:
	"""Collect known skills from explicit context plus free-text message matches."""
	skills: list[str] = []
	if context and isinstance(context.get("skills"), list):
		skills.extend([str(item) for item in context["skills"]])
	text = message.lower()
	for skill in SKILL_BANK:
		if skill in text:
			skills.append(skill)
	return _normalized_set(skills)


def _extract_interests(context: dict[str, Any] | None = None) -> list[str]:
	"""Return normalized interests from structured context when present."""
	if not context or not isinstance(context.get("interests"), list):
		return []
	return _normalized_set([str(item) for item in context["interests"]])


def merge_context_with_profile(context: dict[str, Any] | None, profile: dict[str, Any] | None) -> dict[str, Any]:
	"""Merge request context with persisted profile memory for downstream routing.

	Significance:
		Defines precedence contract: request context wins; profile fills gaps and extends lists.

	Used by:
		Chat/planner orchestration before intent routing and tool execution.
	"""
	# Request-scoped context wins when present; profile memory fills only missing fields and broadens lists.
	merged = dict(context or {})
	profile = profile or {}

	profile_skills = [str(item) for item in profile.get("skills", [])]
	context_skills = [str(item) for item in merged.get("skills", [])] if isinstance(merged.get("skills"), list) else []
	merged["skills"] = _normalized_set(context_skills + profile_skills)

	if not merged.get("target_role") and isinstance(profile.get("target_role"), str):
		merged["target_role"] = profile["target_role"]

	profile_interests = [str(item) for item in profile.get("interests", [])]
	context_interests = [str(item) for item in merged.get("interests", [])] if isinstance(merged.get("interests"), list) else []
	merged["interests"] = _normalized_set(context_interests + profile_interests)

	if isinstance(profile.get("target_companies"), list) and not merged.get("target_companies"):
		merged["target_companies"] = profile.get("target_companies", [])

	return merged


def extract_networking_metrics(profile: dict[str, Any] | None) -> tuple[int | None, int | None]:
	"""Return historical networking availability/response metrics from profile memory."""
	if not profile:
		return None, None
	metrics = profile.get("networking_metrics") if isinstance(profile.get("networking_metrics"), dict) else {}
	availability = metrics.get("avg_weekly_availability_hours")
	response_rate = metrics.get("avg_response_rate_percent")
	try:
		availability_value = int(round(float(availability))) if availability is not None else None
	except (TypeError, ValueError):
		availability_value = None
	try:
		response_value = int(round(float(response_rate))) if response_rate is not None else None
	except (TypeError, ValueError):
		response_value = None
	if availability_value is not None and not (1 <= availability_value <= 80):
		availability_value = None
	if response_value is not None and not (0 <= response_value <= 100):
		response_value = None
	return availability_value, response_value


async def record_networking_metrics(
	user_id: str,
	*,
	weekly_availability_hours: int | None = None,
	response_rate_percent: int | None = None,
) -> dict[str, Any]:
	"""Update rolling networking metrics from newly observed user signals.

	Returns:
		Updated `networking_metrics` block containing rolling averages and sample count.

	Significance:
		Provides longitudinal signal for networking planner cadence tuning.

	Used by:
		Planner networking tool when user provides availability/response-rate hints.
	"""
	if weekly_availability_hours is None and response_rate_percent is None:
		return {}
	existing = await get_user_profile(user_id)
	current = dict(existing.get("networking_metrics", {})) if isinstance(existing.get("networking_metrics"), dict) else {}
	samples = int(current.get("samples", 0))
	next_samples = samples + 1
	updated = dict(current)

	if weekly_availability_hours is not None:
		prev_hours = current.get("avg_weekly_availability_hours")
		if prev_hours is None:
			updated["avg_weekly_availability_hours"] = int(weekly_availability_hours)
		else:
			updated["avg_weekly_availability_hours"] = round(
				((float(prev_hours) * samples) + float(weekly_availability_hours)) / max(1, next_samples),
				1,
			)
		updated["last_weekly_availability_hours"] = int(weekly_availability_hours)

	if response_rate_percent is not None:
		prev_rate = current.get("avg_response_rate_percent")
		if prev_rate is None:
			updated["avg_response_rate_percent"] = int(response_rate_percent)
		else:
			updated["avg_response_rate_percent"] = round(
				((float(prev_rate) * samples) + float(response_rate_percent)) / max(1, next_samples),
				1,
			)
		updated["last_response_rate_percent"] = int(response_rate_percent)

	updated["samples"] = next_samples
	updated["updated_at"] = datetime.now(timezone.utc).isoformat()

	document = {
		"networking_metrics": updated,
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}
	try:
		collection = get_user_profile_collection()
		await collection.update_one({"user_id": user_id}, {"$set": document, "$setOnInsert": {"user_id": user_id}}, upsert=True)
		fallback_profile = dict(existing)
		fallback_profile["user_id"] = user_id
		fallback_profile["networking_metrics"] = updated
		fallback_profile["updated_at"] = document["updated_at"]
		_profile_fallback[user_id] = fallback_profile
	except Exception:
		logger.exception("Failed to record networking metrics for user_id=%s", user_id)
		fallback_profile = dict(existing)
		fallback_profile["user_id"] = user_id
		fallback_profile["networking_metrics"] = updated
		fallback_profile["updated_at"] = document["updated_at"]
		_profile_fallback[user_id] = fallback_profile
	return updated


async def get_user_profile(user_id: str) -> dict[str, Any]:
	"""Load user profile from MongoDB with in-memory fallback.

	Significance:
		Core read path for personalization. Intentionally resilient to storage outages.
	"""
	try:
		collection = get_user_profile_collection()
		document = await collection.find_one({"user_id": user_id})
		if not document:
			return {}
		document.pop("_id", None)
		return document
	except Exception:
		# Swallow storage errors here so chat routing does not fail on a missing MongoDB instance.
		logger.exception("Failed to load user profile from MongoDB for user_id=%s", user_id)
		return _profile_fallback.get(user_id, {})


async def update_user_profile(
	user_id: str,
	message: str,
	context: dict[str, Any] | None,
	intent: str,
	intent_confidence: float,
) -> dict[str, Any]:
	"""Persist incremental profile updates extracted from latest chat turn.

	Args:
		user_id: User identity key for profile storage.
		message: Raw user utterance used for heuristic extraction.
		context: Structured context payload from client/route.
		intent: Routed primary intent label.
		intent_confidence: Routing confidence saved for auditability.

	Returns:
		Full updated profile document persisted (or cached in fallback store).

	Significance:
		Main write path for durable personalization memory across chat sessions.

	Used by:
		Chat message flow and profile-intake enrichment paths.
	"""
	existing = await get_user_profile(user_id)
	# Profile updates are additive: we accumulate durable preferences instead of replacing them with each turn.
	skills = _normalized_set([*existing.get("skills", []), *_extract_skills(message, context)])
	interests = _normalized_set([*existing.get("interests", []), *_extract_interests(context)])
	role = _extract_role(message, context) or existing.get("target_role")
	intent_counts = dict(existing.get("intent_counts", {}))
	intent_counts[intent] = int(intent_counts.get(intent, 0)) + 1

	document = {
		"user_id": user_id,
		"skills": skills,
		"interests": interests,
		"target_role": role,
		"target_companies": existing.get("target_companies", []),
		"networking_metrics": existing.get("networking_metrics", {}),
		"intent_counts": intent_counts,
		"last_intent": intent,
		"last_intent_confidence": round(float(intent_confidence), 4),
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}
	try:
		collection = get_user_profile_collection()
		await collection.update_one({"user_id": user_id}, {"$set": document}, upsert=True)
		_profile_fallback[user_id] = document
	except Exception:
		# Tests and local development can operate without Mongo because the fallback cache mirrors the stored shape.
		logger.exception("Failed to persist user profile to MongoDB for user_id=%s", user_id)
		_profile_fallback[user_id] = document
	return document


def summarize_profile(profile: dict[str, Any] | None) -> str:
	"""Convert profile fields into compact single-line summary for prompts.

	Used by:
		Planner and LLM prompt builders.
	"""
	if not profile:
		return "No profile memory available."
	parts: list[str] = []
	if profile.get("target_role"):
		parts.append(f"target_role={profile['target_role']}")
	if profile.get("skills"):
		parts.append(f"skills={', '.join(profile['skills'][:5])}")
	if profile.get("interests"):
		parts.append(f"interests={', '.join(profile['interests'][:5])}")
	if profile.get("last_intent"):
		parts.append(f"last_intent={profile['last_intent']}")
	return "; ".join(parts) if parts else "No profile memory available."


async def apply_profile_patch(user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
	"""Apply partial profile patch and persist merged result.

	Significance:
		Supports structured profile intake updates without discarding existing memory.
	"""
	existing = await get_user_profile(user_id)
	merged_skills = _normalized_set([*existing.get("skills", []), *patch.get("skills", [])])
	merged_interests = _normalized_set([*existing.get("interests", []), *patch.get("interests", [])])

	document = {
		"user_id": user_id,
		"skills": merged_skills,
		"interests": merged_interests,
		"target_role": patch.get("target_role") or existing.get("target_role"),
		"target_companies": existing.get("target_companies", []),
		"networking_metrics": existing.get("networking_metrics", {}),
		"intent_counts": existing.get("intent_counts", {}),
		"last_intent": existing.get("last_intent"),
		"last_intent_confidence": existing.get("last_intent_confidence", 0.0),
		"education_level": patch.get("education_level") or existing.get("education_level"),
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}
	try:
		collection = get_user_profile_collection()
		await collection.update_one({"user_id": user_id}, {"$set": document}, upsert=True)
		_profile_fallback[user_id] = document
	except Exception:
		logger.exception("Failed to apply profile patch in MongoDB for user_id=%s", user_id)
		_profile_fallback[user_id] = document
	return document


async def clear_user_profile(user_id: str) -> bool:
	"""Delete user profile from MongoDB and fallback cache.

	Returns:
		True when any profile record was removed from primary or fallback storage.

	Used by:
		User-facing profile reset/delete flows.
	"""
	deleted = False
	try:
		collection = get_user_profile_collection()
		result = await collection.delete_one({"user_id": user_id})
		deleted = bool(result.deleted_count)
	except Exception:
		logger.exception("Failed to clear user profile in MongoDB for user_id=%s", user_id)

	if user_id in _profile_fallback:
		deleted = True
		_profile_fallback.pop(user_id, None)

	return deleted

