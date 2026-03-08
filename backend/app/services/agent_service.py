from app.agents.career_assessment_agent import CareerAssessmentAgent
from app.agents.interview_prep_agent import InterviewPrepAgent
from app.agents.job_matching_agent import JobMatchingAgent
from app.agents.learning_path_agent import LearningPathAgent
from app.agents.networking_agent import NetworkingAgent
from app.nlp.intent_recognizer import detect_intent


AGENT_REGISTRY = {
	"career_assessment": CareerAssessmentAgent(),
	"interview_prep": InterviewPrepAgent(),
	"job_matching": JobMatchingAgent(),
	"learning_path": LearningPathAgent(),
	"networking": NetworkingAgent(),
}


def get_agent_response(message: str) -> tuple[str, str, str]:
	intent = detect_intent(message)
	agent = AGENT_REGISTRY.get(intent, AGENT_REGISTRY["career_assessment"])
	reply = agent.respond(message)
	next_step = agent.suggested_next_step()
	return intent, reply, next_step
