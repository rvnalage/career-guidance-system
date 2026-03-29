"""Profile-memory helpers used to persist and reuse user context across chat turns.

The stored profile is intentionally lightweight: skills, interests, target role,
and routing history. MongoDB is preferred, but an in-memory fallback keeps the
chat flow usable during tests and local development.
"""

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
	"""Combine request context with persisted profile memory into a single routing context."""
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


async def get_user_profile(user_id: str) -> dict[str, Any]:
	"""Load a user profile from MongoDB or fall back to the in-memory cache."""
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
	"""Persist incremental profile updates extracted from the latest chat turn."""
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
		"intent_counts": intent_counts,
		"last_intent": intent,
		"last_intent_confidence": round(float(intent_confidence), 4),
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}
	try:
		collection = get_user_profile_collection()
		await collection.update_one({"user_id": user_id}, {"$set": document}, upsert=True)
	except Exception:
		# Tests and local development can operate without Mongo because the fallback cache mirrors the stored shape.
		logger.exception("Failed to persist user profile to MongoDB for user_id=%s", user_id)
		_profile_fallback[user_id] = document
	return document


def summarize_profile(profile: dict[str, Any] | None) -> str:
	"""Convert stored profile fields into a compact single-line prompt summary."""
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
	"""Merge structured profile fields into persisted user profile memory."""
	existing = await get_user_profile(user_id)
	merged_skills = _normalized_set([*existing.get("skills", []), *patch.get("skills", [])])
	merged_interests = _normalized_set([*existing.get("interests", []), *patch.get("interests", [])])

	document = {
		"user_id": user_id,
		"skills": merged_skills,
		"interests": merged_interests,
		"target_role": patch.get("target_role") or existing.get("target_role"),
		"target_companies": existing.get("target_companies", []),
		"intent_counts": existing.get("intent_counts", {}),
		"last_intent": existing.get("last_intent"),
		"last_intent_confidence": existing.get("last_intent_confidence", 0.0),
		"education_level": patch.get("education_level") or existing.get("education_level"),
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}
	try:
		collection = get_user_profile_collection()
		await collection.update_one({"user_id": user_id}, {"$set": document}, upsert=True)
	except Exception:
		logger.exception("Failed to apply profile patch in MongoDB for user_id=%s", user_id)
		_profile_fallback[user_id] = document
	return document
