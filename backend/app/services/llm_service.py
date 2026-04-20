"""LLM prompt construction and runtime integration for optional response refinement.

This module treats the LLM as a grounded post-processor over agent and RAG output.
If the provider is disabled or unavailable, the rest of the chat stack still works.
"""

# Developer Onboarding Notes:
# - Layer: LLM orchestration service
# - Role in system: Converts grounded planner/RAG signals into refined responses, with strict fallback behavior.
# - Main callers: chat route and planner/recommendation services for specialized generated artifacts.
# - Reading tip: Start from `generate_llm_reply`, then inspect provider callers (`_call_*`) and quality/safety filters.


from __future__ import annotations

import re
from time import perf_counter
from typing import Optional

import requests
from requests.exceptions import ReadTimeout

from app.config import settings
from app.utils.logger import get_logger
from app.services.safety_filter import apply_safety_filter


logger = get_logger(__name__)


_runtime_overrides: dict[str, object] = {}

_SUPPORTED_PROVIDERS = {"ollama", "groq", "openai"}
_DEFAULT_OPENAI_MODELS = {
	"gpt-4o-mini",
	"gpt-4o",
	"gpt-4.1-mini",
	"gpt-4.1",
}
_DEFAULT_GROQ_MODELS = {
	"llama-3.1-8b-instant",
	"llama-3.3-70b-versatile",
	"mixtral-8x7b-32768",
	"gemma2-9b-it",
}


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

_ECHO_PREFIXES = (
	"user message:",
	"matched keywords:",
	"profile:",
	"detected intent:",
	"intent confidence:",
	"retrieved context:",
	"base guidance:",
	"next step:",
	"sure, here's",
	"sure, here is",
)

_SALUTATION_PREFIXES = (
	"dear [user],",
	"dear user,",
	"hello [user],",
	"hello user,",
	"hi [user],",
	"hi user,",
)

_LEADING_BOILERPLATE_PATTERNS = (
	re.compile(r"^thank you for reaching out[^.!?\n]*(?:[.!?]|\s*-\s*|\s*:\s*|\s+)?", re.IGNORECASE),
	re.compile(r"^i'?m happy to provide[^.!?\n]*(?:[.!?]|\s*-\s*|\s*:\s*|\s+)?", re.IGNORECASE),
	re.compile(r"^i understand[^.!?\n]*(?:[.!?]|\s*-\s*|\s*:\s*|\s+)?", re.IGNORECASE),
	re.compile(r"^here(?:'s| is) my final advice:?\s*", re.IGNORECASE),
)

_LOW_QUALITY_PATTERNS = (
	re.compile(r"^i understand the importance", re.IGNORECASE),
	re.compile(r"^i'?m happy to provide", re.IGNORECASE),
	re.compile(r"^thank you for reaching out", re.IGNORECASE),
	re.compile(r"role-specific technical practice \+ star behavioral stories", re.IGNORECASE),
	re.compile(r"successful data engineer role-specific", re.IGNORECASE),
)

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


def _truncate_rag_context_for_prompt(rag_context: str, max_chars: int) -> str:
	"""Bound prompt size by truncating retrieved context while preserving bullet-line structure."""
	text = rag_context.strip()
	if not text:
		return ""
	if max_chars <= 0 or len(text) <= max_chars:
		return text

	truncation_marker = "\n- ... (truncated for prompt budget)"
	budget = max(64, max_chars - len(truncation_marker))
	lines = [line for line in text.splitlines() if line.strip()]
	kept_lines: list[str] = []
	current = 0
	for line in lines:
		addition = len(line) + (1 if kept_lines else 0)
		if current + addition > budget:
			break
		kept_lines.append(line)
		current += addition

	if not kept_lines:
		return text[:budget].rstrip() + truncation_marker
	return "\n".join(kept_lines).rstrip() + truncation_marker


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
		"rag_context_max_chars": settings.llm_rag_context_max_chars,
		"chat_reply_max_sentences": settings.chat_reply_max_sentences,
		"require_rag_context": settings.llm_require_rag_context,
		"openai_api_key": settings.openai_api_key.strip(),
		"openai_base_url": settings.openai_base_url.strip(),
		"openai_model": settings.openai_model.strip(),
		"openai_max_tokens": settings.openai_max_tokens,
		"groq_api_key": settings.groq_api_key.strip(),
		"groq_model": settings.groq_model.strip(),
		"groq_max_tokens": settings.groq_max_tokens,
		"auto_fallback_to_openai": settings.llm_auto_fallback_to_openai,
	}
	base.update(_runtime_overrides)
	return base


