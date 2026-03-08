from app.services.agent_service import get_agent_response


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
