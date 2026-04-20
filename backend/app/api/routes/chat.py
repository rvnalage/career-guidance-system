"""Chat API routes for anonymous and authenticated career guidance conversations.

This module coordinates the full chat pipeline: history persistence, profile-memory
merge, intent routing, RAG grounding, optional LLM refinement, and profile updates.
"""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends

from app.database.models import User
from app.dependencies import get_current_user
from app.schemas.chat import (
	ChatMeRequest,
	ChatOutcomeRequest,
	ChatOutcomeResponse,
	ChatRequest,
	ChatResponse,
	NetworkingMetricsRequest,
	NetworkingMetricsResponse,
)
from app.services.critic_service import verify_and_repair_reply
from app.services.history_service import append_message
from app.services.llm_service import generate_llm_reply, limit_sentences
from app.services.outcome_service import record_chat_outcome
from app.services.planner_service import PlannerStep, plan_agent_response
from app.services.profile_service import (
	extract_networking_metrics,
	get_user_profile,
	merge_context_with_profile,
	record_networking_metrics,
	summarize_profile,
	update_user_profile,
)
from app.services.rag_service import get_rag_payload_with_metrics
from app.services.psychometric_service import save_user_psychometric_profile
from app.schemas.psychometric import PsychometricRequest
from app.config import settings
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _build_networking_metrics_response(user_id: str, metrics: dict[str, object] | None) -> NetworkingMetricsResponse:
	"""Map stored networking metrics to an API response payload."""
	metrics = metrics or {}
	avg_hours, avg_rate = extract_networking_metrics({"networking_metrics": metrics})
	return NetworkingMetricsResponse(
		user_id=user_id,
		avg_weekly_availability_hours=float(avg_hours) if avg_hours is not None else None,
		avg_response_rate_percent=float(avg_rate) if avg_rate is not None else None,
		last_weekly_availability_hours=int(metrics.get("last_weekly_availability_hours")) if metrics.get("last_weekly_availability_hours") is not None else None,
		last_response_rate_percent=int(metrics.get("last_response_rate_percent")) if metrics.get("last_response_rate_percent") is not None else None,
		samples=int(metrics.get("samples", 0)),
	)


async def _load_current_networking_metrics(user_id: str) -> NetworkingMetricsResponse:
	"""Load current networking metrics from profile memory and map into API response."""
	profile = await get_user_profile(user_id)
	metrics = profile.get("networking_metrics") if isinstance(profile.get("networking_metrics"), dict) else {}
	return _build_networking_metrics_response(user_id, metrics)


def _serialize_planner_steps(steps: list[PlannerStep]) -> list[dict[str, object]]:
	"""Normalize planner step objects into response/history metadata dictionaries."""
	result: list[dict[str, object]] = []
	for step in steps:
		result.append(
			{
				"name": step.name,
				"detail": step.detail,
				"duration_ms": step.duration_ms,
				"depends_on": step.depends_on,
				"error_type": step.error_type,
			}
		)
	return result


@router.post("/outcome", response_model=ChatOutcomeResponse)
async def record_chat_outcome_anonymous(payload: ChatOutcomeRequest) -> ChatOutcomeResponse:
	"""Store outcome telemetry for anonymous chat sessions."""
	user_id = "frontend-session-user"
	document = await record_chat_outcome(
		user_id,
		{
			"plan_id": payload.plan_id,
			"intent": payload.intent,
			"helpful": payload.helpful,
			"accepted_next_step": payload.accepted_next_step,
			"clicked_suggestion": payload.clicked_suggestion,
			"rating": payload.rating,
			"source": payload.source,
		},
	)
	return ChatOutcomeResponse(
		user_id=user_id,
		plan_id=document.get("plan_id"),
		intent=str(document.get("intent") or "career_assessment"),
		success_score=int(document.get("success_score", 0)),
	)


@router.post("/outcome/me", response_model=ChatOutcomeResponse)
async def record_chat_outcome_me(
	payload: ChatOutcomeRequest,
	current_user: Annotated[User, Depends(get_current_user)],
) -> ChatOutcomeResponse:
	"""Store outcome telemetry for authenticated chat sessions."""
	document = await record_chat_outcome(
		current_user.id,
		{
			"plan_id": payload.plan_id,
			"intent": payload.intent,
			"helpful": payload.helpful,
			"accepted_next_step": payload.accepted_next_step,
			"clicked_suggestion": payload.clicked_suggestion,
			"rating": payload.rating,
			"source": payload.source,
		},
	)
	return ChatOutcomeResponse(
		user_id=current_user.id,
		plan_id=document.get("plan_id"),
		intent=str(document.get("intent") or "career_assessment"),
		success_score=int(document.get("success_score", 0)),
	)


