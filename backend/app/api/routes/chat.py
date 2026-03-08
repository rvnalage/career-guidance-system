from typing import Annotated

from fastapi import APIRouter, Depends

from app.database.models import User
from app.dependencies import get_current_user
from app.schemas.chat import ChatMeRequest, ChatRequest, ChatResponse
from app.services.agent_service import get_agent_response
from app.services.history_service import append_message
from app.services.llm_service import generate_llm_reply
from app.services.rag_service import build_rag_context, get_rag_citations

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_message(payload: ChatRequest) -> ChatResponse:
	await append_message(payload.user_id, "user", payload.message)

	intent, reply, next_step = get_agent_response(payload.message)
	rag_context = build_rag_context(payload.message)
	rag_citations = get_rag_citations(payload.message)
	augmented_reply = reply
	if rag_context:
		augmented_reply = f"{reply}\n\nRelevant references:\n{rag_context}"
	enhanced_reply = generate_llm_reply(
		message=payload.message,
		intent=intent,
		base_reply=augmented_reply,
		next_step=next_step,
		rag_context=rag_context,
	)
	final_reply = enhanced_reply or augmented_reply

	await append_message(payload.user_id, "assistant", f"[{intent}] {final_reply}")
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
	await append_message(current_user.id, "user", payload.message)

	intent, reply, next_step = get_agent_response(payload.message)
	rag_context = build_rag_context(payload.message)
	rag_citations = get_rag_citations(payload.message)
	augmented_reply = reply
	if rag_context:
		augmented_reply = f"{reply}\n\nRelevant references:\n{rag_context}"
	enhanced_reply = generate_llm_reply(
		message=payload.message,
		intent=intent,
		base_reply=augmented_reply,
		next_step=next_step,
		rag_context=rag_context,
	)
	final_reply = enhanced_reply or augmented_reply

	await append_message(current_user.id, "assistant", f"[{intent}] {final_reply}")
	return ChatResponse(
		reply=final_reply,
		suggested_next_step=next_step,
		rag_context=rag_context,
		rag_citations=rag_citations,
	)
