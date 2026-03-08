from app.agents.base_agent import BaseAgent


class CareerAssessmentAgent(BaseAgent):
	name = "career_assessment"

	def respond(self, message: str) -> str:
		return (
			"Your query suggests you are exploring suitable career options. "
			"I recommend mapping your interests, strengths, and preferred work style "
			"to identify high-fit roles."
		)

	def suggested_next_step(self) -> str:
		return "Complete the career interest and aptitude assessment"
