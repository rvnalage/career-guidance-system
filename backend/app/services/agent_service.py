"""Agent routing helpers that bridge intent detection and concrete agent execution."""

# Developer Onboarding Notes:
# - Layer: intent-to-agent routing service
# - Role in system: Selects specialist agent from detected intent and returns primary guidance outputs.
# - Main callers: chat route handlers and planner orchestration service.
# - Reading tip: Start from get_agent_response_with_confidence, then inspect _resolve_intent fallback flow.


from typing import Any

from app.agents.career_assessment_agent import CareerAssessmentAgent
from app.agents.interview_prep_agent import InterviewPrepAgent
from app.agents.job_matching_agent import JobMatchingAgent
from app.agents.learning_path_agent import LearningPathAgent
from app.agents.networking_agent import NetworkingAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.agents.feedback_agent import FeedbackAgent
from app.config import settings
from app.nlp.intent_recognizer import detect_intent_with_confidence
from app.services.intent_model_service import detect_intent_with_model


AGENT_REGISTRY = {
	"career_assessment": CareerAssessmentAgent(),
	"interview_prep": InterviewPrepAgent(),
	"job_matching": JobMatchingAgent(),
	"learning_path": LearningPathAgent(),
	"networking": NetworkingAgent(),
	"recommendation": RecommendationAgent(),
	"feedback": FeedbackAgent(),
}


def _resolve_intent(message: str) -> tuple[str, float, list[str]]:
	"""Resolve intent using model-first strategy with keyword fallback.

	Args:
		message: Raw user message used for intent detection.

	Returns:
		Tuple of intent label, confidence score, and matched keyword/model tags.

	Significance:
		Central routing primitive that keeps behavior stable when ML intent model is
		unavailable by falling back to deterministic keyword recognizer.
	"""
	model_prediction = detect_intent_with_model(message)
	if model_prediction is not None:
		return model_prediction.intent, model_prediction.confidence, ["intent_model"]
	return detect_intent_with_confidence(message)


def get_agent_response(message: str, context: dict[str, Any] | None = None) -> tuple[str, str, str]:
	"""Return agent response without exposing routing diagnostics.

	Significance:
		Backward-compatible simple interface used by routes/tests that only need
		intent, reply text, and next-step suggestion.

	Used by:
		Legacy chat path and agent-focused tests.
	"""
	intent, confidence, _ = _resolve_intent(message)
	if confidence < settings.intent_min_confidence:
		intent = "career_assessment"
	agent = AGENT_REGISTRY.get(intent, AGENT_REGISTRY["career_assessment"])
	reply = agent.respond(message, context)
	next_step = agent.suggested_next_step(message, context)
	return intent, reply, next_step


def get_agent_response_with_confidence(
	message: str,
	context: dict[str, Any] | None = None,
) -> tuple[str, str, str, float, list[str]]:
	"""Return agent response plus routing explainability metadata.

	Returns:
		Tuple of intent, reply, next step, confidence, and keyword/model matches.

	Significance:
		Preferred planner-facing entrypoint so downstream orchestration can adapt to
		routing certainty and preserve traceability in response telemetry.

	Used by:
		Planner service intent bootstrap flow.
	"""
	intent, confidence, matches = _resolve_intent(message)
	if confidence < settings.intent_min_confidence:
		intent = "career_assessment"
	agent = AGENT_REGISTRY.get(intent, AGENT_REGISTRY["career_assessment"])
	reply = agent.respond(message, context)
	next_step = agent.suggested_next_step(message, context)
	return intent, reply, next_step, confidence, matches

