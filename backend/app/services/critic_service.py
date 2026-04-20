"""Lightweight verifier/critic pass for assembled chat responses.

The critic is intentionally rule-based so it remains predictable and cheap while
adding a real verification stage to the chat orchestration pipeline.
"""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_META_ECHO_PREFIXES = (
	"user message:",
	"matched keywords:",
	"profile:",
	"detected intent:",
	"intent confidence:",
	"retrieved context:",
	"base guidance:",
	"next step:",
)


@dataclass
class CriticResult:
	reply: str
	changed: bool = False
	issues: list[str] = field(default_factory=list)


def _strip_meta_echo(reply: str) -> tuple[str, list[str]]:
	"""Remove prompt/debug labels that should never reach the user."""
	issues: list[str] = []
	clean_lines: list[str] = []
	for raw_line in reply.splitlines():
		line = raw_line.strip()
		lower = line.lower()
		if any(lower.startswith(prefix) for prefix in _META_ECHO_PREFIXES):
			issues.append("removed_meta_echo")
			continue
		clean_lines.append(raw_line)
	return "\n".join(clean_lines).strip(), issues


def _ensure_target_role_focus(reply: str, intent: str, context: dict[str, Any] | None) -> tuple[str, list[str]]:
	"""Attach a role anchor when a role-specific intent forgot to mention the target role."""
	if not context:
		return reply, []
	target_role = str(context.get("target_role", "")).strip()
	if not target_role:
		return reply, []
	role_specific_intents = {"career_assessment", "interview_prep", "job_matching", "learning_path", "networking"}
	if intent not in role_specific_intents:
		return reply, []
	if target_role.lower() in reply.lower():
		return reply, []
	if not reply.strip():
		return f"Focus this plan on {target_role}.", ["added_target_role_focus"]
	return f"{reply.strip()}\n\nFocus this guidance on {target_role}.", ["added_target_role_focus"]


def _replace_generic_placeholder(reply: str, context: dict[str, Any] | None) -> tuple[str, list[str]]:
	"""Replace vague placeholder phrases with the resolved target role when available."""
	if not context:
		return reply, []
	target_role = str(context.get("target_role", "")).strip()
	if not target_role:
		return reply, []
	replacements = {
		"the recommended role": target_role,
		"your target role": target_role,
		"target role": target_role,
	}
	updated = reply
	changed = False
	for old_text, new_text in replacements.items():
		if old_text in updated.lower():
			lower_text = updated.lower()
			index = lower_text.find(old_text)
			if index >= 0:
				updated = updated[:index] + new_text + updated[index + len(old_text):]
				changed = True
	issues = ["replaced_generic_role_placeholder"] if changed else []
	return updated, issues


def _ensure_minimum_substance(reply: str, next_step: str) -> tuple[str, list[str]]:
	"""Guard against empty or ultra-short outputs by returning a minimal actionable reply."""
	if len(reply.strip()) >= 80:
		return reply, []
	fallback = reply.strip()
	if fallback:
		fallback = f"{fallback}\n\nNext step: {next_step}."
	else:
		fallback = f"Here is the recommended direction: {next_step}."
	return fallback, ["added_minimum_substance"]


def verify_and_repair_reply(
	*,
	reply: str,
	intent: str,
	next_step: str,
	context: dict[str, Any] | None = None,
) -> CriticResult:
	"""Run a deterministic critic pass over the assembled reply."""
	issues: list[str] = []
	updated = reply.strip()

	updated, local_issues = _strip_meta_echo(updated)
	issues.extend(local_issues)

	updated, local_issues = _replace_generic_placeholder(updated, context)
	issues.extend(local_issues)

	updated, local_issues = _ensure_target_role_focus(updated, intent, context)
	issues.extend(local_issues)

	updated, local_issues = _ensure_minimum_substance(updated, next_step)
	issues.extend(local_issues)

	return CriticResult(reply=updated.strip(), changed=bool(issues), issues=issues)