def _allowed_openai_models() -> set[str]:
	"""Return the allowlisted OpenAI models accepted by runtime config updates."""
	allowed = set(_DEFAULT_OPENAI_MODELS)
	configured = settings.openai_model.strip()
	if configured:
		allowed.add(configured)
	return allowed


def _allowed_groq_models() -> set[str]:
	"""Return the allowlisted Groq models accepted by runtime config updates."""
	allowed = set(_DEFAULT_GROQ_MODELS)
	configured = settings.groq_model.strip()
	if configured:
		allowed.add(configured)
	return allowed


def validate_llm_runtime_config_updates(updates: dict[str, object]) -> dict[str, object]:
	"""Validate and normalize runtime config updates before applying overrides.

	Args:
		updates: Partial runtime settings patch requested by API/admin caller.

	Returns:
		Sanitized update payload with bounded numeric values and validated provider/model names.

	Significance:
		Prevents invalid runtime mutations that can break live inference calls.

	Used by:
		LLM runtime config endpoints prior to `update_llm_runtime_config`.
	"""
	validated = dict(updates)
	provider = str(validated.get("provider", _resolve_runtime_config().get("provider", "ollama"))).strip().lower()
	if provider not in _SUPPORTED_PROVIDERS:
		raise ValueError(f"Unsupported provider '{provider}'. Allowed providers: {', '.join(sorted(_SUPPORTED_PROVIDERS))}.")
	validated["provider"] = provider

	if "request_timeout_seconds" in validated:
		validated["request_timeout_seconds"] = max(5, min(300, int(validated["request_timeout_seconds"])))
	if "chat_reply_max_sentences" in validated:
		validated["chat_reply_max_sentences"] = max(1, min(20, int(validated["chat_reply_max_sentences"])))
	if "ollama_num_predict" in validated:
		validated["ollama_num_predict"] = max(24, min(600, int(validated["ollama_num_predict"])))
	if "openai_max_tokens" in validated:
		validated["openai_max_tokens"] = max(64, min(2048, int(validated["openai_max_tokens"])))
	if "groq_max_tokens" in validated:
		validated["groq_max_tokens"] = max(64, min(4096, int(validated["groq_max_tokens"])))

	if "openai_model" in validated:
		model_name = str(validated["openai_model"]).strip()
		if model_name not in _allowed_openai_models():
			raise ValueError(f"Unsupported OpenAI model '{model_name}'.")
		validated["openai_model"] = model_name

	if "groq_model" in validated:
		model_name = str(validated["groq_model"]).strip()
		if model_name not in _allowed_groq_models():
			raise ValueError(f"Unsupported Groq model '{model_name}'.")
		validated["groq_model"] = model_name

	if provider == "openai" and "model" in validated:
		validated["model"] = str(validated["model"]).strip()
	if provider == "groq" and "model" in validated:
		validated["model"] = str(validated["model"]).strip()
	if provider == "ollama" and "model" in validated:
		validated["model"] = str(validated["model"]).strip()

	return validated


def _active_model_name(runtime: dict[str, object]) -> str:
	"""Resolve active model for the selected provider (ollama finetune, groq model, or openai model)."""
	provider = str(runtime.get("provider", "ollama")).strip().lower()
	finetuned = str(runtime.get("finetuned_model", "")).strip()
	if provider == "ollama" and finetuned:
		return finetuned
	if provider == "groq":
		return str(runtime.get("groq_model", "")).strip()
	if provider == "openai":
		return str(runtime.get("openai_model", "")).strip()
	return str(runtime.get("model", "")).strip()


def update_llm_runtime_config(updates: dict[str, object]) -> dict[str, object]:
	"""Apply in-memory runtime overrides for live provider/model switching.

	Significance:
		Allows experimentation and operational failover without service restart.
	"""
	for key, value in updates.items():
		_runtime_overrides[key] = value
	return get_llm_runtime_status()


def reset_llm_runtime_config() -> dict[str, object]:
	"""Reset all runtime overrides and return effective default status from environment."""
	_runtime_overrides.clear()
	return get_llm_runtime_status()


