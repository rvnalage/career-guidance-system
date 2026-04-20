"""Agent for collecting structured recommendation feedback from the user."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from typing import Any

from app.agents.base_agent import BaseAgent


class FeedbackAgent(BaseAgent):
	name = "feedback"

	def respond(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Explain the feedback format that can improve future recommendation ranking."""
		role = self._extract_target_role(message, context) or "the recommended role"
		return (
			f"I can help you submit structured feedback for {role} recommendations.\n"
			"Useful feedback includes: helpful/not helpful, rating (1-5), and tags like skills/interests/education.\n"
			"This feedback is used to personalize future recommendation ranking."
		)

	def suggested_next_step(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Tell the user which structured fields are required to record recommendation feedback."""
		return "Provide role, helpful flag, rating, and feedback tags to record recommendation feedback"

