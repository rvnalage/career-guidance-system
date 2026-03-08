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
	save_recommendation_feedback,
	save_recommendation_snapshot,
)

router = APIRouter()


async def _enrich_interests_with_psychometric(user_id: str, interests: list[str]) -> list[str]:
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
	enriched_interests = await _enrich_interests_with_psychometric(current_user.id, payload.interests)
	payload = RecommendationRequest(
		user_id=current_user.id,
		interests=enriched_interests,
		skills=payload.skills,
		education_level=payload.education_level,
	)
	profile = await get_personalization_profile(current_user.id)
	recommendations = generate_career_recommendations(payload, personalization_profile=profile)
	await save_recommendation_snapshot(current_user.id, recommendations)
	return RecommendationResponse(recommendations=recommendations)


@router.post("/explain/me", response_model=RecommendationExplainResponse)
async def explain_recommendations_me(
	payload: RecommendationExplainRequest,
	current_user: Annotated[User, Depends(get_current_user)],
) -> RecommendationExplainResponse:
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
	await save_recommendation_feedback(current_user.id, payload)
	return {"user_id": current_user.id, "message": "Feedback recorded"}


@router.get("/history/me", response_model=RecommendationHistoryResponse)
async def recommendation_history_me(
	current_user: Annotated[User, Depends(get_current_user)],
) -> RecommendationHistoryResponse:
	history = await get_recommendation_history(current_user.id)
	items = [RecommendationHistoryItem.model_validate(item) for item in history]
	return RecommendationHistoryResponse(history=items)


@router.delete("/history/me")
async def clear_recommendation_history_me(
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	deleted_count = await clear_recommendation_history(current_user.id)
	return {
		"user_id": current_user.id,
		"deleted_count": deleted_count,
		"message": "Recommendation history cleared",
	}
