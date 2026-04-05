"""LLM prompt construction and runtime integration for optional response refinement.

This module treats the LLM as a grounded post-processor over agent and RAG output.
If the provider is disabled or unavailable, the rest of the chat stack still works.
"""

from __future__ import annotations

from typing import Optional

import requests
from requests.exceptions import ReadTimeout

from app.config import settings
from app.utils.logger import get_logger
from app.services.safety_filter import apply_safety_filter


logger = get_logger(__name__)


_runtime_overrides: dict[str, object] = {}


SYSTEM_PROMPT = (
	"You are a concise career guidance assistant for MTech students."
)

INTENT_PROMPT_GUIDANCE = {
	"learning_path": "Prefer phased roadmap outputs with weekly milestones and project checkpoints.",
	"interview_prep": "Prioritize interview readiness: role-specific technical practice + STAR behavioral stories.",
	"job_matching": "Focus on fit-gap analysis and actionable application strategy buckets.",
	"networking": "Provide concise outreach positioning and follow-up pipeline tactics.",
	"recommendation": "Explain recommendation rationale and confidence drivers before suggesting next actions.",
	"feedback": "Acknowledge feedback and request structured rating/tags to improve personalization.",
	"career_assessment": "Ask clarifying questions and guide to role-fit decision matrix when uncertain.",
}

def limit_sentences(text: str, max_sentences: int) -> str:
	"""Trim prose to at most max_sentences while preserving trailing non-prose sections."""
	if max_sentences <= 0:
		return text.strip()

	marker = "\n\nRelevant references:\n"
	main_text, separator, trailing = text.partition(marker)
	main_text = main_text.strip()
	if not main_text:
		return text.strip()

	sentence_count = 0
	last_end = 0
	for index, char in enumerate(main_text):
		if char in ".!?" and (index + 1 == len(main_text) or main_text[index + 1].isspace()):
			sentence_count += 1
			last_end = index + 1
			if sentence_count >= max_sentences:
				break

	trimmed_main = main_text if sentence_count < max_sentences else main_text[:last_end].strip()
	if separator:
		return f"{trimmed_main}{marker}{trailing.strip()}".strip()
	return trimmed_main


def _resolve_runtime_config() -> dict[str, object]:
	"""Return effective runtime settings by merging env configuration with in-memory overrides."""
	base = {
		"enabled": settings.llm_enabled,
		"provider": settings.llm_provider.strip().lower(),
		"base_url": settings.llm_base_url.strip(),
		"model": settings.llm_model.strip(),
		"finetuned_model": settings.llm_finetuned_model.strip(),
		"request_timeout_seconds": settings.llm_request_timeout_seconds,
		"ollama_num_predict": settings.llm_ollama_num_predict,
		"require_rag_context": settings.llm_require_rag_context,
		"openai_api_key": settings.openai_api_key.strip(),
		"openai_base_url": settings.openai_base_url.strip(),
		"openai_model": settings.openai_model.strip(),
		"auto_fallback_to_openai": settings.llm_auto_fallback_to_openai,
	}
	base.update(_runtime_overrides)
	return base


def _active_model_name(runtime: dict[str, object]) -> str:
	"""Resolve active model for the current provider call path."""
	finetuned = str(runtime.get("finetuned_model", "")).strip()
	return finetuned or str(runtime.get("model", "")).strip()


def update_llm_runtime_config(updates: dict[str, object]) -> dict[str, object]:
	"""Apply in-memory runtime updates so provider/model can be changed without restart."""
	for key, value in updates.items():
		_runtime_overrides[key] = value
	return get_llm_runtime_status()


def reset_llm_runtime_config() -> dict[str, object]:
	"""Reset all runtime overrides and return effective default status from environment."""
	_runtime_overrides.clear()
	return get_llm_runtime_status()


