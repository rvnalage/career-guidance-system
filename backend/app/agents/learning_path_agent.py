from app.agents.base_agent import BaseAgent


class LearningPathAgent(BaseAgent):
	name = "learning_path"

	def respond(self, message: str) -> str:
		return (
			"You appear to be asking about skill development. "
			"I can create a phased roadmap with foundation topics, guided projects, "
			"and portfolio milestones aligned to your target role."
		)

	def suggested_next_step(self) -> str:
		return "Share your current skills to generate a personalized 8-week plan"
