"""Planner outcome telemetry storage and recalibration helpers.

Captures user-level interaction outcomes (helpfulness, next-step usage, click-through)
and derives intent-wise calibration offsets so planner outcome scores can adapt
to real observed success signals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.database.mongo_db import get_outcome_collection
from app.utils.logger import get_logger


logger = get_logger(__name__)

_outcome_fallback: list[dict[str, Any]] = []


def _compute_success_score(payload: dict[str, Any]) -> int:
	"""Compute a deterministic success score from outcome interaction fields."""
	helpful = bool(payload.get("helpful", False))
	accepted = bool(payload.get("accepted_next_step", False))
	clicked = bool(payload.get("clicked_suggestion", False))
	rating_raw = payload.get("rating")
	try:
		rating = int(rating_raw) if rating_raw is not None else 3
	except Exception:
		rating = 3
	rating = max(1, min(5, rating))

	score = 35
	score += 30 if helpful else -10
	score += 20 if accepted else 0
	score += 10 if clicked else 0
	score += (rating - 3) * 8
	return max(0, min(100, score))


async def record_chat_outcome(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
	"""Persist one chat outcome event and return the stored document."""
	document = {
		"user_id": user_id,
		"plan_id": str(payload.get("plan_id") or "").strip() or None,
		"intent": str(payload.get("intent") or "career_assessment").strip().lower(),
		"helpful": bool(payload.get("helpful", False)),
		"accepted_next_step": bool(payload.get("accepted_next_step", False)),
		"clicked_suggestion": bool(payload.get("clicked_suggestion", False)),
		"rating": payload.get("rating"),
		"source": str(payload.get("source") or "chat").strip().lower(),
		"success_score": _compute_success_score(payload),
		"created_at": datetime.now(timezone.utc).isoformat(),
	}
	try:
		collection = get_outcome_collection()
		await collection.insert_one(document)
	except Exception:
		logger.exception("Failed to persist planner outcome telemetry for user_id=%s", user_id)
		_outcome_fallback.append(document)
	return document


async def get_intent_recalibration(user_id: str, intents: list[str]) -> dict[str, int]:
	"""Return intent-specific score offsets derived from historical outcome events.

	Offsets are bounded to [-12, +12] so learned feedback nudges, but does not
	overwrite, deterministic planner quality scoring.
	"""
	if not intents:
		return {}
	intent_set = {str(item).strip().lower() for item in intents if str(item).strip()}
	if not intent_set:
		return {}

	events: list[dict[str, Any]] = []
	try:
		collection = get_outcome_collection()
		cursor = collection.find(
			{"user_id": user_id, "intent": {"$in": list(intent_set)}},
			{"_id": 0, "intent": 1, "success_score": 1},
		).sort("created_at", -1).limit(120)
		events = await cursor.to_list(length=120)
	except Exception:
		logger.exception("Failed to load planner outcome telemetry for user_id=%s", user_id)
		events = [
			item for item in _outcome_fallback
			if item.get("user_id") == user_id and str(item.get("intent", "")).lower() in intent_set
		][-120:]

	per_intent: dict[str, list[int]] = {}
	for event in events:
		intent = str(event.get("intent") or "").lower()
		if intent not in intent_set:
			continue
		score_raw = event.get("success_score")
		try:
			score = int(score_raw)
		except Exception:
			continue
		per_intent.setdefault(intent, []).append(score)

	offsets: dict[str, int] = {}
	for intent_name in intent_set:
		values = per_intent.get(intent_name, [])
		if not values:
			offsets[intent_name] = 0
			continue
		avg_score = sum(values) / len(values)
		# Center around 65 as neutral planner target.
		offset = int(round((avg_score - 65) / 3))
		offsets[intent_name] = max(-12, min(12, offset))
	return offsets
