from app.services.agent_service import get_agent_response
from app.nlp.intent_recognizer import detect_intent_with_confidence


def test_agent_service_selects_networking_agent():
	intent, reply, next_step = get_agent_response("I need linkedin networking strategy")
	assert intent == "networking"
	assert "linkedin" in reply.lower() or "network" in reply.lower()
	assert "networking" in next_step.lower() or "outreach" in next_step.lower()


def test_agent_service_defaults_to_career_assessment():
	intent, reply, next_step = get_agent_response("I am confused about my future")
	assert intent == "career_assessment"
	assert "career" in reply.lower() or "role" in reply.lower()
	assert "assessment" in next_step.lower()


def test_agent_service_learning_path_uses_timeline_signal():
	intent, reply, next_step = get_agent_response("Create a learning roadmap for data science in 6 weeks")
	assert intent == "learning_path"
	assert "6 weeks" in reply.lower()
	assert "week" in next_step.lower()


def test_agent_service_job_matching_uses_context_skills():
	intent, reply, next_step = get_agent_response(
		"Need role matching",
		context={"target_role": "data engineer", "skills": ["python", "sql", "docker", "aws"]},
	)
	assert intent == "job_matching"
	assert "data engineer" in reply.lower()
	assert "readiness" in reply.lower()
	assert "job links" in next_step.lower() or "resume" in next_step.lower()


def test_agent_service_selects_recommendation_agent():
	intent, reply, next_step = get_agent_response("Please recommend best role for my profile")
	assert intent == "recommendation"
	assert "recommend" in reply.lower()
	assert "skills" in next_step.lower()


def test_agent_service_selects_feedback_agent():
	intent, reply, next_step = get_agent_response("I want to give feedback and rating")
	assert intent == "feedback"
	assert "feedback" in reply.lower()
	assert "rating" in next_step.lower()


def test_detect_intent_with_confidence_returns_matches():
	intent, confidence, matches = detect_intent_with_confidence("please recommend best role")
	assert intent == "recommendation"
	assert confidence > 0.35
	assert len(matches) >= 1


def test_low_signal_message_falls_back_to_career_assessment():
	intent, reply, _ = get_agent_response("hmm")
	assert intent == "career_assessment"
	assert "career" in reply.lower() or "role" in reply.lower()
