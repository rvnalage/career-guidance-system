from app.agents.base_agent import BaseAgent


class NetworkingAgent(BaseAgent):
	name = "networking"

	def respond(self, message: str) -> str:
		return (
			"I can guide networking strategy including resume positioning, LinkedIn optimization, "
			"and personalized outreach messages for mentors and recruiters."
		)

	def suggested_next_step(self) -> str:
		return "Share your target companies to draft outreach and networking plan"
