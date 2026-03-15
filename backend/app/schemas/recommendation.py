"""Pydantic schemas for recommendation requests, outputs, feedback, and explanations."""

from pydantic import BaseModel


class RecommendationRequest(BaseModel):
	"""Input payload required to generate recommendation scores."""
	user_id: str = ""
	interests: list[str]
	skills: list[str]
	education_level: str


class CareerRecommendation(BaseModel):
	"""Single ranked career recommendation with confidence and rationale."""
	role: str
	confidence: float
	reason: str


class RecommendationResponse(BaseModel):
	"""Envelope for recommendation lists returned by the API."""
	recommendations: list[CareerRecommendation]


class RecommendationHistoryItem(BaseModel):
	"""Stored recommendation snapshot entry for history endpoints."""
	user_id: str
	recommendations: list[CareerRecommendation]
	generated_at: str


class RecommendationHistoryResponse(BaseModel):
	"""Envelope for recommendation history responses."""
	history: list[RecommendationHistoryItem]


class RecommendationFeedbackRequest(BaseModel):
	"""Structured recommendation feedback payload used for personalization."""
	role: str
	helpful: bool
	rating: int = 3
	feedback_tags: list[str] = []


class RecommendationExplainRequest(BaseModel):
	"""Input payload for explanation generation over ranked career options."""
	interests: list[str]
	skills: list[str]
	education_level: str


class FeatureContribution(BaseModel):
	"""Single feature contribution emitted by the active explainer."""
	feature: str
	value: float


class RecommendationExplanation(BaseModel):
	"""Recommendation result enriched with feature-level explanation output."""
	role: str
	confidence: float
	contributions: list[FeatureContribution]
	label: str


class RecommendationExplainResponse(BaseModel):
	"""Envelope for explanation results returned by the recommendation API."""
	explanations: list[RecommendationExplanation]
