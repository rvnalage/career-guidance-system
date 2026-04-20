"""Pydantic schemas for psychometric scoring requests and responses."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from pydantic import BaseModel


class PsychometricRequest(BaseModel):
	"""Input dimensions used to compute normalized psychometric scores."""
	# Values should generally be in range 1-5.
	dimensions: dict[str, int]


class PsychometricResponse(BaseModel):
	"""Normalized psychometric profile returned by scoring endpoints."""
	normalized_scores: dict[str, float]
	top_traits: list[str]
	recommended_domains: list[str]

