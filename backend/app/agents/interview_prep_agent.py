"""Agent for interview preparation guidance and mock-planning responses."""

from typing import Any

from app.agents.base_agent import BaseAgent


class InterviewPrepAgent(BaseAgent):
	name = "interview_prep"

	def respond(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Return a short interview-preparation sprint plan tailored to role and timeline signals."""
		role = self._extract_target_role(message, context) or "your target role"
		timeline_weeks = self._extract_timeline_weeks(message, context) or 4
		skills = self._extract_skill_keywords(message, context)
		skills_text = ", ".join(skills[:4]) if skills else "core fundamentals"

		return (
			f"Interview prep plan for {role} ({timeline_weeks}-week sprint):\n"
			"1. Resume-to-story mapping: convert each project into problem, approach, impact, and trade-offs.\n"
			f"2. Technical drill: prioritize {skills_text} and role-specific interview patterns.\n"
			"3. Behavioral prep: STAR answers for ownership, conflict, failure, and leadership.\n"
			"4. Mock cycle: 2 timed mocks per week, then patch weak areas using a revision tracker."
		)

	def suggested_next_step(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Suggest the most useful artifact needed to generate focused interview practice."""
		role = self._extract_target_role(message, context)
		if role:
			return f"Share your latest resume to build a 10-question mock set for {role}"
		return "Choose your target role and interview date to generate a focused prep calendar"