def get_llm_runtime_status() -> dict[str, object]:
	"""Return effective runtime LLM settings for diagnostics.

	Significance:
		Primary observability payload to confirm provider, active model, token/timeout
		limits, and whether overrides are currently active.

	Used by:
		LLM status route and runbook troubleshooting flows.
	"""
	runtime = _resolve_runtime_config()
	provider = str(runtime.get("provider", "ollama")).strip().lower()
	finetuned = str(runtime.get("finetuned_model", "")).strip()
	ollama_finetuned_active = provider == "ollama" and bool(finetuned)
	return {
		"enabled": bool(runtime.get("enabled", False)),
		"require_rag_context": bool(runtime.get("require_rag_context", True)),
		"provider": provider,
		"base_url": str(runtime.get("base_url", "")),
		"openai_api_key_configured": bool(str(runtime.get("openai_api_key", "")).strip()),
		"base_model": str(runtime.get("model", "")),
		"request_timeout_seconds": int(runtime.get("request_timeout_seconds", settings.llm_request_timeout_seconds)),
		"ollama_num_predict": int(runtime.get("ollama_num_predict", settings.llm_ollama_num_predict)),
		"rag_context_max_chars": int(runtime.get("rag_context_max_chars", settings.llm_rag_context_max_chars)),
		"chat_reply_max_sentences": int(runtime.get("chat_reply_max_sentences", settings.chat_reply_max_sentences)),
		"finetuned_model": finetuned,
		"active_model": _active_model_name(runtime),
		"is_finetuned_active": ollama_finetuned_active,
		"auto_fallback_to_openai": bool(runtime.get("auto_fallback_to_openai", False)),
		"openai_base_url": str(runtime.get("openai_base_url", "")),
		"openai_model": str(runtime.get("openai_model", "")),
		"openai_max_tokens": int(runtime.get("openai_max_tokens", settings.openai_max_tokens)),
		"groq_model": str(runtime.get("groq_model", "")),
		"groq_max_tokens": int(runtime.get("groq_max_tokens", settings.groq_max_tokens)),
		"groq_api_key_configured": bool(str(runtime.get("groq_api_key", "")).strip()),
		"runtime_override_active": bool(_runtime_overrides),
	}


def _build_prompt(
	message: str,
	intent: str,
	base_reply: str,
	next_step: str,
	rag_context: str,
	chat_reply_max_sentences: int,
	intent_confidence: float,
	keyword_matches: list[str],
	user_profile_summary: str,
	skill_gaps: list[str] | None = None,
) -> str:
	"""Build grounded user prompt from planner and retrieval context.

	Significance:
		Central prompt-template contract for response quality. Keeps generation tied to
		RAG and planner evidence while discouraging meta-echo boilerplate.
	"""
	rag_section = rag_context.strip() or "No retrieved context."
	intent_guidance = INTENT_PROMPT_GUIDANCE.get(intent, "Keep response concise and actionable.")
	matches_text = ", ".join(keyword_matches) if keyword_matches else "none"
	skill_gap_section = ""
	if skill_gaps:
		gaps_text = ", ".join(skill_gaps[:4])
		skill_gap_section = (
			f"SKILL_GAPS: The user is missing these skills for their target role: {gaps_text}.\n"
			"- For each missing skill, suggest one free or low-cost resource (course, tutorial, or documentation).\n"
		)
	# This is the user-content block for chat-style providers; system instructions are sent separately.
	return (
		"Task: Write the final assistant reply for the user's career question.\n"
		"Hard rules:\n"
		"- Use only the CONTEXT and BASE_GUIDANCE below.\n"
		"- Do not repeat section labels like 'User message' or 'Profile'.\n"
		"- Output only final advice prose, no preface.\n"
		"- Do not thank the user, greet the user, or mention that you are happy to help.\n"
		"- Do not say 'I understand', 'Dear user', or similar courtesy phrases.\n"
		f"- Write up to {chat_reply_max_sentences} sentences. Use numbered steps, bullet points, or structured paragraphs as appropriate for the question.\n"
		f"Intent guidance: {intent_guidance}\n"
		f"QUESTION: {message}\n"
		f"INTENT: {intent} (confidence {intent_confidence:.2f})\n"
		f"KEYWORDS: {matches_text}\n"
		f"PROFILE: {user_profile_summary}\n"
		f"{skill_gap_section}"
		f"CONTEXT:\n{rag_section}\n"
		f"BASE_GUIDANCE: {base_reply}\n"
		f"NEXT_STEP_HINT: {next_step}\n"
		"Final reply:"
	)


