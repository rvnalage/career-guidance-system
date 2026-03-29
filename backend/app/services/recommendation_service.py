"""Recommendation scoring, explanation, feedback, and history persistence helpers.

This module implements a deterministic recommendation engine that combines skills,
interests, education fit, and feedback-derived personalization, then exposes both
plain recommendations and XAI-friendly contribution outputs.
"""

from datetime import datetime, timezone

from app.schemas.recommendation import (
	CareerRecommendation,
	FeatureContribution,
	RecommendationExplainRequest,
	RecommendationExplanation,
	RecommendationFeedbackRequest,
	RecommendationRequest,
)
from app.database.mongo_db import get_feedback_collection, get_recommendation_collection
from app.utils.constants import CAREER_PATHS, EDUCATION_ORDER
from app.utils.logger import get_logger
from app.xai.explainer import explain_recommendation

_recommendation_fallback: dict[str, list[dict]] = {}
_feedback_fallback: dict[str, list[dict]] = {}
logger = get_logger(__name__)


def _normalize(items: list[str]) -> set[str]:
	"""Return lowercase non-empty values for set-based matching operations."""
	return {item.strip().lower() for item in items if item and item.strip()}


def _safe_ratio(matches: int, total: int) -> float:
	"""Avoid division errors when a role definition has an empty feature list."""
	if total <= 0:
		return 0.0
	return matches / total


def _education_score(user_education: str, required_education: str) -> float:
	"""Convert education alignment into a bounded compatibility score."""
	user_rank = EDUCATION_ORDER.get(user_education.strip().lower(), 0)
	required_rank = EDUCATION_ORDER.get(required_education.strip().lower(), 0)
	if user_rank == 0 or required_rank == 0:
		return 0.2
	if user_rank >= required_rank:
		return 1.0
	if user_rank + 1 == required_rank:
		return 0.6
	return 0.2


def _reason_text(skill_matches: int, interest_matches: int, required_skills: int) -> str:
	"""Generate a short human-readable explanation for a recommendation result."""
	return (
		f"Matched {skill_matches}/{required_skills} core skills and "
		f"{interest_matches} related interests."
	)


def _bounded(value: float, low: float, high: float) -> float:
	"""Clamp a numeric value into the requested closed interval."""
	return max(low, min(high, value))


def _default_personalization_profile() -> dict[str, dict]:
	"""Return neutral personalization weights and no role bonuses."""
	return {
		"role_bonus": {},
		"weights": {
			"skill": 0.5,
			"interest": 0.3,
			"education": 0.2,
		},
	}


def _compute_personalization_profile(feedback_items: list[dict]) -> dict[str, dict]:
	"""Translate recommendation feedback into per-role bonuses and feature weight shifts."""
	profile = _default_personalization_profile()
	role_bonus = profile["role_bonus"]
	weights = profile["weights"]

	for item in feedback_items:
		role = str(item.get("role", "")).strip()
		helpful = bool(item.get("helpful", False))
		rating = int(item.get("rating", 3))
		tags = [str(tag).lower().strip() for tag in item.get("feedback_tags", [])]

		impact = (rating - 3) / 10.0
		if helpful:
			impact += 0.04
		else:
			impact -= 0.04

		if role:
			role_bonus[role] = _bounded(float(role_bonus.get(role, 0.0)) + impact, -0.2, 0.2)

		if "skills" in tags:
			weights["skill"] = _bounded(weights["skill"] + impact * 0.5, 0.2, 0.7)
		if "interests" in tags:
			weights["interest"] = _bounded(weights["interest"] + impact * 0.5, 0.15, 0.6)
		if "education" in tags:
			weights["education"] = _bounded(weights["education"] + impact * 0.5, 0.1, 0.5)

	total = weights["skill"] + weights["interest"] + weights["education"]
	if total > 0:
		weights["skill"] = round(weights["skill"] / total, 4)
		weights["interest"] = round(weights["interest"] / total, 4)
		weights["education"] = round(weights["education"] / total, 4)

	return profile


async def get_personalization_profile(user_id: str) -> dict[str, dict]:
	"""Load a user's derived personalization profile from feedback history."""
	try:
		collection = get_feedback_collection()
		cursor = collection.find({"user_id": user_id}).sort("created_at", 1)
		feedback_items = await cursor.to_list(length=500)
		for item in feedback_items:
			item.pop("_id", None)
	except Exception:
		logger.exception("Failed to load recommendation feedback for user_id=%s", user_id)
		feedback_items = _feedback_fallback.get(user_id, [])

	if not feedback_items:
		return _default_personalization_profile()
	return _compute_personalization_profile(feedback_items)


