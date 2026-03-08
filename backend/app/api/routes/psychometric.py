from typing import Annotated

from fastapi import APIRouter, Depends

from app.database.models import User
from app.dependencies import get_current_user
from app.schemas.psychometric import PsychometricRequest, PsychometricResponse
from app.services.psychometric_service import (
	get_user_psychometric_profile,
	save_user_psychometric_profile,
	score_psychometric,
)

router = APIRouter()


@router.post("/score", response_model=PsychometricResponse)
async def score_psychometric_test(payload: PsychometricRequest) -> PsychometricResponse:
	normalized_scores, top_traits, recommended_domains = score_psychometric(payload)
	return PsychometricResponse(
		normalized_scores=normalized_scores,
		top_traits=top_traits,
		recommended_domains=recommended_domains,
	)


@router.post("/score/me", response_model=PsychometricResponse)
async def score_psychometric_test_me(
	payload: PsychometricRequest,
	current_user: Annotated[User, Depends(get_current_user)],
) -> PsychometricResponse:
	document = await save_user_psychometric_profile(current_user.id, payload)
	return PsychometricResponse(
		normalized_scores=document.get("normalized_scores", {}),
		top_traits=document.get("top_traits", []),
		recommended_domains=document.get("recommended_domains", []),
	)


@router.get("/profile/me", response_model=PsychometricResponse)
async def psychometric_profile_me(
	current_user: Annotated[User, Depends(get_current_user)],
) -> PsychometricResponse:
	document = await get_user_psychometric_profile(current_user.id)
	if not document:
		return PsychometricResponse(normalized_scores={}, top_traits=[], recommended_domains=[])

	return PsychometricResponse(
		normalized_scores=document.get("normalized_scores", {}),
		top_traits=document.get("top_traits", []),
		recommended_domains=document.get("recommended_domains", []),
	)