def _strip_meta_echo(text: str) -> str:
	"""Remove common prompt-template echoes that some local models prepend."""
	if not text.strip():
		return text
	cleaned_lines: list[str] = []
	for raw_line in text.splitlines():
		line = raw_line.strip()
		if not line:
			cleaned_lines.append(raw_line)
			continue
		lower = line.lower()
		if any(lower.startswith(prefix) for prefix in _ECHO_PREFIXES):
			continue
		cleaned_lines.append(raw_line)
	cleaned = "\n".join(cleaned_lines).strip()
	if not cleaned:
		return text.strip()

	# Remove generic greeting salutation line if present at the beginning.
	lines = [line for line in cleaned.splitlines() if line.strip()]
	if lines and lines[0].strip().lower() in _SALUTATION_PREFIXES:
		cleaned = "\n".join(lines[1:]).strip()

	for pattern in _LEADING_BOILERPLATE_PATTERNS:
		cleaned = pattern.sub("", cleaned).strip()

	return cleaned or text.strip()


def _trim_incomplete_tail(text: str) -> str:
	"""Drop a trailing fragment when the model stops mid-sentence."""
	stripped = text.strip()
	if not stripped:
		return stripped
	if stripped[-1] in ".!?":
		return stripped

	last_sentence_end = max(stripped.rfind("."), stripped.rfind("!"), stripped.rfind("?"))
	if last_sentence_end == -1:
		return stripped
	return stripped[: last_sentence_end + 1].strip()


def _is_low_quality_generation(text: str) -> bool:
	"""Detect generic/template-like local model output that should not replace grounded agent text."""
	stripped = text.strip()
	if not stripped:
		return True
	if len(stripped) < 60:
		return True
	for pattern in _LOW_QUALITY_PATTERNS:
		if pattern.search(stripped):
			return True
	return False


def _log_prompt_diagnostics(
	*,
	provider: str,
	model: str,
	original_rag_context: str,
	prompt_rag_context: str,
	prompt: str,
	runtime: dict[str, object],
) -> None:
	"""Emit compact prompt diagnostics to debug local model latency and fallbacks."""
	logger.info(
		"LLM prompt diagnostics provider=%s model=%s prompt_chars=%s rag_chars_original=%s rag_chars_prompt=%s timeout_seconds=%s num_predict=%s",
		provider,
		model,
		len(prompt),
		len(original_rag_context.strip()),
		len(prompt_rag_context.strip()),
		int(runtime.get("request_timeout_seconds", settings.llm_request_timeout_seconds)),
		int(runtime.get("ollama_num_predict", settings.llm_ollama_num_predict)),
	)


def _call_ollama(prompt: str, runtime: dict[str, object]) -> Optional[str]:
	"""Call local Ollama chat endpoint and return model text.

	Used by:
		`generate_llm_reply` and specialist plan-generation helpers.
	"""
	url = f"{str(runtime.get('base_url', '')).rstrip('/')}/api/chat"
	num_predict = max(24, min(600, int(runtime.get("ollama_num_predict", settings.llm_ollama_num_predict))))
	payload = {
		"model": _active_model_name(runtime),
		"messages": [
			{"role": "system", "content": SYSTEM_PROMPT},
			{"role": "user", "content": prompt},
		],
		"stream": False,
		"keep_alive": "10m",
		"options": {
			"num_predict": num_predict,
			"temperature": 0.1,
		},
	}

	start_time = perf_counter()
	response = requests.post(
		url,
		json=payload,
		timeout=(5, int(runtime.get("request_timeout_seconds", settings.llm_request_timeout_seconds))),
	)
	response.raise_for_status()
	data = response.json()
	message = data.get("message") or {}
	content = str(message.get("content", "")).strip()
	logger.info(
		"Ollama generate completed model=%s elapsed_ms=%s response_chars=%s done=%s",
		_active_model_name(runtime),
		int((perf_counter() - start_time) * 1000),
		len(content),
		data.get("done"),
	)
	return content or None


