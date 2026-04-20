"""Agent for fit-gap analysis between a student's profile and target roles."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from typing import Any

from app.agents.base_agent import BaseAgent


class JobMatchingAgent(BaseAgent):
	name = "job_matching"

	def respond(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Return a readiness and application-strategy summary for job matching queries."""
		role = self._extract_target_role(message, context) or "target role"
		skills = self._extract_skill_keywords(message, context)
		timeline_weeks = self._extract_timeline_weeks(message, context)

		if len(skills) >= 4:
			readiness = "medium-high"
		elif len(skills) >= 2:
			readiness = "medium"
		else:
			readiness = "early"

		timeline_text = f"in {timeline_weeks} weeks" if timeline_weeks else "with your current timeline"
		skills_text = ", ".join(skills[:6]) if skills else "not enough profile signals yet"

		return (
			f"Profile-to-job matching summary for {role} ({timeline_text}):\n"
			f"- Current readiness: {readiness}.\n"
			f"- Detected strengths: {skills_text}.\n"
			"- Gap analysis: identify missing must-have skills and interview depth for shortlisted roles.\n"
			"- Application strategy: apply in 3 buckets (stretch, realistic, safe) and track response rates weekly."
		)

	def suggested_next_step(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Ask for concrete job evidence so the fit-gap analysis can become role-specific."""
		role = self._extract_target_role(message, context) or "your target role"
		return f"Share your resume plus 5 job links for {role} to produce exact fit-gap recommendations"

