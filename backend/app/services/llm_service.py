"""LLM prompt construction and runtime integration for optional response refinement.

This module treats the LLM as a grounded post-processor over agent and RAG output.
If the provider is disabled or unavailable, the rest of the chat stack still works.
"""

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
		"groq_api_key": settings.groq_api_key.strip(),
		"groq_model": settings.groq_model.strip(),
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
		"rag_context_max_chars": int(runtime.get("rag_context_max_chars", settings.llm_rag_context_max_chars)),
		"chat_reply_max_sentences": int(runtime.get("chat_reply_max_sentences", settings.chat_reply_max_sentences)),
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
	chat_reply_max_sentences: int,
	intent_confidence: float,
	keyword_matches: list[str],
	user_profile_summary: str,
) -> str:
	"""Build a compact grounded prompt that minimizes template-echo behavior on local models."""
	rag_section = rag_context.strip() or "No retrieved context."
	intent_guidance = INTENT_PROMPT_GUIDANCE.get(intent, "Keep response concise and actionable.")
	matches_text = ", ".join(keyword_matches) if keyword_matches else "none"
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
	"""Call a local Ollama chat endpoint and return refined text."""
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
		"temperature": 0.1,
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


def _call_groq(prompt: str, runtime: dict[str, object]) -> Optional[str]:
	"""Call Groq chat completions endpoint and return refined text."""
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
		"max_tokens": 512,
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
) -> Optional[str]:
	"""Return an LLM-refined reply when runtime conditions permit, else return None."""
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
