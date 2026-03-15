"""Agent for recommendation-oriented prompts before the scoring engine is invoked."""

from typing import Any

from app.agents.base_agent import BaseAgent


class RecommendationAgent(BaseAgent):
	name = "recommendation"

	def respond(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Explain what profile signals drive recommendation quality and explainability."""
		role = self._extract_target_role(message, context) or "your target role cluster"
		skills = self._extract_skill_keywords(message, context)
		skill_text = ", ".join(skills[:5]) if skills else "not enough skill details yet"
		timeline_weeks = self._extract_timeline_weeks(message, context)
		timeline_text = f" over {timeline_weeks} weeks" if timeline_weeks else ""

		return (
			f"I can generate personalized career recommendations{timeline_text} for {role}.\n"
			f"Current extracted skills: {skill_text}.\n"
			"To maximize recommendation quality, I use your skills, interests, education fit, and prior feedback.\n"
			"I can also explain why each role is ranked and what actions improve confidence."
		)

	def suggested_next_step(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Request the minimum structured inputs needed by the recommendation engine."""
		return "Share 5 skills, 3 interests, and education level to generate top role recommendations"
