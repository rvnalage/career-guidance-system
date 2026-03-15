"""Agent routing helpers that bridge intent detection and concrete agent execution."""

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


AGENT_REGISTRY = {
	"career_assessment": CareerAssessmentAgent(),
	"interview_prep": InterviewPrepAgent(),
	"job_matching": JobMatchingAgent(),
	"learning_path": LearningPathAgent(),
	"networking": NetworkingAgent(),
	"recommendation": RecommendationAgent(),
	"feedback": FeedbackAgent(),
}


def get_agent_response(message: str, context: dict[str, Any] | None = None) -> tuple[str, str, str]:
	"""Return agent output using confidence-gated intent routing without exposing score details."""
	intent, confidence, _ = detect_intent_with_confidence(message)
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
	"""Return agent output together with routing confidence and matched keywords."""
	intent, confidence, matches = detect_intent_with_confidence(message)
	if confidence < settings.intent_min_confidence:
		intent = "career_assessment"
	agent = AGENT_REGISTRY.get(intent, AGENT_REGISTRY["career_assessment"])
	reply = agent.respond(message, context)
	next_step = agent.suggested_next_step(message, context)
	return intent, reply, next_step, confidence, matches