def get_llm_runtime_status() -> dict[str, object]:
	"""Expose runtime LLM settings for diagnostics and environment verification."""
	runtime = _resolve_runtime_config()
	finetuned = str(runtime.get("finetuned_model", "")).strip()
	return {
		"enabled": bool(runtime.get("enabled", False)),
		"require_rag_context": bool(runtime.get("require_rag_context", True)),
		"provider": str(runtime.get("provider", "ollama")),
		"base_url": str(runtime.get("base_url", "")),
		"openai_api_key_configured": bool(str(runtime.get("openai_api_key", "")).strip()),
		"base_model": str(runtime.get("model", "")),
		"request_timeout_seconds": int(runtime.get("request_timeout_seconds", settings.llm_request_timeout_seconds)),
		"ollama_num_predict": int(runtime.get("ollama_num_predict", settings.llm_ollama_num_predict)),
		"finetuned_model": finetuned,
		"active_model": _active_model_name(runtime),
		"is_finetuned_active": bool(finetuned),
		"auto_fallback_to_openai": bool(runtime.get("auto_fallback_to_openai", False)),
		"openai_base_url": str(runtime.get("openai_base_url", "")),
		"openai_model": str(runtime.get("openai_model", "")),
		"runtime_override_active": bool(_runtime_overrides),
	}


def _build_prompt(
	message: str,
	intent: str,
	base_reply: str,
	next_step: str,
	rag_context: str,
	intent_confidence: float,
	keyword_matches: list[str],
	user_profile_summary: str,
) -> str:
	"""Build a grounded prompt that constrains the LLM to retrieved and deterministic guidance."""
	rag_section = rag_context.strip() or "No retrieved context."
	intent_guidance = INTENT_PROMPT_GUIDANCE.get(intent, "Keep response concise and actionable.")
	matches_text = ", ".join(keyword_matches) if keyword_matches else "none"
	# The prompt is structured so the LLM acts as a grounded rewriter, not as an unconstrained generator.
	return (
		f"System: {SYSTEM_PROMPT}\n"
		"Use only the retrieved context and base guidance as source-of-truth.\n"
		"Do not invent facts.\n"
		f"Reply in at most {settings.chat_reply_max_sentences} short sentences.\n"
		f"Intent-specific guidance: {intent_guidance}\n"
		f"Detected intent: {intent}\n"
		f"Intent confidence: {intent_confidence}\n"
		f"User message: {message}\n"
		f"Matched keywords: {matches_text}\n"
		f"Profile: {user_profile_summary}\n"
		f"Retrieved context: {rag_section}\n"
		f"Base guidance: {base_reply}\n"
		f"Next step: {next_step}\n"
		"Return only the final reply text."
	)


def _call_ollama(prompt: str, runtime: dict[str, object]) -> Optional[str]:
	"""Call a local Ollama-compatible generate endpoint and return refined text."""
	url = f"{str(runtime.get('base_url', '')).rstrip('/')}/api/generate"
	num_predict = max(24, min(256, int(runtime.get("ollama_num_predict", settings.llm_ollama_num_predict))))
	payload = {
		"model": _active_model_name(runtime),
		"prompt": prompt,
		"stream": False,
		"keep_alive": "10m",
		"options": {
			"num_predict": num_predict,
			"temperature": 0.2,
		},
	}

	response = requests.post(
		url,
		json=payload,
		timeout=(5, int(runtime.get("request_timeout_seconds", settings.llm_request_timeout_seconds))),
	)
	response.raise_for_status()
	data = response.json()
	return str(data.get("response", "")).strip() or None