def _score_paths(
	payload: RecommendationRequest,
	personalization_profile: dict[str, dict] | None = None,
) -> list[tuple[float, CareerRecommendation, list[FeatureContribution]]]:
	"""Score all supported career paths and return ranked recommendations with raw contributions."""
	user_skills = _normalize(payload.skills)
	user_interests = _normalize(payload.interests)
	profile = personalization_profile or _default_personalization_profile()
	weights = profile.get("weights", _default_personalization_profile()["weights"])
	role_bonus_map = profile.get("role_bonus", {})

	weighted_recommendations: list[tuple[float, CareerRecommendation, list[FeatureContribution]]] = []

	for path in CAREER_PATHS:
		role = path["role"]
		required_skills = _normalize(path["required_skills"])
		related_interests = _normalize(path["related_interests"])

		skill_matches = len(user_skills.intersection(required_skills))
		interest_matches = len(user_interests.intersection(related_interests))

		skill_score = _safe_ratio(skill_matches, len(required_skills))
		interest_score = _safe_ratio(interest_matches, len(related_interests))
		education_score = _education_score(payload.education_level, path["min_education"])
		personalization_bonus = _bounded(float(role_bonus_map.get(role, 0.0)), -0.2, 0.2)

		# Weighted aggregate tuned for student career suitability scoring + feedback personalization.
		final_score = (
			(float(weights.get("skill", 0.5)) * skill_score)
			+ (float(weights.get("interest", 0.3)) * interest_score)
			+ (float(weights.get("education", 0.2)) * education_score)
			+ personalization_bonus
		)
		final_score = _bounded(final_score, 0.0, 1.0)

		recommendation = CareerRecommendation(
			role=role,
			confidence=round(final_score, 4),
			reason=_reason_text(skill_matches, interest_matches, len(required_skills)),
		)
		contributions = [
			FeatureContribution(feature="skill_match", value=round(skill_score, 4)),
			FeatureContribution(feature="interest_match", value=round(interest_score, 4)),
			FeatureContribution(feature="education_fit", value=round(education_score, 4)),
			FeatureContribution(feature="personalization_bonus", value=round(personalization_bonus, 4)),
		]
		weighted_recommendations.append((final_score, recommendation, contributions))

	weighted_recommendations.sort(key=lambda item: item[0], reverse=True)
	return weighted_recommendations


def generate_career_recommendations(
	payload: RecommendationRequest,
	top_k: int = 3,
	personalization_profile: dict[str, dict] | None = None,
) -> list[CareerRecommendation]:
	"""Return the top-k ranked career recommendations for a user profile."""
	weighted_recommendations = _score_paths(payload, personalization_profile=personalization_profile)
	return [item[1] for item in weighted_recommendations[:top_k]]


def generate_recommendation_explanations(
	payload: RecommendationExplainRequest,
	personalization_profile: dict[str, dict] | None = None,
	top_k: int = 3,
) -> list[RecommendationExplanation]:
	"""Return top-k recommendations together with explainer-specific feature contributions."""
	request_payload = RecommendationRequest(
		user_id="",
		interests=payload.interests,
		skills=payload.skills,
		education_level=payload.education_level,
	)
	weighted_recommendations = _score_paths(request_payload, personalization_profile=personalization_profile)
	profile = personalization_profile or _default_personalization_profile()
	weights = profile.get("weights", _default_personalization_profile()["weights"])
	explanations: list[RecommendationExplanation] = []
	for _, recommendation, contributions in weighted_recommendations[:top_k]:
		feature_map = {item.feature: item.value for item in contributions}
		explained_contributions, label = explain_recommendation(feature_map, weights)
		xai_contributions = [
			FeatureContribution(feature=feature, value=value)
			for feature, value in explained_contributions
		]
		explanations.append(
			RecommendationExplanation(
				role=recommendation.role,
				confidence=recommendation.confidence,
				contributions=xai_contributions,
				label=label,
			)
		)
	return explanations


async def save_recommendation_snapshot(user_id: str, recommendations: list[CareerRecommendation]) -> dict:
	"""Persist a generated recommendation set so dashboard and history endpoints can replay it."""
	document = {
		"user_id": user_id,
		"recommendations": [item.model_dump() for item in recommendations],
		"generated_at": datetime.now(timezone.utc).isoformat(),
	}
	try:
		collection = get_recommendation_collection()
		await collection.insert_one(document)
	except Exception:
		logger.exception("Failed to save recommendation snapshot for user_id=%s", user_id)
		_recommendation_fallback.setdefault(user_id, []).append(document)
	return document


async def get_recommendation_history(user_id: str, limit: int = 10) -> list[dict]:
	"""Return recent recommendation snapshots in newest-first order."""
	try:
		collection = get_recommendation_collection()
		cursor = collection.find({"user_id": user_id}).sort("generated_at", -1).limit(limit)
		documents = await cursor.to_list(length=limit)
		for item in documents:
			item.pop("_id", None)
		return documents
	except Exception:
		logger.exception("Failed to load recommendation history for user_id=%s", user_id)
		return list(reversed(_recommendation_fallback.get(user_id, [])[-limit:]))


async def clear_recommendation_history(user_id: str) -> int:
	"""Delete stored recommendation history and return the number of removed items."""
	deleted_count = 0
	try:
		collection = get_recommendation_collection()
		result = await collection.delete_many({"user_id": user_id})
		deleted_count = int(result.deleted_count)
	except Exception:
		logger.exception("Failed to clear recommendation history for user_id=%s", user_id)
		deleted_count = len(_recommendation_fallback.get(user_id, []))

	_recommendation_fallback[user_id] = []
	return deleted_count


async def save_recommendation_feedback(user_id: str, payload: RecommendationFeedbackRequest) -> dict:
	"""Store user feedback used later to personalize recommendation scoring weights."""
	document = {
		"user_id": user_id,
		"role": payload.role,
		"helpful": payload.helpful,
		"rating": max(1, min(5, payload.rating)),
		"feedback_tags": payload.feedback_tags,
		"created_at": datetime.now(timezone.utc).isoformat(),
	}
	try:
		collection = get_feedback_collection()
		await collection.insert_one(document)
	except Exception:
		logger.exception("Failed to save recommendation feedback for user_id=%s", user_id)
		_feedback_fallback.setdefault(user_id, []).append(document)
	return document
