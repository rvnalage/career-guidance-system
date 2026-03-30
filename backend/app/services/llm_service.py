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


logger = get_logger(__name__)


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


def _active_model_name() -> str:
	"""Resolve the model name that should be sent to the configured LLM provider."""
	# Prefer a fine-tuned model when configured, but fall back to the base model without changing callers.
	finetuned = settings.llm_finetuned_model.strip()
	return finetuned or settings.llm_model


def get_llm_runtime_status() -> dict[str, object]:
	"""Expose runtime LLM settings for diagnostics and environment verification."""
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
	# These early returns make the runtime behavior explicit: disabled, unsupported provider, or no RAG context means no LLM call.
	if not settings.llm_enabled:
		return None
	if settings.llm_provider.lower() != "ollama":
		return None
	if settings.llm_require_rag_context and not rag_context.strip():
		return None

	url = f"{settings.llm_base_url.rstrip('/')}/api/generate"
	payload = {
		"model": _active_model_name(),
		"prompt": _build_prompt(
			message,
			intent,
			base_reply,
			next_step,
			rag_context,
			intent_confidence,
			keyword_matches or [],
			user_profile_summary,
		),
		"stream": False,
		"keep_alive": "10m",
		"options": {
			"num_predict": 160,
		},
	}

	try:
		response = requests.post(
			url,
			json=payload,
			timeout=(5, settings.llm_request_timeout_seconds),
		)
		response.raise_for_status()
		data = response.json()
		llm_text = str(data.get("response", "")).strip()
		return limit_sentences(llm_text, settings.chat_reply_max_sentences) or None
	except ReadTimeout:
		logger.warning(
			"Ollama request timed out after %s seconds for model=%s",
			settings.llm_request_timeout_seconds,
			_active_model_name(),
		)
		return None
	except Exception:
		# Keep chat resilient even when the local Ollama service is missing, down, or returns malformed data.
		logger.warning("LLM refinement request failed", exc_info=True)
		return None
