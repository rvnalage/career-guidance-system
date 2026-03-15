from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
	user_id: str
	message: str
	context: dict | None = None


class ChatMeRequest(BaseModel):
	message: str
	context: dict | None = None


class ChatResponse(BaseModel):
	reply: str
	suggested_next_step: str
	rag_context: str = ""
	rag_citations: list[dict[str, Any]] = Field(default_factory=list)