def _call_openai_compatible(prompt: str, runtime: dict[str, object], *, fallback_mode: bool = False) -> Optional[str]:
	"""Call OpenAI-compatible chat completion endpoint and return model text.

	Significance:
		Used both as primary provider path and as fallback when local provider fails.
	"""
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
		"temperature": 0.1,
		"max_tokens": max(64, min(2048, int(runtime.get("openai_max_tokens", settings.openai_max_tokens)))),
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


def _call_groq(prompt: str, runtime: dict[str, object]) -> Optional[str]:
	"""Call Groq chat completion endpoint and return model text."""
	api_key = str(runtime.get("groq_api_key", "")).strip()
	if not api_key:
		logger.warning("LLM provider=groq but GROQ_API_KEY is missing")
		return None

	model_name = str(runtime.get("groq_model", settings.groq_model)).strip()
	url = "https://api.groq.com/openai/v1/chat/completions"
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
		"temperature": 0.1,
		"max_tokens": max(64, min(4096, int(runtime.get("groq_max_tokens", settings.groq_max_tokens)))),
	}

	start_time = perf_counter()
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
	content = str(message.get("content", "")).strip()
	logger.info(
		"Groq generate completed model=%s elapsed_ms=%s response_chars=%s",
		model_name,
		int((perf_counter() - start_time) * 1000),
		len(content),
	)
	return content or None


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
	skill_gaps: list[str] | None = None,
) -> Optional[str]:
	"""Generate a refined assistant reply with strict resilience and safety gates.

	Args:
		message: Latest user question.
		intent: Routed intent label from planner/agent layer.
		base_reply: Deterministic grounded reply from local orchestration.
		next_step: Follow-up hint from primary intent agent.
		rag_context: Retrieved knowledge context (optional based on runtime policy).
		intent_confidence: Router confidence score for prompt conditioning.
		keyword_matches: Intent keyword hits for explainability/grounding.
		user_profile_summary: Compact profile memory snapshot for personalization.
		skill_gaps: Optional missing-skill hints for actionable outputs.

	Returns:
		Filtered refined reply text, or None when LLM should be skipped/fallback to base guidance.

	Significance:
		Primary LLM entrypoint for chat responses. Enforces provider fallback policy,
		output quality checks, and safety filtering before returning text to users.

	Used by:
		Chat route response assembly pipeline.
	"""
	runtime = _resolve_runtime_config()
	# These early returns make runtime behavior explicit: disabled or no RAG context means no LLM call.
	if not bool(runtime.get("enabled", False)):
		logger.info("LLM refinement skipped because runtime is disabled")
		return None
	if bool(runtime.get("require_rag_context", True)) and not rag_context.strip():
		logger.info("LLM refinement skipped because RAG context is required and retrieval returned empty context")
		return None

	prompt_rag_context = _truncate_rag_context_for_prompt(
		rag_context,
		int(runtime.get("rag_context_max_chars", settings.llm_rag_context_max_chars)),
	)
	reply_max_sentences = int(runtime.get("chat_reply_max_sentences", settings.chat_reply_max_sentences))

	prompt = _build_prompt(
		message,
		intent,
		base_reply,
		next_step,
		prompt_rag_context,
		reply_max_sentences,
		intent_confidence,
		keyword_matches or [],
		user_profile_summary,
		skill_gaps=skill_gaps,
	)
	provider = str(runtime.get("provider", "ollama")).lower().strip()
	model_name = _active_model_name(runtime)
	_log_prompt_diagnostics(
		provider=provider,
		model=model_name,
		original_rag_context=rag_context,
		prompt_rag_context=prompt_rag_context,
		prompt=prompt,
		runtime=runtime,
	)

	try:
		llm_text: Optional[str] = None
		if provider == "ollama":
			llm_text = _call_ollama(prompt, runtime)
		elif provider == "openai":
			llm_text = _call_openai_compatible(prompt, runtime)
		elif provider == "groq":
			llm_text = _call_groq(prompt, runtime)
		else:
			logger.warning("Unsupported LLM provider: %s", runtime.get("provider"))
			return None

		if not llm_text and provider == "ollama" and bool(runtime.get("auto_fallback_to_openai", False)):
			logger.warning("Primary provider ollama returned no response; attempting automatic fallback to openai")
			llm_text = _call_openai_compatible(prompt, runtime, fallback_mode=True)

		if not llm_text:
			logger.info("LLM refinement produced no text response after provider call")
			return None
		candidate_text = _trim_incomplete_tail(_strip_meta_echo(llm_text))
		if _is_low_quality_generation(candidate_text):
			logger.info("LLM refinement rejected low-quality/template-like response")
			return None
		filtered = apply_safety_filter(candidate_text)
		if filtered.blocked:
			logger.info("LLM refinement blocked by safety filter (reason=%s)", filtered.reason)
			return filtered.text  # return fallback message, not None, so it reaches the user
		logger.info("LLM refinement accepted response_chars=%s", len(filtered.text.strip()))
		return limit_sentences(filtered.text, reply_max_sentences) or None
	except ReadTimeout:
		logger.warning(
			"LLM request timed out after %s seconds for provider=%s model=%s prompt_chars=%s rag_chars_prompt=%s",
			runtime.get("request_timeout_seconds", settings.llm_request_timeout_seconds),
			provider,
			model_name,
			len(prompt),
			len(prompt_rag_context.strip()),
		)
		if provider == "ollama" and bool(runtime.get("auto_fallback_to_openai", False)):
			try:
				llm_text = _call_openai_compatible(prompt, runtime, fallback_mode=True)
				if llm_text:
					filtered = apply_safety_filter(llm_text)
					if filtered.blocked:
						return filtered.text
					return limit_sentences(filtered.text, reply_max_sentences) or None
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
					return limit_sentences(filtered.text, reply_max_sentences) or None
			except Exception:
				logger.warning("Fallback to openai failed", exc_info=True)
		logger.warning("LLM refinement request failed", exc_info=True)
		return None

