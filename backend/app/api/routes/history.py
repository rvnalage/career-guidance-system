"""History API routes for reading and clearing persisted chat conversations."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.database.models import User
from app.dependencies import get_current_user
from app.services.history_service import clear_user_history, get_user_history

router = APIRouter()


@router.get("/me")
async def get_history_me(
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	"""Return the authenticated user's stored chat message history."""
	messages = await get_user_history(current_user.id)
	return {"user_id": current_user.id, "messages": messages}


@router.delete("/me")
async def clear_history_me(
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	"""Delete the authenticated user's chat history and return the removal count."""
	deleted_count = await clear_user_history(current_user.id)
	return {
		"user_id": current_user.id,
		"deleted_count": deleted_count,
		"message": "Chat history cleared",
	}
