"""Diagnostics routes for inspecting the optional LLM runtime configuration."""

from fastapi import APIRouter

from app.services.llm_service import get_llm_runtime_status

router = APIRouter()


@router.get("/status")
async def llm_status() -> dict[str, object]:
	"""Return the active LLM configuration and enablement state."""
	return get_llm_runtime_status()
