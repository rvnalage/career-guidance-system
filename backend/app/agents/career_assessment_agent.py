"""Agent responsible for broad career exploration and role-fit clarification."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from typing import Any

from app.agents.base_agent import BaseAgent


class CareerAssessmentAgent(BaseAgent):
	name = "career_assessment"

	def respond(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Return a structured decision-making plan when the user needs general career direction."""
		role = self._extract_target_role(message, context)
		timeline_weeks = self._extract_timeline_weeks(message, context) or 8
		skills = self._extract_skill_keywords(message, context)
		skills_text = ", ".join(skills[:5]) if skills else "your current skill set"
		role_text = role or "2-3 target roles"

		return (
			f"Let us make your career decision systematic over the next {timeline_weeks} weeks.\n"
			f"Focus role: {role_text}.\n"
			f"Observed strengths to leverage: {skills_text}.\n\n"
			"Plan:\n"
			"1. Self-profile: define interests, strengths, and non-negotiables (work type, domain, location).\n"
			"2. Role-fit matrix: compare target roles against required skills, growth, and effort-to-transition.\n"
			"3. Evidence loop: run 1 mini-project + 2 informational interviews to validate role fit.\n"
			"4. Decision checkpoint: lock one primary path and one backup path."
		)

	def suggested_next_step(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Suggest the next assessment step needed to narrow broad career options."""
		role = self._extract_target_role(message, context)
		if role:
			return f"Complete a role-fit scorecard for {role} (skills, interest, market demand)"
		return "Complete a quick self-assessment: list your top 3 strengths, 3 interests, and 2 target roles"

