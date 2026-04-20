# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.

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
	plan_id: str | None = None
	plan_variant: str | None = None
	plan_variant_reason: str | None = None
	planner_duration_ms: int = 0
	outcome_scores: list[dict[str, Any]] = Field(default_factory=list)
	planner_steps: list[dict[str, Any]] = Field(default_factory=list)
	critic_changed: bool = False
	critic_issues: list[str] = Field(default_factory=list)


class ChatOutcomeRequest(BaseModel):
	plan_id: str | None = None
	intent: str | None = None
	helpful: bool = False
	accepted_next_step: bool = False
	clicked_suggestion: bool = False
	rating: int | None = None
	source: Literal["chat", "dashboard", "recommendations", "jobs"] = "chat"


class ChatOutcomeResponse(BaseModel):
	user_id: str
	plan_id: str | None = None
	intent: str
	success_score: int
	message: str = "Outcome recorded"


class NetworkingMetricsRequest(BaseModel):
	user_id: str | None = None
	weekly_availability_hours: int | None = Field(default=None, ge=1, le=80)
	response_rate_percent: int | None = Field(default=None, ge=0, le=100)


class NetworkingMetricsResponse(BaseModel):
	user_id: str
	avg_weekly_availability_hours: float | None = None
	avg_response_rate_percent: float | None = None
	last_weekly_availability_hours: int | None = None
	last_response_rate_percent: int | None = None
	samples: int = 0
	message: str = "Networking metrics recorded"

