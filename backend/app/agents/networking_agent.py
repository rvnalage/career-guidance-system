"""Agent for networking strategy, outreach, and referral-oriented guidance."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from typing import Any

from app.agents.base_agent import BaseAgent


class NetworkingAgent(BaseAgent):
	name = "networking"

	def respond(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Return a concise networking plan anchored to role and company targets."""
		role = self._extract_target_role(message, context) or "your target role"
		target_companies = self._extract_target_companies(context)
		companies_text = ", ".join(target_companies[:5]) if target_companies else "your top target companies"

		return (
			f"Networking strategy for {role}:\n"
			f"1. Positioning: tune headline/about section for recruiter search on {companies_text}.\n"
			"2. Warm outreach: connect with alumni, hiring managers, and practitioners with personalized intent.\n"
			"3. Value-first follow-up: share project insights or role-relevant questions before asking referral.\n"
			"4. Pipeline tracking: monitor connection-to-conversation and conversation-to-referral conversion weekly."
		)

	def suggested_next_step(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Ask for company targets or profile details needed to draft tailored outreach."""
		companies = self._extract_target_companies(context)
		if companies:
			return f"I can draft 3 outreach messages for {companies[0]} and similar companies"
		return "Share 3 target companies and your LinkedIn headline for personalized outreach drafts"