@router.post("/networking-metrics", response_model=NetworkingMetricsResponse)
async def record_networking_metrics_anonymous(payload: NetworkingMetricsRequest) -> NetworkingMetricsResponse:
	"""Store networking cadence metrics from anonymous clients and return updated rolling values."""
	user_id = (payload.user_id or "frontend-session-user").strip() or "frontend-session-user"
	metrics = await record_networking_metrics(
		user_id,
		weekly_availability_hours=payload.weekly_availability_hours,
		response_rate_percent=payload.response_rate_percent,
	)
	return _build_networking_metrics_response(user_id, metrics)


@router.post("/networking-metrics/me", response_model=NetworkingMetricsResponse)
async def record_networking_metrics_me(
	payload: NetworkingMetricsRequest,
	current_user: Annotated[User, Depends(get_current_user)],
) -> NetworkingMetricsResponse:
	"""Store networking cadence metrics for authenticated users and return updated rolling values."""
	metrics = await record_networking_metrics(
		current_user.id,
		weekly_availability_hours=payload.weekly_availability_hours,
		response_rate_percent=payload.response_rate_percent,
	)
	return _build_networking_metrics_response(current_user.id, metrics)


@router.get("/networking-metrics", response_model=NetworkingMetricsResponse)
async def get_networking_metrics_anonymous(user_id: str | None = None) -> NetworkingMetricsResponse:
	"""Return current networking metrics for anonymous/session use without writing new data."""
	resolved_user_id = (user_id or "frontend-session-user").strip() or "frontend-session-user"
	return await _load_current_networking_metrics(resolved_user_id)


@router.get("/networking-metrics/me", response_model=NetworkingMetricsResponse)
async def get_networking_metrics_me(
	current_user: Annotated[User, Depends(get_current_user)],
) -> NetworkingMetricsResponse:
	"""Return current networking metrics for the authenticated user without writing new data."""
	return await _load_current_networking_metrics(current_user.id)


