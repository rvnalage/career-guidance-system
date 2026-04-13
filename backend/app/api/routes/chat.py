"""Chat API routes for anonymous and authenticated career guidance conversations.

This module coordinates the full chat pipeline: history persistence, profile-memory
merge, intent routing, RAG grounding, optional LLM refinement, and profile updates.
"""

from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends

from app.database.models import User
from app.dependencies import get_current_user
from app.schemas.chat import ChatMeRequest, ChatRequest, ChatResponse
from app.services.agent_service import get_agent_response_with_confidence
from app.services.history_service import append_message
from app.services.llm_service import generate_llm_reply, limit_sentences
from app.services.profile_service import (
	get_user_profile,
	merge_context_with_profile,
	summarize_profile,
	update_user_profile,
)
from app.services.rag_service import build_rag_context, get_rag_citations
from app.services.psychometric_service import save_user_psychometric_profile
from app.schemas.psychometric import PsychometricRequest
from app.config import settings
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


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

	intent, reply, next_step, confidence, keyword_matches = get_agent_response_with_confidence(
		payload.message,
		resolved_context,
	)
	# RAG is computed independently from the agent so the response can stay grounded even when the LLM is disabled.
	rag_context = build_rag_context(payload.message)
	rag_citations = get_rag_citations(payload.message)
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
	)
	final_reply = enhanced_reply or augmented_reply
	final_reply = limit_sentences(final_reply, settings.chat_reply_max_sentences)
	llm_used = enhanced_reply is not None
	response_source = "agent"
	if rag_context:
		response_source = "agent_rag_llm" if llm_used else "agent_rag"
	response_time_ms = int((perf_counter() - start_time) * 1000)
	logger.info(
		"Chat response assembled source=%s llm_used=%s enhanced_reply_chars=%s final_reply_chars=%s",
		response_source,
		llm_used,
		len((enhanced_reply or "").strip()),
		len(final_reply.strip()),
	)

	await append_message(
		payload.user_id,
		"assistant",
		f"[{intent}] {final_reply}",
		metadata={
			"suggested_next_step": next_step,
			"rag_citations": rag_citations,
			"response_source": response_source,
			"llm_used": llm_used,
			"response_time_ms": response_time_ms,
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

	intent, reply, next_step, confidence, keyword_matches = get_agent_response_with_confidence(
		payload.message,
		resolved_context,
	)
	rag_context = build_rag_context(payload.message)
	rag_citations = get_rag_citations(payload.message)
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
	)
	final_reply = enhanced_reply or augmented_reply
	final_reply = limit_sentences(final_reply, settings.chat_reply_max_sentences)
	llm_used = enhanced_reply is not None
	response_source = "agent"
	if rag_context:
		response_source = "agent_rag_llm" if llm_used else "agent_rag"
	response_time_ms = int((perf_counter() - start_time) * 1000)
	logger.info(
		"Chat response assembled source=%s llm_used=%s enhanced_reply_chars=%s final_reply_chars=%s",
		response_source,
		llm_used,
		len((enhanced_reply or "").strip()),
		len(final_reply.strip()),
	)

	await append_message(
		current_user.id,
		"assistant",
		f"[{intent}] {final_reply}",
		metadata={
			"suggested_next_step": next_step,
			"rag_citations": rag_citations,
			"response_source": response_source,
			"llm_used": llm_used,
			"response_time_ms": response_time_ms,
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
	)