async def generate_recommendation_reason_via_llm(
	*,
	user_role: str,
	user_skills: list[str],
	user_interests: list[str],
	matched_skills: int,
	total_required_skills: int,
	interest_matches: int,
	education_fit: float,
	confidence_score: float,
) -> Optional[str]:
	"""Generate short personalized recommendation rationale text.

	Used by:
		Recommendation service during post-scoring reason enrichment.
	"""
	runtime = _resolve_runtime_config()
	if not bool(runtime.get("enabled", False)):
		return None
	
	skills_text = ", ".join(user_skills[:5]) if user_skills else "no skills provided"
	interests_text = ", ".join(user_interests[:4]) if user_interests else "no interests provided"
	
	prompt = (
		"Task: Write a 1-2 sentence personalized explanation for why this career recommendation fits.\n"
		"Use the user's actual data, NOT generic templates.\n\n"
		f"TARGET ROLE: {user_role}\n"
		f"USER_SKILLS: {skills_text}\n"
		f"USER_INTERESTS: {interests_text}\n"
		f"SKILL_MATCH: {matched_skills}/{total_required_skills} core skills\n"
		f"INTEREST_MATCH: {interest_matches} related interests\n"
		f"EDUCATION_FIT: {education_fit:.0%}\n"
		f"CONFIDENCE: {confidence_score:.0%}\n\n"
		"Explanation:"
	)
	
	try:
		llm_text: Optional[str] = None
		provider = str(runtime.get("provider", "ollama")).lower().strip()
		
		if provider == "ollama":
			llm_text = _call_ollama(prompt, runtime)
		elif provider == "openai" or provider == "groq":
			llm_text = _call_openai_compatible(prompt, runtime)
		
		if llm_text:
			return _trim_incomplete_tail(llm_text.strip())
	except Exception:
		logger.exception("Failed to generate recommendation reason via LLM")
	
	return None


async def generate_interview_plan_via_llm(
	*,
	target_role: str,
	timeline_days: int,
	skill_gaps: list[str],
	company_name: str | None = None,
) -> Optional[str]:
	"""Generate interview sprint plan from role, timeline, and gap signals.

	Used by:
		Planner interview tool path.
	"""
	runtime = _resolve_runtime_config()
	if not bool(runtime.get("enabled", False)):
		return None
	
	gaps_text = ", ".join(skill_gaps[:4]) if skill_gaps else "general interview readiness"
	company_hint = f" Target company: {company_name}." if company_name else ""
	
	prompt = (
		f"You are an interview prep coach. Generate a {timeline_days}-day interview sprint plan for a {target_role} role.{company_hint}\n"
		f"KEY SKILL GAPS TO ADDRESS: {gaps_text}\n\n"
		"Output a day-by-day plan with specific focus areas and activities. Be concise (3-4 sentences per day).\n"
		"Format as: 'Day 1: [topic]. [specific activity]. Day 2: ...'"
	)
	
	try:
		llm_text: Optional[str] = None
		provider = str(runtime.get("provider", "ollama")).lower().strip()
		
		if provider == "ollama":
			llm_text = _call_ollama(prompt, runtime)
		elif provider == "openai" or provider == "groq":
			llm_text = _call_openai_compatible(prompt, runtime)
		
		if llm_text:
			return _trim_incomplete_tail(llm_text.strip())
	except Exception:
		logger.exception("Failed to generate interview plan via LLM")
	
	return None


