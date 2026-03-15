"""Chat API routes for anonymous and authenticated career guidance conversations.

This module coordinates the full chat pipeline: history persistence, profile-memory
merge, intent routing, RAG grounding, optional LLM refinement, and profile updates.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.database.models import User
from app.dependencies import get_current_user
from app.schemas.chat import ChatMeRequest, ChatRequest, ChatResponse
from app.services.agent_service import get_agent_response_with_confidence
from app.services.history_service import append_message
from app.services.llm_service import generate_llm_reply
from app.services.profile_service import (
	get_user_profile,
	merge_context_with_profile,
	summarize_profile,
	update_user_profile,
)
from app.services.rag_service import build_rag_context, get_rag_citations

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_message(payload: ChatRequest) -> ChatResponse:
	"""Process an anonymous chat message and return a grounded assistant response."""
	# Persist the raw user turn first so downstream enrichment failures do not lose the request.
	await append_message(payload.user_id, "user", payload.message)
	profile = await get_user_profile(payload.user_id)
	# Merge explicit request context with long-lived profile memory before intent routing.
	resolved_context = merge_context_with_profile(payload.context, profile)

	intent, reply, next_step, confidence, keyword_matches = get_agent_response_with_confidence(
		payload.message,
		resolved_context,
	)
	# RAG is computed independently from the agent so the response can stay grounded even when the LLM is disabled.
	rag_context = build_rag_context(payload.message)
	rag_citations = get_rag_citations(payload.message)
	augmented_reply = reply
	if rag_context:
		augmented_reply = f"{reply}\n\nRelevant references:\n{rag_context}"
	profile_summary = summarize_profile(profile)
	# The LLM only refines the agent response; if it is unavailable, the deterministic agent reply is returned as-is.
	enhanced_reply = generate_llm_reply(
		message=payload.message,
		intent=intent,
		base_reply=augmented_reply,
		next_step=next_step,
		rag_context=rag_context,
		intent_confidence=confidence,
		keyword_matches=keyword_matches,
		user_profile_summary=profile_summary,
	)
	final_reply = enhanced_reply or augmented_reply

	await append_message(payload.user_id, "assistant", f"[{intent}] {final_reply}")
	# Update profile after the turn so future requests can reuse extracted skills, interests, and role hints.
	await update_user_profile(
		user_id=payload.user_id,
		message=payload.message,
		context=resolved_context,
		intent=intent,
		intent_confidence=confidence,
	)
	return ChatResponse(
		reply=final_reply,
		suggested_next_step=next_step,
		rag_context=rag_context,
		rag_citations=rag_citations,
	)


@router.post("/message/me", response_model=ChatResponse)
async def send_message_me(
	payload: ChatMeRequest,
	current_user: Annotated[User, Depends(get_current_user)],
) -> ChatResponse:
	"""Process an authenticated chat message using the user identity from JWT state."""
	# The authenticated variant derives identity from JWT and never trusts a client-supplied user_id.
	await append_message(current_user.id, "user", payload.message)
	profile = await get_user_profile(current_user.id)
	resolved_context = merge_context_with_profile(payload.context, profile)

	intent, reply, next_step, confidence, keyword_matches = get_agent_response_with_confidence(
		payload.message,
		resolved_context,
	)
	rag_context = build_rag_context(payload.message)
	rag_citations = get_rag_citations(payload.message)
	augmented_reply = reply
	if rag_context:
		augmented_reply = f"{reply}\n\nRelevant references:\n{rag_context}"
	profile_summary = summarize_profile(profile)
	enhanced_reply = generate_llm_reply(
		message=payload.message,
		intent=intent,
		base_reply=augmented_reply,
		next_step=next_step,
		rag_context=rag_context,
		intent_confidence=confidence,
		keyword_matches=keyword_matches,
		user_profile_summary=profile_summary,
	)
	final_reply = enhanced_reply or augmented_reply

	await append_message(current_user.id, "assistant", f"[{intent}] {final_reply}")
	await update_user_profile(
		user_id=current_user.id,
		message=payload.message,
		context=resolved_context,
		intent=intent,
		intent_confidence=confidence,
	)
	return ChatResponse(
		reply=final_reply,
		suggested_next_step=next_step,
		rag_context=rag_context,
		rag_citations=rag_citations,
	)
