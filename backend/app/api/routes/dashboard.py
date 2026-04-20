"""Dashboard API routes for summary and report views over user activity."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from app.database.models import User
from app.dependencies import get_current_user
from app.services.history_service import get_user_history
from app.services.recommendation_service import get_recommendation_history

router = APIRouter()


async def _build_summary_for_user(user_id: str) -> tuple[dict[str, object], list[dict], list[dict]]:
	"""Assemble dashboard summary data from chat and recommendation histories."""
	history = await get_user_history(user_id, limit=100)
	recommendation_history = await get_recommendation_history(user_id, limit=10)
	top_roles: list[str] = []
	if recommendation_history:
		top_roles = [item["role"] for item in recommendation_history[0].get("recommendations", [])[:3]]

	profile_completion = min(100, 30 + (5 * len(top_roles)) + min(40, len(history)))
	summary = {
		"user_id": user_id,
		"profile_completion": profile_completion,
		"top_roles": top_roles,
		"next_action": "Generate new recommendations" if not top_roles else "Start learning path for top role",
	}
	return summary, history, recommendation_history


@router.get("/summary/me")
async def get_dashboard_summary(
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	"""Return the lightweight dashboard summary for the authenticated user."""
	summary, _, _ = await _build_summary_for_user(current_user.id)
	return summary


@router.get("/report/me")
async def get_dashboard_report(
	current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, object]:
	"""Return a detailed dashboard report including recent chat and recommendation history."""
	summary, history, recommendation_history = await _build_summary_for_user(current_user.id)
	recent_chat = history[-10:]
	return {
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"summary": summary,
		"recent_chat_messages": recent_chat,
		"recommendation_history": recommendation_history,
		"latest_recommendations": recommendation_history[0].get("recommendations", []) if recommendation_history else [],
	}

