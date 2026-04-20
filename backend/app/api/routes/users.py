"""User profile routes for reading and updating authenticated account details."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models import User
from app.dependencies import get_current_user, get_database_session
from app.schemas.user import UserProfile
from app.services.user_service import to_user_profile, update_user_profile, reset_user_data

router = APIRouter()


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
	current_user: Annotated[User, Depends(get_current_user)],
) -> UserProfile:
	"""Return the current authenticated user's profile in API schema form."""
	return to_user_profile(current_user)


@router.put("/me", response_model=UserProfile)
async def update_current_user(
	payload: UserProfile,
	current_user: Annotated[User, Depends(get_current_user)],
	db: Annotated[Session, Depends(get_database_session)],
) -> UserProfile:
	"""Update the current user's persisted profile fields in the relational store."""
	try:
		updated_user = update_user_profile(db, current_user, payload)
	except SQLAlchemyError as exc:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail="Database unavailable. Please try again later.",
		) from exc
	return to_user_profile(updated_user)


@router.delete("/data/me")
async def reset_user_data_endpoint(
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	"""Reset all user data including chat history, recommendations, and psychometric profile."""
	return await reset_user_data(current_user.id)

