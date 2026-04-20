"""Agent for phased learning-roadmap and upskilling guidance."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from typing import Any

from app.agents.base_agent import BaseAgent


class LearningPathAgent(BaseAgent):
	name = "learning_path"

	def respond(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Return a staged roadmap that maps foundations, projects, and interview prep."""
		role = self._extract_target_role(message, context) or "your target role"
		timeline_weeks = self._extract_timeline_weeks(message, context) or 8
		skills = self._extract_skill_keywords(message, context)
		baseline = ", ".join(skills[:5]) if skills else "foundational concepts"

		return (
			f"Learning roadmap for {role} ({timeline_weeks} weeks):\n"
			"1. Foundation phase: strengthen theory and tools most used in the role.\n"
			f"2. Build phase: create guided mini-projects using {baseline}.\n"
			"3. Portfolio phase: publish one production-style project with measurable outcomes.\n"
			"4. Interview phase: convert project learnings into concise stories and revision notes."
		)

	def suggested_next_step(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Request baseline skill level so the roadmap can be adapted to the user's depth."""
		timeline_weeks = self._extract_timeline_weeks(message, context) or 8
		return f"Share your current skill level (beginner/intermediate/advanced) to get a week-by-week {timeline_weeks}-week plan"

