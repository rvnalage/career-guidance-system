"""Pydantic schemas for psychometric scoring requests and responses."""

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