async def generate_interview_focus_areas_via_llm(
	*,
	target_role: str,
	skill_gaps: list[str],
	timeline_days: int,
	company_name: str | None = None,
) -> Optional[str]:
	"""Generate role-specific interview focus areas with concise rationale and drills."""
	runtime = _resolve_runtime_config()
	if not bool(runtime.get("enabled", False)):
		return None

	gaps_text = ", ".join(skill_gaps[:4]) if skill_gaps else "core interview fundamentals"
	company_hint = f" Target company: {company_name}." if company_name else ""

	prompt = (
		f"You are an interview coach. Create top focus areas for a {target_role} interview prep sprint over {timeline_days} days.{company_hint}\n"
		f"KNOWN GAPS: {gaps_text}\n\n"
		"Return exactly 4 focus areas. For each area, include: why it matters + one practical drill. "
		"Use compact bullets."
	)

	try:
		llm_text: Optional[str] = None
		provider = str(runtime.get("provider", "ollama")).lower().strip()

		if provider == "ollama":
			llm_text = _call_ollama(prompt, runtime)
		elif provider == "openai" or provider == "groq":
			llm_text = _call_openai_compatible(prompt, runtime)

		if llm_text:
			return _trim_incomplete_tail(llm_text.strip())
	except Exception:
		logger.exception("Failed to generate interview focus areas via LLM")

	return None


async def generate_learning_plan_via_llm(
	*,
	target_role: str,
	timeline_weeks: int,
	skill_gaps: list[str],
	learning_style: str | None = None,
) -> Optional[str]:
	"""Generate role-aligned learning plan for configured timeline.

	Used by:
		Planner learning tool path.
	"""
	runtime = _resolve_runtime_config()
	if not bool(runtime.get("enabled", False)):
		return None
	
	gaps_text = ", ".join(skill_gaps[:5]) if skill_gaps else "role fundamentals"
	style_hint = f" Preferred learning style: {learning_style}." if learning_style else ""
	
	prompt = (
		f"You are a career development coach. Generate a {timeline_weeks}-week learning path for becoming a {target_role}.{style_hint}\n"
		f"PRIMARY SKILL GAPS: {gaps_text}\n\n"
		"Output a week-by-week plan with concrete skills, projects, and milestones. Be practical and actionable.\n"
		"Use format: 'Week 1: [skill focus]. [activities]. Week 2: ...'"
	)
	
	try:
		llm_text: Optional[str] = None
		provider = str(runtime.get("provider", "ollama")).lower().strip()
		
		if provider == "ollama":
			llm_text = _call_ollama(prompt, runtime)
		elif provider == "openai" or provider == "groq":
			llm_text = _call_openai_compatible(prompt, runtime)
		
		if llm_text:
			return _trim_incomplete_tail(llm_text.strip())
	except Exception:
		logger.exception("Failed to generate learning plan via LLM")
	
	return None


