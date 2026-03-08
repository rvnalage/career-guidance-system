from app.agents.base_agent import BaseAgent


class InterviewPrepAgent(BaseAgent):
	name = "interview_prep"

	def respond(self, message: str) -> str:
		return (
			"I can help you prepare for interviews with role-specific questions, "
			"project storytelling guidance, and a revision checklist."
		)

	def suggested_next_step(self) -> str:
		return "Choose a target role to start an interview preparation track"
