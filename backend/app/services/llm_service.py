"""LLM prompt construction and runtime integration for optional response refinement.

This module treats the LLM as a grounded post-processor over agent and RAG output.
If the provider is disabled or unavailable, the rest of the chat stack still works.
"""

from __future__ import annotations

from typing import Optional

import requests

from app.config import settings
from app.utils.logger import get_logger


logger = get_logger(__name__)


SYSTEM_PROMPT = (
	"You are an expert career guidance assistant for MTech students. "
	"Give practical, concise guidance with clear next actions."
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

INTENT_FEW_SHOT = {
	"learning_path": "Example style: Week 1-2 foundations, Week 3-5 build project, Week 6-8 portfolio and interview prep.",
	"interview_prep": "Example style: 10-question mock set + revision tracker + final timed mock.",
	"job_matching": "Example style: shortlist 15 jobs into stretch/realistic/safe and close top 3 skill gaps.",
	"networking": "Example style: optimize headline, send 5 tailored outreaches/week, track reply conversion.",
	"recommendation": "Example style: top 3 roles with confidence and feature contributions.",
	"feedback": "Example style: role + helpful flag + rating + tags for personalization update.",
	"career_assessment": "Example style: strengths, interests, constraints, then select primary and backup path.",
}


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
	few_shot = INTENT_FEW_SHOT.get(intent, "")
	matches_text = ", ".join(keyword_matches) if keyword_matches else "none"
	# The prompt is structured so the LLM acts as a grounded rewriter, not as an unconstrained generator.
	return (
		f"System: {SYSTEM_PROMPT}\n"
		"Use only the retrieved context and base guidance below as source-of-truth. "
		"Never invent tools, jobs, certifications, universities, timelines, salaries, or guarantees.\n"
		"If retrieved context is insufficient, preserve the base guidance without adding new claims.\n"
		"Keep guidance actionable, concise, and safe.\n"
		f"Intent-specific guidance: {intent_guidance}\n"
		f"Few-shot style cue: {few_shot}\n"
		f"Detected intent: {intent}\n"
		f"Intent confidence: {intent_confidence}\n"
		f"Matched intent keywords: {matches_text}\n"
		f"User profile memory: {user_profile_summary}\n"
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
		# Keep chat resilient even when the local Ollama service is missing, down, or returns malformed data.
		logger.exception("LLM refinement request failed")
		return None