async def generate_networking_strategy_via_llm(
	*,
	target_role: str,
	target_companies: list[str],
	weekly_availability_hours: int | None = None,
	response_rate_percent: int | None = None,
	seniority_level: str | None = None,
) -> Optional[str]:
	"""Generate networking strategy with cadence tuned to availability/response signals.

	Used by:
		Planner networking tool path.
	"""
	runtime = _resolve_runtime_config()
	if not bool(runtime.get("enabled", False)):
		return None
	
	companies_text = ", ".join(target_companies[:3]) if target_companies else "your target companies"
	availability_hint = (
		f" Weekly availability: {weekly_availability_hours} hours."
		if weekly_availability_hours is not None
		else ""
	)
	response_hint = (
		f" Current outreach response rate: {response_rate_percent}%."
		if response_rate_percent is not None
		else ""
	)
	seniority_hint = f" Career level: {seniority_level}." if seniority_level else ""
	
	prompt = (
		f"You are a networking strategist. Design a concrete 3-week networking plan for landing a {target_role} role at {companies_text}.{availability_hint}{response_hint}{seniority_hint}\n"
		"Include: specific platforms (LinkedIn, alumni networks), outreach messaging, conversation starters, follow-up cadence.\n"
		"Adapt message volume and follow-up cadence to availability and response-rate signals. "
		"Be specific and actionable. Format: 'Week 1: [actions]. Week 2: [actions]. Week 3: [actions].'"
	)
	
	try:
		llm_text: Optional[str] = None
		provider = str(runtime.get("provider", "ollama")).lower().strip()
		
		if provider == "ollama":
			llm_text = _call_ollama(prompt, runtime)
		elif provider == "openai" or provider == "groq":
			llm_text = _call_openai_compatible(prompt, runtime)
		
		if llm_text:
			return _trim_incomplete_tail(llm_text.strip())
	except Exception:
		logger.exception("Failed to generate networking strategy via LLM")
	
	return None


async def generate_job_readiness_assessment_via_llm(
	*,
	target_role: str,
	user_skills: list[str],
	skill_gaps: list[str],
	experience_months: int | None = None,
) -> Optional[str]:
	"""Generate job-readiness assessment with strengths, gaps, and short action plan.

	Used by:
		Planner job-readiness tool path.
	"""
	runtime = _resolve_runtime_config()
	if not bool(runtime.get("enabled", False)):
		return None
	
	skills_text = ", ".join(user_skills[:6]) if user_skills else "no skills"
	gaps_text = ", ".join(skill_gaps[:4]) if skill_gaps else "none identified"
	exp_hint = f" Experience: {experience_months} months." if experience_months else ""
	
	prompt = (
		f"Assess job readiness for {target_role}.\n"
		f"CURRENT_SKILLS: {skills_text}\n"
		f"SKILL_GAPS: {gaps_text}{exp_hint}\n\n"
		"Provide: 1) readiness level (early/medium/high), 2) top 3 strengths, 3) critical gaps, 4) 30-day action items.\n"
		"Be honest but constructive. Format as clear sections."
	)
	
	try:
		llm_text: Optional[str] = None
		provider = str(runtime.get("provider", "ollama")).lower().strip()
		
		if provider == "ollama":
			llm_text = _call_ollama(prompt, runtime)
		elif provider == "openai" or provider == "groq":
			llm_text = _call_openai_compatible(prompt, runtime)
		
		if llm_text:
			return _trim_incomplete_tail(llm_text.strip())
	except Exception:
		logger.exception("Failed to generate job readiness assessment via LLM")
	
	return None


async def generate_career_assessment_framework_via_llm(
	*,
	target_roles: list[str],
	user_skills: list[str],
	user_interests: list[str],
	timeline_weeks: int,
) -> Optional[str]:
	"""Generate career-assessment framework with role-fit rubric and checkpoints.

	Used by:
		Planner career-assessment tool path.
	"""
	runtime = _resolve_runtime_config()
	if not bool(runtime.get("enabled", False)):
		return None

	roles_text = ", ".join(target_roles[:3]) if target_roles else "2-3 realistic target roles"
	skills_text = ", ".join(user_skills[:6]) if user_skills else "current baseline skills"
	interests_text = ", ".join(user_interests[:5]) if user_interests else "stated interests"

	prompt = (
		f"Create a personalized {timeline_weeks}-week career assessment framework.\n"
		f"CANDIDATE_ROLES: {roles_text}\n"
		f"CURRENT_SKILLS: {skills_text}\n"
		f"INTERESTS: {interests_text}\n\n"
		"Provide: 1) role-fit rubric with weighted criteria, 2) weekly validation activities, "
		"3) decision checkpoint with go/no-go signals, 4) one backup-path strategy. "
		"Keep it practical and concise."
	)

	try:
		llm_text: Optional[str] = None
		provider = str(runtime.get("provider", "ollama")).lower().strip()

		if provider == "ollama":
			llm_text = _call_ollama(prompt, runtime)
		elif provider == "openai" or provider == "groq":
			llm_text = _call_openai_compatible(prompt, runtime)

		if llm_text:
			return _trim_incomplete_tail(llm_text.strip())
	except Exception:
		logger.exception("Failed to generate career assessment framework via LLM")

	return None
