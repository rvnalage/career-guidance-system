"""Recommendation API routes for generation, explanation, feedback, and history."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from typing import Annotated

from fastapi import APIRouter, Depends

from app.database.models import User
from app.dependencies import get_current_user
from app.schemas.recommendation import (
	RecommendationExplainRequest,
	RecommendationExplainResponse,
	RecommendationFeedbackRequest,
	RecommendationHistoryItem,
	RecommendationHistoryResponse,
	RecommendationRequest,
	RecommendationResponse,
)
from app.services.psychometric_service import get_user_psychometric_profile
from app.services.recommendation_service import (
	clear_recommendation_history,
	generate_recommendation_explanations,
	generate_career_recommendations,
	get_personalization_profile,
	get_recommendation_history,
	get_recommendation_feedback,
	save_recommendation_feedback,
	save_recommendation_snapshot,
)
from app.xai.explainer import get_explainer_runtime_status

router = APIRouter()


async def _enrich_interests_with_psychometric(user_id: str, interests: list[str]) -> list[str]:
	"""Merge stored psychometric domains into request interests without duplicating entries."""
	profile = await get_user_psychometric_profile(user_id)
	if not profile:
		return interests

	recommended_domains = [str(domain).strip() for domain in profile.get("recommended_domains", []) if str(domain).strip()]
	if not recommended_domains:
		return interests

	merged = list(interests)
	for domain in recommended_domains:
		if domain.lower() not in {item.lower() for item in merged}:
			merged.append(domain)
	return merged


@router.post("/generate", response_model=RecommendationResponse)
async def generate_recommendations(
	payload: RecommendationRequest,
	current_user: Annotated[User, Depends(get_current_user)],
) -> RecommendationResponse:
	"""Generate personalized career recommendations for the authenticated user."""
	enriched_interests = await _enrich_interests_with_psychometric(current_user.id, payload.interests)
	payload = RecommendationRequest(
		user_id=current_user.id,
		interests=enriched_interests,
		skills=payload.skills,
		education_level=payload.education_level,
	)
	profile = await get_personalization_profile(current_user.id)
	recommendations = await generate_career_recommendations(payload, personalization_profile=profile)
	await save_recommendation_snapshot(current_user.id, recommendations)
	return RecommendationResponse(recommendations=recommendations)


@router.post("/explain/me", response_model=RecommendationExplainResponse)
async def explain_recommendations_me(
	payload: RecommendationExplainRequest,
	current_user: Annotated[User, Depends(get_current_user)],
) -> RecommendationExplainResponse:
	"""Return recommendation explanations with feature-level XAI contributions."""
	enriched_interests = await _enrich_interests_with_psychometric(current_user.id, payload.interests)
	payload = RecommendationExplainRequest(
		interests=enriched_interests,
		skills=payload.skills,
		education_level=payload.education_level,
	)
	profile = await get_personalization_profile(current_user.id)
	explanations = generate_recommendation_explanations(payload, personalization_profile=profile)
	return RecommendationExplainResponse(explanations=explanations)


@router.post("/feedback/me")
async def recommendation_feedback_me(
	payload: RecommendationFeedbackRequest,
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	"""Store structured user feedback to support future recommendation personalization."""
	await save_recommendation_feedback(current_user.id, payload)
	return {"user_id": current_user.id, "message": "Feedback recorded"}


@router.get("/feedback/me")
async def get_recommendation_feedback_me(
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	"""Return the authenticated user's stored recommendation feedback entries."""
	items = await get_recommendation_feedback(current_user.id)
	return {"user_id": current_user.id, "feedback": items}


@router.get("/xai/status")
async def recommendation_xai_status(
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	"""Expose the current runtime explainer mode for diagnostics and demos."""
	status = get_explainer_runtime_status()
	status["user_id"] = current_user.id
	return status


@router.get("/history/me", response_model=RecommendationHistoryResponse)
async def recommendation_history_me(
	current_user: Annotated[User, Depends(get_current_user)],
) -> RecommendationHistoryResponse:
	"""Return the authenticated user's stored recommendation history."""
	history = await get_recommendation_history(current_user.id)
	items = [RecommendationHistoryItem.model_validate(item) for item in history]
	return RecommendationHistoryResponse(history=items)


@router.delete("/history/me")
async def clear_recommendation_history_me(
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	"""Clear recommendation history for the authenticated user."""
	deleted_count = await clear_recommendation_history(current_user.id)
	return {
		"user_id": current_user.id,
		"deleted_count": deleted_count,
		"message": "Recommendation history cleared",
	}