@router.post("/message", response_model=ChatResponse)
async def send_message(payload: ChatRequest) -> ChatResponse:
	"""Process an anonymous chat message and return a grounded assistant response."""
	start_time = perf_counter()
	base_context = dict(payload.context or {})
	if payload.skills:
		base_context["skills"] = payload.skills
	if payload.interests:
		base_context["interests"] = payload.interests
	if payload.education_level:
		base_context["education_level"] = payload.education_level

	# Persist the raw user turn first so downstream enrichment failures do not lose the request.
	await append_message(payload.user_id, "user", payload.message)
	profile = await get_user_profile(payload.user_id)
	# Merge explicit request context with long-lived profile memory before intent routing.
	resolved_context = merge_context_with_profile(base_context, profile)

	planner_result = await plan_agent_response(
		payload.message,
		resolved_context,
		user_id=payload.user_id,
	)
	intent = planner_result.intent
	reply = planner_result.reply
	next_step = planner_result.next_step
	confidence = planner_result.confidence
	keyword_matches = planner_result.keyword_matches
	# RAG is computed independently from the agent so the response can stay grounded even when the LLM is disabled.
	rag_context, rag_citations, rag_metrics = get_rag_payload_with_metrics(
		payload.message,
		intent=intent,
		target_role=str(resolved_context.get("target_role") or "").strip() or None,
		skill_gaps=planner_result.skill_gaps,
	)
	base_reply = reply
	augmented_reply = base_reply
	if rag_context:
		augmented_reply = f"{base_reply}\n\nRelevant references:\n{rag_context}"
	profile_summary = summarize_profile(profile)
	# Pass only the agent reply here; rag_context is already sent separately so we avoid duplicating retrieval text.
	enhanced_reply = generate_llm_reply(
		message=payload.message,
		intent=intent,
		base_reply=base_reply,
		next_step=next_step,
		rag_context=rag_context,
		intent_confidence=confidence,
		keyword_matches=keyword_matches,
		user_profile_summary=profile_summary,
		skill_gaps=planner_result.skill_gaps if planner_result.skill_gaps else None,
	)
	final_reply = enhanced_reply or augmented_reply
	final_reply = limit_sentences(final_reply, settings.chat_reply_max_sentences)
	critic_result = verify_and_repair_reply(
		reply=final_reply,
		intent=intent,
		next_step=next_step,
		context=resolved_context,
	)
	final_reply = critic_result.reply
	if critic_result.changed:
		planner_result.steps.append(
			PlannerStep(
				name="critic",
				detail=f"Applied verifier repairs: {', '.join(critic_result.issues)}",
			)
		)
	llm_used = enhanced_reply is not None
	response_source = "agent"
	if rag_context:
		response_source = "agent_rag_llm" if llm_used else "agent_rag"
	response_time_ms = int((perf_counter() - start_time) * 1000)
	logger.info(
		"Chat response assembled source=%s llm_used=%s critic_changed=%s enhanced_reply_chars=%s final_reply_chars=%s",
		response_source,
		llm_used,
		critic_result.changed,
		len((enhanced_reply or "").strip()),
		len(final_reply.strip()),
	)
	logger.info(
		"RAG telemetry retrieved_count=%s retrieval_ms=%s auto_filters_used=%s fallback_without_filters=%s",
		rag_metrics.get("retrieved_count", 0),
		rag_metrics.get("retrieval_ms", 0),
		rag_metrics.get("auto_filters_used", False),
		rag_metrics.get("fallback_without_filters", False),
	)

	await append_message(
		payload.user_id,
		"assistant",
		f"[{intent}] {final_reply}",
		metadata={
			"suggested_next_step": next_step,
			"rag_citations": rag_citations,
			"rag_metrics": rag_metrics,
			"response_source": response_source,
			"llm_used": llm_used,
			"response_time_ms": response_time_ms,
			"plan_id": planner_result.plan_id,
			"plan_variant": planner_result.plan_variant,
			"plan_variant_reason": planner_result.plan_variant_reason,
			"planner_duration_ms": planner_result.planner_duration_ms,
			"outcome_scores": planner_result.outcome_scores,
			"critic_changed": critic_result.changed,
			"critic_issues": critic_result.issues,
			"planner_steps": _serialize_planner_steps(planner_result.steps),
		},
	)
	# Update profile after the turn so future requests can reuse extracted skills, interests, and role hints.
	if payload.context_owner_type == "self":
		await update_user_profile(
			user_id=payload.user_id,
			message=payload.message,
			context=resolved_context,
			intent=intent,
			intent_confidence=confidence,
		)
		if payload.psychometric_dimensions:
			await save_user_psychometric_profile(
				payload.user_id,
				PsychometricRequest(dimensions=payload.psychometric_dimensions),
			)
	return ChatResponse(
		reply=final_reply,
		suggested_next_step=next_step,
		rag_context=rag_context,
		rag_citations=rag_citations,
		response_source=response_source,
		llm_used=llm_used,
		response_time_ms=response_time_ms,
		plan_id=planner_result.plan_id,
		plan_variant=planner_result.plan_variant,
		plan_variant_reason=planner_result.plan_variant_reason,
		planner_duration_ms=planner_result.planner_duration_ms,
		outcome_scores=planner_result.outcome_scores,
		planner_steps=_serialize_planner_steps(planner_result.steps),
		critic_changed=critic_result.changed,
		critic_issues=critic_result.issues,
	)


