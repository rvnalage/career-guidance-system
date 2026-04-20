"""Recommendation scoring, explanation, feedback, and history persistence helpers.

This module implements a deterministic recommendation engine that combines skills,
interests, education fit, and feedback-derived personalization, then exposes both
plain recommendations and XAI-friendly contribution outputs.
"""

# Developer Onboarding Notes:
# - Layer: recommendation engine service
# - Role in system: Scores career-role fit, adds explanations, and stores recommendation/feedback memory.
# - Main callers: `app.api.routes.recommendation` and planner orchestration in `app.services.planner_service`.
# - Reading tip: Start from `generate_career_recommendations`, then inspect `_score_paths` and personalization helpers.


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
from app.config import settings
from app.utils.constants import CAREER_PATHS, EDUCATION_ORDER, SKILL_RESOURCES
from app.utils.logger import get_logger
from app.services.user_model_service import score_role_preferences
from app.services.cf_service import score_cf_roles
from app.services.bandit_service import record_feedback as bandit_record_feedback, rerank_recommendations
from app.services.llm_service import generate_recommendation_reason_via_llm
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


async def _reason_text_with_llm(
	user_skills: list[str],
	user_interests: list[str],
	role: str,
	skill_matches: int,
	total_required_skills: int,
	interest_matches: int,
	education_fit: float,
	confidence: float,
) -> str:
	"""Try to generate rich LLM explanation, fall back to numeric summary if unavailable."""
	llm_reason = await generate_recommendation_reason_via_llm(
		user_role=role,
		user_skills=user_skills,
		user_interests=user_interests,
		matched_skills=skill_matches,
		total_required_skills=total_required_skills,
		interest_matches=interest_matches,
		education_fit=education_fit,
		confidence_score=confidence,
	)
	if llm_reason:
		return llm_reason
	return _reason_text(skill_matches, interest_matches, total_required_skills)


def _bounded(value: float, low: float, high: float) -> float:
	"""Clamp a numeric value into the requested closed interval."""
	return max(low, min(high, value))


def _missing_skills_for_role(role: str, user_skills: list[str]) -> list[str]:
	"""Return up to 3 missing required skills for a given role based on current user skills."""
	role_data = next((item for item in CAREER_PATHS if item["role"] == role), None)
	if not role_data:
		return []
	user_skill_set = {str(skill).strip().lower() for skill in user_skills if str(skill).strip()}
	missing: list[str] = []
	for required in role_data["required_skills"]:
		required_norm = str(required).strip().lower()
		if required_norm and required_norm not in user_skill_set:
			missing.append(str(required).strip())
	return missing[:3]


def _upgrade_suggestions_for_gaps(missing_skills: list[str]) -> list[str]:
	"""Map missing skills to known upgrade resources for UI-ready display."""
	suggestions: list[str] = []
	for skill in missing_skills:
		resource = SKILL_RESOURCES.get(str(skill).strip().lower())
		if resource:
			suggestions.append(f"{skill}: {resource}")
	return suggestions[:3]


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
	"""Convert feedback history into role bonuses and dynamic feature weights.

	Significance:
		Implements lightweight online personalization without retraining a model.
		Positive/negative feedback nudges role priors and scoring weights.
	"""
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
	"""Load and assemble personalization profile for one user.

	Returns:
		Dictionary with role bonuses, normalized weights, and optional CF role scores.

	Significance:
		Single entrypoint that fuses heuristic feedback shaping + optional user-model and
		collaborative-filtering signals used by `_score_paths`.

	Used by:
		Recommendation endpoints and planner-driven recommendation flow.
	"""
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
	profile = _compute_personalization_profile(feedback_items)
	roles = [path["role"] for path in CAREER_PATHS]
	model_scores = score_role_preferences(feedback_items, roles)
	if model_scores:
		# Blend model role affinity into existing heuristic role bonuses while preserving hard bounds.
		for role, score in model_scores.items():
			existing = float(profile["role_bonus"].get(role, 0.0))
			centered = (float(score) - 0.5) * 2.0  # map [0,1] -> [-1,1]
			model_bonus = centered * 0.1 * max(0.0, min(1.0, settings.user_preference_model_alpha))
			profile["role_bonus"][role] = _bounded(existing + model_bonus, -0.2, 0.2)
	# CF hybrid: store raw CF scores separately so _score_paths can expose them as an
	# explicit explainable contribution (do NOT fold into role_bonus to avoid double-counting).
	profile["cf_scores"] = score_cf_roles(user_id, roles)
	return profile


