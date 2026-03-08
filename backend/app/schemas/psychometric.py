from pydantic import BaseModel


class PsychometricRequest(BaseModel):
	# Values should generally be in range 1-5.
	dimensions: dict[str, int]


class PsychometricResponse(BaseModel):
	normalized_scores: dict[str, float]
	top_traits: list[str]
	recommended_domains: list[str]
