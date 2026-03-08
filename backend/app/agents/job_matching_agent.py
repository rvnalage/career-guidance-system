from app.agents.base_agent import BaseAgent


class JobMatchingAgent(BaseAgent):
	name = "job_matching"

	def respond(self, message: str) -> str:
		return (
			"I can match your profile with role requirements and highlight skill gaps. "
			"This helps prioritize opportunities where your current profile has the best fit."
		)

	def suggested_next_step(self) -> str:
		return "Provide your top 5 skills and preferred domains for role matching"
