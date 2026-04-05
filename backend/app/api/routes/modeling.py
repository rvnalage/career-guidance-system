"""Routes for inspecting phase-2 model runtime status."""

from fastapi import APIRouter

from app.services.model_runtime_service import get_model_runtime_status

router = APIRouter()


@router.get("/status")
async def modeling_status() -> dict[str, object]:
	"""Return enablement and artifact presence for optional modelized components."""
	return get_model_runtime_status()