def _call_openai_compatible(prompt: str, runtime: dict[str, object], *, fallback_mode: bool = False) -> Optional[str]:
	"""Call OpenAI (or compatible) chat completions endpoint and return refined text."""
	api_key = str(runtime.get("openai_api_key", "")).strip()
	if not api_key:
		logger.warning("LLM provider=openai but OPENAI_API_KEY is missing")
		return None

	if fallback_mode:
		base_url = str(runtime.get("openai_base_url", "")).strip()
		model_name = str(runtime.get("openai_model", "")).strip()
	else:
		base_url = str(runtime.get("base_url", "")).strip()
		model_name = _active_model_name(runtime)

	url = f"{base_url.rstrip('/')}/chat/completions"
	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
	}
	payload = {
		"model": model_name,
		"messages": [
			{"role": "system", "content": SYSTEM_PROMPT},
			{"role": "user", "content": prompt},
		],
		"temperature": 0.2,
		"max_tokens": 260,
	}

	response = requests.post(
		url,
		headers=headers,
		json=payload,
		timeout=(5, int(runtime.get("request_timeout_seconds", settings.llm_request_timeout_seconds))),
	)
	response.raise_for_status()
	data = response.json()
	choices = data.get("choices") or []
	if not choices:
		return None
	message = choices[0].get("message", {})
	return str(message.get("content", "")).strip() or None


def generate_llm_reply(
	*,
	message: str,
	intent: str,
	base_reply: str,
	next_step: str,
	rag_context: str = "",
	intent_confidence: float = 0.0,
	keyword_matches: list[str] | None = None,
	user_profile_summary: str = "No profile memory available.",
) -> Optional[str]:
	"""Return an LLM-refined reply when runtime conditions permit, else return None."""
	runtime = _resolve_runtime_config()
	# These early returns make runtime behavior explicit: disabled or no RAG context means no LLM call.
	if not bool(runtime.get("enabled", False)):
		return None
	if bool(runtime.get("require_rag_context", True)) and not rag_context.strip():
		return None

	prompt = _build_prompt(
		message,
		intent,
		base_reply,
		next_step,
		rag_context,
		intent_confidence,
		keyword_matches or [],
		user_profile_summary,
	)
	provider = str(runtime.get("provider", "ollama")).lower().strip()

	try:
		llm_text: Optional[str] = None
		if provider == "ollama":
			llm_text = _call_ollama(prompt, runtime)
		elif provider == "openai":
			llm_text = _call_openai_compatible(prompt, runtime)
		else:
			logger.warning("Unsupported LLM provider: %s", runtime.get("provider"))
			return None

		if not llm_text and provider == "ollama" and bool(runtime.get("auto_fallback_to_openai", False)):
			logger.warning("Primary provider ollama returned no response; attempting automatic fallback to openai")
			llm_text = _call_openai_compatible(prompt, runtime, fallback_mode=True)

		if not llm_text:
			return None
		filtered = apply_safety_filter(llm_text)
		if filtered.blocked:
			return filtered.text  # return fallback message, not None, so it reaches the user
		return limit_sentences(filtered.text, settings.chat_reply_max_sentences) or None
	except ReadTimeout:
		logger.warning(
			"LLM request timed out after %s seconds for provider=%s model=%s",
			runtime.get("request_timeout_seconds", settings.llm_request_timeout_seconds),
			provider,
			_active_model_name(runtime),
		)
		if provider == "ollama" and bool(runtime.get("auto_fallback_to_openai", False)):
			try:
				llm_text = _call_openai_compatible(prompt, runtime, fallback_mode=True)
				if llm_text:
					filtered = apply_safety_filter(llm_text)
					if filtered.blocked:
						return filtered.text
					return limit_sentences(filtered.text, settings.chat_reply_max_sentences) or None
			except Exception:
				logger.warning("Fallback to openai after timeout failed", exc_info=True)
		return None
	except Exception:
		# Keep chat resilient even when provider is down, missing, or returns malformed data.
		if provider == "ollama" and bool(runtime.get("auto_fallback_to_openai", False)):
			try:
				llm_text = _call_openai_compatible(prompt, runtime, fallback_mode=True)
				if llm_text:
					filtered = apply_safety_filter(llm_text)
					if filtered.blocked:
						return filtered.text
					return limit_sentences(filtered.text, settings.chat_reply_max_sentences) or None
			except Exception:
				logger.warning("Fallback to openai failed", exc_info=True)
		logger.warning("LLM refinement request failed", exc_info=True)
		return None
