from __future__ import annotations

from typing import Optional

import requests

from app.config import settings


SYSTEM_PROMPT = (
	"You are an expert career guidance assistant for MTech students. "
	"Give practical, concise guidance with clear next actions."
)


def _active_model_name() -> str:
	finetuned = settings.llm_finetuned_model.strip()
	return finetuned or settings.llm_model


def get_llm_runtime_status() -> dict[str, object]:
	finetuned = settings.llm_finetuned_model.strip()
	return {
		"enabled": settings.llm_enabled,
		"require_rag_context": settings.llm_require_rag_context,
		"provider": settings.llm_provider,
		"base_url": settings.llm_base_url,
		"base_model": settings.llm_model,
		"finetuned_model": finetuned,
		"active_model": _active_model_name(),
		"is_finetuned_active": bool(finetuned),
	}


def _build_prompt(message: str, intent: str, base_reply: str, next_step: str, rag_context: str) -> str:
	rag_section = rag_context.strip() or "No retrieved context."
	return (
		f"System: {SYSTEM_PROMPT}\n"
		"Use only the retrieved context and base guidance below as source-of-truth. "
		"Never invent tools, jobs, certifications, universities, timelines, salaries, or guarantees.\n"
		"If retrieved context is insufficient, preserve the base guidance without adding new claims.\n"
		"Keep guidance actionable, concise, and safe.\n"
		f"Detected intent: {intent}\n"
		f"User message: {message}\n"
		f"Retrieved context:\n{rag_section}\n"
		f"Base guidance: {base_reply}\n"
		f"Suggested next step: {next_step}\n"
		"Return only the improved assistant reply in plain text."
	)


def generate_llm_reply(
	*,
	message: str,
	intent: str,
	base_reply: str,
	next_step: str,
	rag_context: str = "",
) -> Optional[str]:
	if not settings.llm_enabled:
		return None
	if settings.llm_provider.lower() != "ollama":
		return None
	if settings.llm_require_rag_context and not rag_context.strip():
		return None

	url = f"{settings.llm_base_url.rstrip('/')}/api/generate"
	payload = {
		"model": _active_model_name(),
		"prompt": _build_prompt(message, intent, base_reply, next_step, rag_context),
		"stream": False,
	}

	try:
		response = requests.post(
			url,
			json=payload,
			timeout=settings.llm_request_timeout_seconds,
		)
		response.raise_for_status()
		data = response.json()
		llm_text = str(data.get("response", "")).strip()
		return llm_text or None
	except Exception:
		# Keep chat resilient even when local LLM is unavailable.
		return None
