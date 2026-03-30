from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
	user_id: str
	message: str
	context: dict | None = None
	context_owner_type: Literal["self", "on_behalf"] = "self"
	skills: list[str] = Field(default_factory=list)
	interests: list[str] = Field(default_factory=list)
	education_level: str | None = None
	psychometric_dimensions: dict[str, int] | None = None


class ChatMeRequest(BaseModel):
	message: str
	context: dict | None = None
	context_owner_type: Literal["self", "on_behalf"] = "self"
	skills: list[str] = Field(default_factory=list)
	interests: list[str] = Field(default_factory=list)
	education_level: str | None = None
	psychometric_dimensions: dict[str, int] | None = None


class ChatResponse(BaseModel):
	reply: str
	suggested_next_step: str
	rag_context: str = ""
	rag_citations: list[dict[str, Any]] = Field(default_factory=list)
	response_source: Literal["agent", "agent_rag", "agent_rag_llm"] = "agent"
	llm_used: bool = False
	response_time_ms: int = 0
