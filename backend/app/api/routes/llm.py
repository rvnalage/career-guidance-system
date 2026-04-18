"""Diagnostics routes for inspecting the optional LLM runtime configuration."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm_service import (
	get_llm_runtime_status,
	reset_llm_runtime_config,
	update_llm_runtime_config,
	validate_llm_runtime_config_updates,
)

router = APIRouter()


class LLMRuntimeConfigUpdate(BaseModel):
	"""Optional in-memory LLM runtime overrides that apply without process restart."""
	enabled: bool | None = None
	provider: str | None = None
	base_url: str | None = None
	model: str | None = None
	finetuned_model: str | None = None
	require_rag_context: bool | None = None
	request_timeout_seconds: int | None = None
	ollama_num_predict: int | None = None
	rag_context_max_chars: int | None = None
	chat_reply_max_sentences: int | None = None
	auto_fallback_to_openai: bool | None = None
	openai_base_url: str | None = None
	openai_model: str | None = None
	openai_max_tokens: int | None = None
	groq_model: str | None = None
	groq_max_tokens: int | None = None


@router.get("/status")
async def llm_status() -> dict[str, object]:
	"""Return the active LLM configuration and enablement state."""
	return get_llm_runtime_status()


@router.post("/config")
async def llm_update_config(payload: LLMRuntimeConfigUpdate) -> dict[str, object]:
	"""Apply runtime overrides so provider/model can be toggled live without restart."""
	updates = payload.model_dump(exclude_none=True)
	try:
		validated_updates = validate_llm_runtime_config_updates(updates)
	except ValueError as exc:
		raise HTTPException(status_code=422, detail=str(exc)) from exc
	return update_llm_runtime_config(validated_updates)


@router.post("/config/reset")
async def llm_reset_config() -> dict[str, object]:
	"""Clear all runtime overrides and revert to environment-backed defaults."""
	return reset_llm_runtime_config()
