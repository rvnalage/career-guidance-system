"""Lightweight orchestration layer for multi-step career guidance responses.

This planner keeps the existing specialist agents but lets one request combine
multiple capabilities: intent routing, supporting specialist handoffs, and the
recommendation engine when enough profile evidence is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from time import perf_counter
from typing import Any

from app.schemas.recommendation import RecommendationRequest
from app.services.agent_service import AGENT_REGISTRY, get_agent_response_with_confidence
from app.services.market_service import fetch_job_market_data_async
from app.services.outcome_service import get_intent_recalibration
from app.services.profile_service import get_user_profile
from app.services.psychometric_service import get_user_psychometric_profile
from app.services.recommendation_service import (
	generate_career_recommendations,
	get_recommendation_feedback,
	get_recommendation_history,
	get_personalization_profile,
)


INTENT_HINTS = {
	"interview_prep": ["interview", "mock", "hr round", "technical round"],
	"learning_path": ["learn", "roadmap", "upskill", "study plan", "course"],
	"recommendation": ["recommend", "suggest", "career option", "best role"],
	"job_matching": ["job", "match", "fit", "eligibility", "openings"],
	"networking": ["network", "linkedin", "mentor", "referral", "outreach"],
}


ROLE_SKILL_LIBRARY = {
	"data scientist": ["python", "sql", "statistics", "machine learning", "nlp"],
	"data analyst": ["sql", "excel", "tableau", "power bi", "statistics"],
	"ml engineer": ["python", "machine learning", "deep learning", "docker", "kubernetes"],
	"backend developer": ["python", "fastapi", "sql", "docker", "aws"],
	"devops engineer": ["docker", "kubernetes", "aws", "linux", "monitoring"],
}


@dataclass
class PlannerStep:
	name: str
	detail: str
	duration_ms: int | None = None
	depends_on: list[str] = field(default_factory=list)
	error_type: str | None = None


@dataclass
class PlannerResult:
	plan_id: str
	intent: str
	reply: str
	next_step: str
	confidence: float
	plan_variant: str | None = None
	plan_variant_reason: str | None = None
	planner_duration_ms: int = 0
	keyword_matches: list[str] = field(default_factory=list)
	outcome_scores: list[dict[str, object]] = field(default_factory=list)
	steps: list[PlannerStep] = field(default_factory=list)


@dataclass
class PlannerState:
	message: str
	context: dict[str, Any]
	user_id: str | None = None
	plan_id: str = ""
	planner_started_at: float = 0.0
	intent: str = "career_assessment"
	auxiliary_intents: list[str] = field(default_factory=list)
	confidence: float = 0.0
	keyword_matches: list[str] = field(default_factory=list)
	primary_reply: str = ""
	primary_next_step: str = ""
	supporting_notes: list[str] = field(default_factory=list)
	profile_memory_summary: str = ""
	psychometric_summary: str = ""
	history_summary: str = ""
	feedback_summary: str = ""
	recommendation_summary: str = ""
	skill_gap_summary: str = ""
	interview_plan_summary: str = ""
	learning_plan_summary: str = ""
	networking_plan_summary: str = ""
	job_market_summary: str = ""
	recommended_roles: list[str] = field(default_factory=list)
	rejected_roles: set[str] = field(default_factory=set)
	skill_gaps: list[str] = field(default_factory=list)
	outcome_scores: dict[str, int] = field(default_factory=dict)
	intent_recalibration: dict[str, int] = field(default_factory=dict)
	plan_variant: str | None = None
	plan_variant_reason: str | None = None
	steps: list[PlannerStep] = field(default_factory=list)


def _context_fingerprint(context: dict[str, Any]) -> str:
	"""Return a stable fingerprint string for the request context payload."""
	try:
		serialized = json.dumps(context, sort_keys=True, default=str)
	except Exception:
		serialized = str(context)
	return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:12]


def _build_plan_id(state: PlannerState) -> str:
	"""Build a deterministic plan id from user/message/context and planner start time."""
	seed = f"{state.user_id or 'anonymous'}|{state.message.strip().lower()}|{_context_fingerprint(state.context)}|{state.planner_started_at:.6f}"
	return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def _append_step(
	state: PlannerState,
	name: str,
	detail: str,
	*,
	started_at: float | None = None,
	depends_on: list[str] | None = None,
	error_type: str | None = None,
) -> None:
	"""Append a planner step with optional execution timing and dependency metadata."""
	duration_ms = None
	if started_at is not None:
		duration_ms = max(0, int((perf_counter() - started_at) * 1000))
	state.steps.append(
		PlannerStep(
			name=name,
			detail=detail,
			duration_ms=duration_ms,
			depends_on=list(depends_on or []),
			error_type=error_type,
		)
	)


async def _run_tool_safely(
	state: PlannerState,
	*,
	step_name: str,
	depends_on: list[str],
	runner,
	failure_detail: str,
) -> None:
	"""Run an async planner tool and record structured failure metadata without aborting the plan."""
	started_at = perf_counter()
	try:
		await runner(state)
	except Exception as exc:
		_append_step(
			state,
			step_name,
			f"{failure_detail}. Fallback: continued plan without this tool output.",
			started_at=started_at,
			depends_on=depends_on,
			error_type=exc.__class__.__name__,
		)


def _run_sync_step_safely(
	state: PlannerState,
	*,
	step_name: str,
	depends_on: list[str],
	runner,
	failure_detail: str,
) -> None:
	"""Run a sync planner step and record structured failure metadata without aborting the plan."""
	started_at = perf_counter()
	try:
		runner(state)
	except Exception as exc:
		_append_step(
			state,
			step_name,
			f"{failure_detail}. Fallback: continued plan without this step output.",
			started_at=started_at,
			depends_on=depends_on,
			error_type=exc.__class__.__name__,
		)


def _secondary_agent_names(intent: str) -> list[str]:
	"""Return supporting specialists that complement the primary routed agent."""
	return {
		"career_assessment": ["learning_path"],
		"interview_prep": ["learning_path"],
		"job_matching": ["recommendation", "networking"],
		"learning_path": ["career_assessment"],
		"networking": ["job_matching"],
		"recommendation": ["job_matching"],
		"feedback": ["recommendation"],
	}.get(intent, [])


def _detect_auxiliary_intents(message: str, primary_intent: str) -> list[str]:
	"""Infer additional intents when a user asks for mixed outcomes in one turn."""
	normalized = message.lower().strip()
	if not normalized:
		return []
	result: list[str] = []
	for intent_name, hints in INTENT_HINTS.items():
		if intent_name == primary_intent:
			continue
		if any(hint in normalized for hint in hints):
			result.append(intent_name)
	return result[:2]


def _education_level(context: dict[str, Any]) -> str | None:
	"""Return a normalized education level value when present."""
	value = context.get("education_level")
	if value is None:
		return None
	text = str(value).strip().lower()
	return text or None


def _supports_recommendation_tool(context: dict[str, Any]) -> bool:
	"""Require minimum structured evidence before invoking the recommendation engine."""
	skills = context.get("skills") if isinstance(context.get("skills"), list) else []
	interests = context.get("interests") if isinstance(context.get("interests"), list) else []
	return bool(skills) and bool(interests) and bool(_education_level(context))


def _target_role_from_context(context: dict[str, Any]) -> str | None:
	"""Return a cleaned target role from merged request/profile context when present."""
	value = context.get("target_role")
	if value is None:
		return None
	text = str(value).strip()
	return text or None


def _resolve_target_role(state: PlannerState) -> str | None:
	"""Pick a target role from explicit context, recommendation tool output, or recency hints."""
	from_context = _target_role_from_context(state.context)
	if from_context:
		return from_context
	if state.recommended_roles:
		return state.recommended_roles[0]
	if "data scientist" in state.history_summary.lower():
		return "data scientist"
	return None


def _required_skills_for_role(role: str | None) -> list[str]:
	"""Return a best-effort required-skill baseline for known role families."""
	if not role:
		return []
	normalized = role.strip().lower()
	for role_name, skills in ROLE_SKILL_LIBRARY.items():
		if role_name in normalized or normalized in role_name:
			return skills
	return []


def _skill_gap_for_role(role: str | None, current_skills: list[str]) -> tuple[list[str], list[str]]:
	"""Return matched and missing skills for a role based on context/profile signals."""
	required = _required_skills_for_role(role)
	if not required:
		return [], []
	current = {str(item).strip().lower() for item in current_skills if str(item).strip()}
	matched = [skill for skill in required if skill.lower() in current]
	missing = [skill for skill in required if skill.lower() not in current]
	return matched, missing


def _summarize_profile_memory(profile: dict[str, Any]) -> str:
	"""Convert durable profile memory into a compact planner note."""
	if not profile:
		return ""
	parts: list[str] = []
	if profile.get("target_role"):
		parts.append(f"target role {profile['target_role']}")
	if profile.get("skills"):
		parts.append(f"skills: {', '.join([str(item) for item in profile['skills'][:4]])}")
	if profile.get("interests"):
		parts.append(f"interests: {', '.join([str(item) for item in profile['interests'][:3]])}")
	if not parts:
		return ""
	return "Profile memory loaded: " + "; ".join(parts) + "."


def _summarize_psychometric_profile(psychometric: dict[str, Any] | None) -> str:
	"""Summarize psychometric traits/domains for downstream planning decisions."""
	if not psychometric:
		return ""
	top_traits = psychometric.get("top_traits") or []
	recommended_domains = psychometric.get("recommended_domains") or []
	if not top_traits and not recommended_domains:
		return ""
	trait_text = ", ".join([str(item) for item in top_traits[:3]])
	domain_text = ", ".join([str(item) for item in recommended_domains[:3]])
	parts: list[str] = []
	if trait_text:
		parts.append(f"top traits: {trait_text}")
	if domain_text:
		parts.append(f"recommended domains: {domain_text}")
	return "Psychometric signal: " + "; ".join(parts) + "."


def _summarize_history(history: list[dict]) -> str:
	"""Convert recent recommendation history into a compact recap."""
	if not history:
		return ""
	latest = history[0]
	recommendations = latest.get("recommendations", [])
	roles = [str(item.get("role", "")).strip() for item in recommendations if str(item.get("role", "")).strip()]
	if not roles:
		return ""
	return f"Recent recommendation history: latest run suggested {', '.join(roles[:3])}."


def _summarize_feedback(feedback_items: list[dict]) -> tuple[str, set[str]]:
	"""Summarize explicit feedback and return rejected roles for planner filtering."""
	if not feedback_items:
		return "", set()
	rejected_roles = {
		str(item.get("role", "")).strip().lower()
		for item in feedback_items
		if item.get("helpful") is False and str(item.get("role", "")).strip()
	}
	helpful_roles = [
		str(item.get("role", "")).strip()
		for item in feedback_items
		if item.get("helpful") is True and str(item.get("role", "")).strip()
	]
	parts: list[str] = []
	if helpful_roles:
		parts.append(f"Helpful feedback history favors {', '.join(helpful_roles[:2])}.")
	if rejected_roles:
		rejected_text = ", ".join(sorted(rejected_roles)[:2])
		parts.append(f"Avoid previously rejected roles such as {rejected_text} unless the user asks explicitly.")
	return " ".join(parts), rejected_roles


def _summarize_recommendations(top_roles: list[Any]) -> str:
	"""Convert top recommendation objects into a compact guidance block."""
	if not top_roles:
		return ""
	lines = ["Tool result: top recommended roles from your current profile signals:"]
	for item in top_roles[:3]:
		lines.append(f"- {item.role} ({item.confidence * 100:.0f}%): {item.reason}")
	return "\n".join(lines)


async def _maybe_run_recommendation_tool(state: PlannerState) -> None:
	"""Attach recommendation-engine output when the request has enough structure."""
	if not _supports_recommendation_tool(state.context):
		return

	personalization_profile = await get_personalization_profile(state.user_id or "")
	payload = RecommendationRequest(
		user_id=state.user_id or "",
		interests=[str(item) for item in state.context.get("interests", [])],
		skills=[str(item) for item in state.context.get("skills", [])],
		education_level=_education_level(state.context) or "bachelor",
	)
	recommendations = generate_career_recommendations(
		payload,
		top_k=3,
		personalization_profile=personalization_profile,
	)
	if state.rejected_roles:
		recommendations = [item for item in recommendations if item.role.strip().lower() not in state.rejected_roles]
	if recommendations:
		state.recommended_roles = [item.role for item in recommendations]
		state.recommendation_summary = _summarize_recommendations(recommendations)
		_append_step(
			state,
			"recommendation_tool",
			"Generated ranked role suggestions from structured profile signals.",
			depends_on=[f"primary_{state.intent}"],
		)


async def _maybe_load_recommendation_memory(state: PlannerState) -> None:
	"""Load prior recommendation runs and feedback as reusable planner memory."""
	if not state.user_id:
		return
	history = await get_recommendation_history(state.user_id, limit=3)
	feedback_items = await get_recommendation_feedback(state.user_id)
	state.history_summary = _summarize_history(history)
	state.feedback_summary, state.rejected_roles = _summarize_feedback(feedback_items)
	if state.history_summary:
		_append_step(
			state,
			"history_tool",
			"Loaded recent recommendation history for planner memory.",
			depends_on=["intent_router"],
		)
	if state.feedback_summary:
		_append_step(
			state,
			"feedback_tool",
			"Loaded recommendation feedback to guide planner decisions.",
			depends_on=["history_tool"],
		)


async def _maybe_load_profile_memory_tool(state: PlannerState) -> None:
	"""Load durable profile and psychometric memory for non-recommendation flows."""
	if not state.user_id:
		return
	profile_started = perf_counter()
	profile = await get_user_profile(state.user_id)
	state.profile_memory_summary = _summarize_profile_memory(profile)
	if state.profile_memory_summary:
		_append_step(
			state,
			"profile_tool",
			"Loaded long-lived profile memory for planning context.",
			started_at=profile_started,
			depends_on=["intent_router"],
		)
	psychometric_started = perf_counter()
	psychometric = await get_user_psychometric_profile(state.user_id)
	state.psychometric_summary = _summarize_psychometric_profile(psychometric)
	if state.psychometric_summary:
		_append_step(
			state,
			"psychometric_tool",
			"Loaded psychometric traits and domain signals for personalization.",
			started_at=psychometric_started,
			depends_on=["profile_tool"],
		)


def _job_query_candidates(state: PlannerState) -> list[str]:
	"""Choose a small set of role queries for the jobs tool."""
	queries: list[str] = []
	target_role = _target_role_from_context(state.context)
	if target_role:
		queries.append(target_role)
	for role in state.recommended_roles:
		if role not in queries:
			queries.append(role)
	if state.history_summary and not queries:
		# Best-effort fallback: history summary already contains recent roles in text form.
		queries.append("data scientist")
	return queries[:2]


def _summarize_jobs(role: str, jobs: list[Any], source: str) -> str:
	"""Render a concise jobs snapshot for the planner response."""
	if not jobs:
		return ""
	items = [f"- {item.job_title} at {item.company} ({item.location})" for item in jobs[:3]]
	return f"Job-market snapshot for {role} via {source}:\n" + "\n".join(items)


async def _maybe_run_job_market_tool(state: PlannerState) -> None:
	"""Attach a live job-market snapshot for matching/networking/recommendation flows."""
	intents = {state.intent, *state.auxiliary_intents}
	if intents.isdisjoint({"job_matching", "networking", "recommendation"}):
		return
	queries = _job_query_candidates(state)
	if not queries:
		return
	query = queries[0]
	tool_started = perf_counter()
	source, jobs = await fetch_job_market_data_async(query, limit=3)
	if jobs:
		state.job_market_summary = _summarize_jobs(query, jobs, source)
		_append_step(
			state,
			"jobs_tool",
			f"Fetched current market roles for query '{query}'.",
			started_at=tool_started,
			depends_on=[f"primary_{state.intent}"],
		)


async def _maybe_run_skill_gap_tool(state: PlannerState) -> None:
	"""Build a role-specific skill gap snapshot for learning/interview/job flows."""
	intents = {state.intent, *state.auxiliary_intents}
	if intents.isdisjoint({"learning_path", "interview_prep", "job_matching", "career_assessment"}):
		return
	role = _resolve_target_role(state)
	matched, missing = _skill_gap_for_role(role, [str(item) for item in state.context.get("skills", [])])
	if not role or (not matched and not missing):
		return
	state.skill_gaps = missing[:4]
	matched_text = ", ".join(matched[:3]) if matched else "none captured yet"
	missing_text = ", ".join(missing[:4]) if missing else "no major gaps detected from current role baseline"
	state.skill_gap_summary = (
		f"Skill-gap signal for {role}: matched={matched_text}; missing={missing_text}."
	)
	_append_step(
		state,
		"skill_gap_tool",
		f"Compared your current skills against baseline requirements for '{role}'.",
		depends_on=["profile_tool"],
	)


async def _maybe_run_interview_tool(state: PlannerState) -> None:
	"""Generate a focused interview prep sprint when interview intent is present."""
	intents = {state.intent, *state.auxiliary_intents}
	if "interview_prep" not in intents:
		return
	role = _resolve_target_role(state) or "your target role"
	focus = state.skill_gaps[:3] if state.skill_gaps else ["problem solving", "communication", "project storytelling"]
	variant_a = (
		f"Interview sprint plan (Variant A, execution-first) for {role}: "
		f"Day 1 solve one timed problem and one role-specific case ({focus[0]}), "
		f"Day 2 run a mock interview with feedback loops ({focus[1] if len(focus) > 1 else focus[0]}), "
		f"Day 3 tighten STAR stories and redo weak sections ({focus[2] if len(focus) > 2 else focus[0]})."
	)
	variant_b = (
		f"Interview sprint plan (Variant B, foundation-first) for {role}: "
		f"Day 1 revise core concepts and notes ({focus[0]}), "
		f"Day 2 structured Q&A drill and explanation practice ({focus[1] if len(focus) > 1 else focus[0]}), "
		f"Day 3 run a mock interview and produce a revision checklist ({focus[2] if len(focus) > 2 else focus[0]})."
	)
	variant_label, variant_reason = _select_plan_variant(state, "interview_prep")
	state.interview_plan_summary = variant_a if variant_label == "A" else variant_b
	_record_variant_selection(state, "interview_prep", variant_label, variant_reason)
	_append_step(
		state,
		"interview_tool",
		f"Built a short interview sprint (variant {variant_label}) based on inferred gaps and role focus.",
		depends_on=["skill_gap_tool"],
	)


async def _maybe_run_learning_path_tool(state: PlannerState) -> None:
	"""Generate a compact learning sprint from skill gaps and psychometric preferences."""
	intents = {state.intent, *state.auxiliary_intents}
	if intents.isdisjoint({"learning_path", "career_assessment", "recommendation"}):
		return
	role = _resolve_target_role(state) or "your role focus"
	domain_hint = ""
	if state.psychometric_summary:
		domain_hint = " Align electives with psychometric-fit domains from your profile."
	if state.skill_gaps:
		focus_text = ", ".join(state.skill_gaps[:3])
	else:
		focus_text = "core role fundamentals"
	variant_a = (
		f"Learning sprint (Variant A, execution-first) for {role}: Week 1 focused practice on {focus_text}, "
		"Week 2 mini-project implementation, Week 3 project hardening with reviews, "
		"Week 4 portfolio publish plus interview-aligned revision." + domain_hint
	)
	variant_b = (
		f"Learning sprint (Variant B, foundation-first) for {role}: Week 1 foundations and concept drills, "
		f"Week 2 guided labs on {focus_text}, Week 3 structured capstone build, "
		"Week 4 portfolio documentation and reflection." + domain_hint
	)
	variant_label, variant_reason = _select_plan_variant(state, "learning_path")
	state.learning_plan_summary = variant_a if variant_label == "A" else variant_b
	_record_variant_selection(state, "learning_path", variant_label, variant_reason)
	_append_step(
		state,
		"learning_tool",
		f"Generated a 4-week learning sprint (variant {variant_label}) from current gaps and profile signals.",
		depends_on=["skill_gap_tool"],
	)


async def _maybe_run_networking_tool(state: PlannerState) -> None:
	"""Create a lightweight networking outreach plan when networking signal is present."""
	intents = {state.intent, *state.auxiliary_intents}
	if "networking" not in intents:
		return
	role = _resolve_target_role(state) or "your target role"
	target_companies = [str(item).strip() for item in state.context.get("target_companies", []) if str(item).strip()]
	company_text = ", ".join(target_companies[:3]) if target_companies else "your top 3 target companies"
	state.networking_plan_summary = (
		f"Networking plan for {role}: shortlist alumni/role peers at {company_text}, "
		"send 5 personalized outreach messages per week, and request one informational call every 10 days."
	)
	_append_step(
		state,
		"networking_tool",
		"Prepared targeted outreach steps based on role and company preferences.",
		depends_on=["profile_tool"],
	)


def _collect_supporting_notes(state: PlannerState) -> None:
	"""Run lightweight specialist handoffs based on the routed primary intent."""
	agent_names: list[str] = []
	for intent_name in [state.intent, *state.auxiliary_intents]:
		for agent_name in _secondary_agent_names(intent_name):
			if agent_name not in agent_names:
				agent_names.append(agent_name)
	for agent_name in agent_names:
		agent = AGENT_REGISTRY.get(agent_name)
		if agent is None:
			continue
		note = agent.respond(state.message, state.context)
		if not note.strip():
			continue
		state.supporting_notes.append(f"{agent_name.replace('_', ' ').title()} perspective:\n{note}")
		_append_step(
			state,
			f"support_{agent_name}",
			f"Collected supporting guidance from {agent_name}.",
			depends_on=[f"primary_{state.intent}"],
		)


def _select_plan_variant(state: PlannerState, intent_name: str) -> tuple[str, str]:
	"""Pick a deterministic plan variant label and rationale for high-impact intents."""
	message_text = state.message.lower()
	quick_tokens = ("quick", "fast", "asap", "urgent", "tomorrow", "short")
	deep_tokens = ("detailed", "comprehensive", "thorough", "in-depth", "deep")
	has_quick_signal = any(token in message_text for token in quick_tokens)
	has_deep_signal = any(token in message_text for token in deep_tokens)
	if has_quick_signal and not has_deep_signal:
		return "A", "message requested a faster execution-first plan"
	if has_deep_signal and not has_quick_signal:
		return "B", "message requested a deeper foundation-first plan"
	recalibration = int(state.intent_recalibration.get(intent_name, 0))
	if recalibration < 0:
		return "B", "recent outcomes were weaker, so a structure-first variant was selected"
	if recalibration > 0:
		return "A", "recent outcomes were strong, so an execution-first variant was selected"
	if state.plan_id:
		return (
			("A", "deterministic A/B split from plan id")
			if (int(state.plan_id[-1], 16) % 2 == 0)
			else ("B", "deterministic A/B split from plan id")
		)
	return "A", "defaulted to baseline variant"


def _record_variant_selection(state: PlannerState, intent_name: str, variant_label: str, reason: str) -> None:
	"""Persist selected variant metadata for the primary routed intent."""
	if state.intent != intent_name:
		return
	state.plan_variant = f"{intent_name}:{variant_label}"
	state.plan_variant_reason = reason
	_append_step(
		state,
		"plan_variant_selector",
		f"Selected variant {variant_label} for {intent_name}: {reason}.",
		depends_on=[f"primary_{state.intent}"],
	)


def _build_final_reply(state: PlannerState) -> str:
	"""Compose the planner result into one grounded base reply for optional LLM refinement."""
	sections = [state.primary_reply]
	if state.profile_memory_summary:
		sections.append(state.profile_memory_summary)
	if state.psychometric_summary:
		sections.append(state.psychometric_summary)
	if state.feedback_summary:
		sections.append(state.feedback_summary)
	if state.history_summary:
		sections.append(state.history_summary)
	if state.recommendation_summary:
		sections.append(state.recommendation_summary)
	if state.skill_gap_summary:
		sections.append(state.skill_gap_summary)
	if state.interview_plan_summary:
		sections.append(state.interview_plan_summary)
	if state.learning_plan_summary:
		sections.append(state.learning_plan_summary)
	if state.networking_plan_summary:
		sections.append(state.networking_plan_summary)
	if state.job_market_summary:
		sections.append(state.job_market_summary)
	sections.extend(state.supporting_notes[:2])
	return "\n\n".join(section.strip() for section in sections if section and section.strip())


def _score_to_band(score: int) -> str:
	"""Convert numeric evaluator score to a compact quality band."""
	if score >= 85:
		return "strong"
	if score >= 70:
		return "good"
	if score >= 55:
		return "moderate"
	return "low"


def _compute_outcome_scores(state: PlannerState) -> dict[str, int]:
	"""Estimate intent-wise plan quality from tool coverage and actionability signals."""
	scores: dict[str, int] = {}
	intents = [state.intent, *state.auxiliary_intents]
	for intent_name in intents:
		if intent_name == "interview_prep":
			score = 48
			score += 20 if state.interview_plan_summary else 0
			score += 14 if state.skill_gap_summary else 0
			score += 10 if state.profile_memory_summary else 0
			score += 8 if state.psychometric_summary else 0
			scores[intent_name] = min(100, score)
			continue
		if intent_name == "learning_path":
			score = 45
			score += 22 if state.learning_plan_summary else 0
			score += 14 if state.skill_gap_summary else 0
			score += 9 if state.psychometric_summary else 0
			score += 8 if state.profile_memory_summary else 0
			scores[intent_name] = min(100, score)
			continue
		if intent_name in {"recommendation", "job_matching"}:
			score = 46
			score += 20 if state.recommendation_summary else 0
			score += 14 if state.job_market_summary else 0
			score += 10 if state.feedback_summary else 0
			score += 8 if state.history_summary else 0
			scores[intent_name] = min(100, score)
			continue
		if intent_name == "networking":
			score = 47
			score += 20 if state.networking_plan_summary else 0
			score += 12 if state.job_market_summary else 0
			score += 11 if state.profile_memory_summary else 0
			score += 8 if state.psychometric_summary else 0
			scores[intent_name] = min(100, score)
			continue
		# career_assessment and fallback intents
		score = 44
		score += 16 if state.profile_memory_summary else 0
		score += 14 if state.psychometric_summary else 0
		score += 14 if state.skill_gap_summary else 0
		score += 10 if state.learning_plan_summary else 0
		scores[intent_name] = min(100, score)
	return scores


def _maybe_run_outcome_evaluator_tool(state: PlannerState) -> None:
	"""Attach deterministic evaluator scores so each intent has a measurable outcome quality signal."""
	raw_scores = _compute_outcome_scores(state)
	state.outcome_scores = {}
	for intent_name, score in raw_scores.items():
		adjusted = score + int(state.intent_recalibration.get(intent_name, 0))
		state.outcome_scores[intent_name] = max(0, min(100, adjusted))
	if not state.outcome_scores:
		return
	ordered = sorted(state.outcome_scores.items(), key=lambda item: item[1], reverse=True)
	summary = ", ".join([f"{name}={score} ({_score_to_band(score)})" for name, score in ordered])
	if state.intent_recalibration:
		calib = ", ".join([f"{name}:{offset:+d}" for name, offset in sorted(state.intent_recalibration.items()) if offset])
		if calib:
			summary = f"{summary}. calibrated_offsets={calib}"
	_append_step(
		state,
		"outcome_evaluator_tool",
		f"Computed intent outcome quality scores: {summary}.",
		depends_on=[f"primary_{state.intent}"],
	)


async def plan_agent_response(
	message: str,
	context: dict[str, Any] | None = None,
	*,
	user_id: str | None = None,
) -> PlannerResult:
	"""Execute a small multi-step orchestration over existing agents and tools."""
	state = PlannerState(message=message, context=dict(context or {}), user_id=user_id)
	state.planner_started_at = perf_counter()
	state.plan_id = _build_plan_id(state)
	intent, reply, next_step, confidence, keyword_matches = get_agent_response_with_confidence(message, state.context)
	state.intent = intent
	state.primary_reply = reply
	state.primary_next_step = next_step
	state.confidence = confidence
	state.keyword_matches = keyword_matches
	state.auxiliary_intents = _detect_auxiliary_intents(message, intent)
	if state.user_id:
		state.intent_recalibration = await get_intent_recalibration(state.user_id, [state.intent, *state.auxiliary_intents])
	_append_step(
		state,
		"intent_router",
		f"Selected primary intent '{intent}' with confidence {confidence:.2f}.",
	)
	_append_step(
		state,
		f"primary_{intent}",
		f"Generated primary guidance using {intent}.",
		depends_on=["intent_router"],
	)
	if state.auxiliary_intents:
		_append_step(
			state,
			"intent_blender",
			f"Detected auxiliary intents: {', '.join(state.auxiliary_intents)}.",
			depends_on=["intent_router"],
		)

	await _run_tool_safely(
		state,
		step_name="history_tool",
		depends_on=["intent_router"],
		runner=_maybe_load_recommendation_memory,
		failure_detail="Failed to load recommendation history/feedback memory",
	)
	await _run_tool_safely(
		state,
		step_name="profile_tool",
		depends_on=["intent_router"],
		runner=_maybe_load_profile_memory_tool,
		failure_detail="Failed to load profile or psychometric memory",
	)
	_run_sync_step_safely(
		state,
		step_name="support_router",
		depends_on=[f"primary_{state.intent}"],
		runner=_collect_supporting_notes,
		failure_detail="Failed to collect supporting specialist perspectives",
	)
	await _run_tool_safely(
		state,
		step_name="recommendation_tool",
		depends_on=[f"primary_{state.intent}"],
		runner=_maybe_run_recommendation_tool,
		failure_detail="Recommendation engine execution failed",
	)
	await _run_tool_safely(
		state,
		step_name="skill_gap_tool",
		depends_on=["profile_tool"],
		runner=_maybe_run_skill_gap_tool,
		failure_detail="Skill-gap analyzer failed",
	)
	await _run_tool_safely(
		state,
		step_name="interview_tool",
		depends_on=["skill_gap_tool"],
		runner=_maybe_run_interview_tool,
		failure_detail="Interview sprint builder failed",
	)
	await _run_tool_safely(
		state,
		step_name="learning_tool",
		depends_on=["skill_gap_tool"],
		runner=_maybe_run_learning_path_tool,
		failure_detail="Learning sprint builder failed",
	)
	await _run_tool_safely(
		state,
		step_name="networking_tool",
		depends_on=["profile_tool"],
		runner=_maybe_run_networking_tool,
		failure_detail="Networking plan builder failed",
	)
	await _run_tool_safely(
		state,
		step_name="jobs_tool",
		depends_on=[f"primary_{state.intent}"],
		runner=_maybe_run_job_market_tool,
		failure_detail="Job market fetch failed",
	)
	_run_sync_step_safely(
		state,
		step_name="outcome_evaluator_tool",
		depends_on=[f"primary_{state.intent}"],
		runner=_maybe_run_outcome_evaluator_tool,
		failure_detail="Outcome evaluator failed",
	)

	return PlannerResult(
		plan_id=state.plan_id,
		intent=state.intent,
		reply=_build_final_reply(state),
		next_step=state.primary_next_step,
		confidence=state.confidence,
		plan_variant=state.plan_variant,
		plan_variant_reason=state.plan_variant_reason,
		planner_duration_ms=max(0, int((perf_counter() - state.planner_started_at) * 1000)),
		keyword_matches=state.keyword_matches,
		outcome_scores=[{"intent": name, "score": score} for name, score in sorted(state.outcome_scores.items())],
		steps=state.steps,
	)