@router.post("/message/me", response_model=ChatResponse)
async def send_message_me(
	payload: ChatMeRequest,
	current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
	"""Process an authenticated chat message using the user identity from JWT state."""
	start_time = perf_counter()
	base_context = dict(payload.context or {})
	if payload.skills:
		base_context["skills"] = payload.skills
	if payload.interests:
		base_context["interests"] = payload.interests
	if payload.education_level:
		base_context["education_level"] = payload.education_level

	# The authenticated variant derives identity from JWT and never trusts a client-supplied user_id.
	await append_message(current_user.id, "user", payload.message)
	profile = await get_user_profile(current_user.id)
	resolved_context = merge_context_with_profile(base_context, profile)

	planner_result = await plan_agent_response(
		payload.message,
		resolved_context,
		user_id=current_user.id,
	)
	intent = planner_result.intent
	reply = planner_result.reply
	next_step = planner_result.next_step
	confidence = planner_result.confidence
	keyword_matches = planner_result.keyword_matches
	rag_context, rag_citations, rag_metrics = get_rag_payload_with_metrics(
		payload.message,
		intent=intent,
		target_role=str(resolved_context.get("target_role") or "").strip() or None,
		skill_gaps=planner_result.skill_gaps,
	)
	base_reply = reply
	augmented_reply = base_reply
	if rag_context:
		augmented_reply = f"{base_reply}\n\nRelevant references:\n{rag_context}"
	profile_summary = summarize_profile(profile)
	enhanced_reply = generate_llm_reply(
		message=payload.message,
		intent=intent,
		base_reply=base_reply,
		next_step=next_step,
		rag_context=rag_context,
		intent_confidence=confidence,
		keyword_matches=keyword_matches,
		user_profile_summary=profile_summary,
		skill_gaps=planner_result.skill_gaps if planner_result.skill_gaps else None,
	)
	final_reply = enhanced_reply or augmented_reply
	final_reply = limit_sentences(final_reply, settings.chat_reply_max_sentences)
	critic_result = verify_and_repair_reply(
		reply=final_reply,
		intent=intent,
		next_step=next_step,
		context=resolved_context,
	)
	final_reply = critic_result.reply
	if critic_result.changed:
		planner_result.steps.append(
			PlannerStep(
				name="critic",
				detail=f"Applied verifier repairs: {', '.join(critic_result.issues)}",
			)
		)
	llm_used = enhanced_reply is not None
	response_source = "agent"
	if rag_context:
		response_source = "agent_rag_llm" if llm_used else "agent_rag"
	response_time_ms = int((perf_counter() - start_time) * 1000)
	logger.info(
		"Chat response assembled source=%s llm_used=%s critic_changed=%s enhanced_reply_chars=%s final_reply_chars=%s",
		response_source,
		llm_used,
		critic_result.changed,
		len((enhanced_reply or "").strip()),
		len(final_reply.strip()),
	)
	logger.info(
		"RAG telemetry retrieved_count=%s retrieval_ms=%s auto_filters_used=%s fallback_without_filters=%s",
		rag_metrics.get("retrieved_count", 0),
		rag_metrics.get("retrieval_ms", 0),
		rag_metrics.get("auto_filters_used", False),
		rag_metrics.get("fallback_without_filters", False),
	)

	await append_message(
		current_user.id,
		"assistant",
		f"[{intent}] {final_reply}",
		metadata={
			"suggested_next_step": next_step,
			"rag_citations": rag_citations,
			"rag_metrics": rag_metrics,
			"response_source": response_source,
			"llm_used": llm_used,
			"response_time_ms": response_time_ms,
			"plan_id": planner_result.plan_id,
			"plan_variant": planner_result.plan_variant,
			"plan_variant_reason": planner_result.plan_variant_reason,
			"planner_duration_ms": planner_result.planner_duration_ms,
			"outcome_scores": planner_result.outcome_scores,
			"critic_changed": critic_result.changed,
			"critic_issues": critic_result.issues,
			"planner_steps": _serialize_planner_steps(planner_result.steps),
		},
	)
	if payload.context_owner_type == "self":
		await update_user_profile(
			user_id=current_user.id,
			message=payload.message,
			context=resolved_context,
			intent=intent,
			intent_confidence=confidence,
		)
		if payload.psychometric_dimensions:
			await save_user_psychometric_profile(
				current_user.id,
				PsychometricRequest(dimensions=payload.psychometric_dimensions),
			)
	return ChatResponse(
		reply=final_reply,
		suggested_next_step=next_step,
		rag_context=rag_context,
		rag_citations=rag_citations,
		response_source=response_source,
		llm_used=llm_used,
		response_time_ms=response_time_ms,
		plan_id=planner_result.plan_id,
		plan_variant=planner_result.plan_variant,
		plan_variant_reason=planner_result.plan_variant_reason,
		planner_duration_ms=planner_result.planner_duration_ms,
		outcome_scores=planner_result.outcome_scores,
		planner_steps=_serialize_planner_steps(planner_result.steps),
		critic_changed=critic_result.changed,
		critic_issues=critic_result.issues,
	)