def _score_paths(
	payload: RecommendationRequest,
	personalization_profile: dict[str, dict] | None = None,
) -> list[tuple[float, CareerRecommendation, list[FeatureContribution]]]:
	"""Score all supported roles and return ranked recommendations with contributions.

	Args:
		payload: User profile signals (skills, interests, education).
		personalization_profile: Optional precomputed profile; defaults to neutral weights.

	Returns:
		List of tuples: `(final_score, recommendation, feature_contributions)` sorted descending.

	Significance:
		Core deterministic scorer for recommendation quality and explainability.
		Every downstream recommendation/explanation API depends on this function.
	"""
	user_skills = _normalize(payload.skills)
	user_interests = _normalize(payload.interests)
	profile = personalization_profile or _default_personalization_profile()
	weights = profile.get("weights", _default_personalization_profile()["weights"])
	role_bonus_map = profile.get("role_bonus", {})
	cf_scores_map: dict[str, float] = profile.get("cf_scores", {})

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

		# CF additive term â€” kept separate from personalization_bonus for XAI transparency.
		cf_raw = float(cf_scores_map.get(role, 0.5))
		alpha = max(0.0, min(1.0, settings.cf_model_alpha))
		cf_contribution = _bounded((cf_raw - 0.5) * 2.0 * 0.1 * alpha, -0.1, 0.1)

		# Weighted aggregate tuned for student career suitability scoring + feedback personalization.
		final_score = (
			(float(weights.get("skill", 0.5)) * skill_score)
			+ (float(weights.get("interest", 0.3)) * interest_score)
			+ (float(weights.get("education", 0.2)) * education_score)
			+ personalization_bonus
			+ cf_contribution
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
			FeatureContribution(feature="cf_score", value=round(cf_raw, 4)),
		]
		weighted_recommendations.append((final_score, recommendation, contributions))

	weighted_recommendations.sort(key=lambda item: item[0], reverse=True)
	return weighted_recommendations


async def generate_career_recommendations(
	payload: RecommendationRequest,
	top_k: int = 3,
	personalization_profile: dict[str, dict] | None = None,
) -> list[CareerRecommendation]:
	"""Generate top-k recommendations, then enrich each with gaps and rationale.

	Significance:
		Primary service API for role suggestions. Combines deterministic ranking,
		bandit rerank, skill-gap extraction, and optional LLM explanation upgrade.

	Used by:
		Recommendation route handlers and planner recommendation tool path.
	"""
	weighted_recommendations = _score_paths(payload, personalization_profile=personalization_profile)
	top_candidates = [item[1] for item in weighted_recommendations[:top_k]]
	reranked_roles = rerank_recommendations([r.role for r in top_candidates])
	role_to_rec = {r.role: r for r in top_candidates}
	recs = [role_to_rec[role] for role in reranked_roles if role in role_to_rec]
	
	# Enrich recommendations with LLM-generated reasons if available
	for rec in recs:
		missing_skills = _missing_skills_for_role(rec.role, payload.skills)
		rec.skill_gaps = missing_skills
		rec.upgrade_suggestions = _upgrade_suggestions_for_gaps(missing_skills)
		if weighted_recommendations:
			for score, orig_rec, _ in weighted_recommendations:
				if orig_rec.role == rec.role:
					# Get corresponding skill/interest/education data
					user_skills = [str(s).strip().lower() for s in payload.skills]
					user_interests = [str(i).strip().lower() for i in payload.interests]
					role_data = next((p for p in CAREER_PATHS if p["role"] == rec.role), None)
					if role_data:
						role_skills = {s.lower() for s in role_data["required_skills"]}
						role_interests = {i.lower() for i in role_data["related_interests"]}
						skill_matches = len(set(user_skills) & role_skills)
						interest_matches = len(set(user_interests) & role_interests)
						edu_fit = _education_score(payload.education_level, role_data["min_education"])
						llm_reason = await _reason_text_with_llm(
							payload.skills,
							payload.interests,
							rec.role,
							skill_matches,
							len(role_data["required_skills"]),
							interest_matches,
							edu_fit,
							rec.confidence,
						)
						if llm_reason:
							rec.reason = llm_reason
					break
	
	return recs


def generate_recommendation_explanations(
	payload: RecommendationExplainRequest,
	personalization_profile: dict[str, dict] | None = None,
	top_k: int = 3,
) -> list[RecommendationExplanation]:
	"""Return recommendation explanations with XAI-formatted contribution labels.

	Significance:
		Bridges raw scoring features to user-facing explainability artifacts.
	"""
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
	"""Persist generated recommendations for history/audit replay.

	Used by:
		Recommendation create endpoints after successful generation.
	"""
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


async def get_recommendation_feedback(user_id: str) -> list[dict]:
	"""Return all stored feedback entries for a user in newest-first order."""
	try:
		collection = get_feedback_collection()
		cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
		items = await cursor.to_list(length=500)
		for item in items:
			item.pop("_id", None)
		return items
	except Exception:
		logger.exception("Failed to load recommendation feedback for user_id=%s", user_id)
		return list(reversed(_feedback_fallback.get(user_id, [])))


async def save_recommendation_feedback(user_id: str, payload: RecommendationFeedbackRequest) -> dict:
	"""Store recommendation feedback and update online bandit statistics.

	Significance:
		Feedback loop for both future personalization profile computation and
		exploration-exploitation updates in the bandit reranker.
	"""
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
	# Update bandit arm statistics for online learning.
	bandit_record_feedback(payload.role, payload.helpful, document["rating"])
	return document

