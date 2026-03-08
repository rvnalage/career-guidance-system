from pydantic import BaseModel


class RecommendationRequest(BaseModel):
	user_id: str = ""
	interests: list[str]
	skills: list[str]
	education_level: str


class CareerRecommendation(BaseModel):
	role: str
	confidence: float
	reason: str


class RecommendationResponse(BaseModel):
	recommendations: list[CareerRecommendation]


class RecommendationHistoryItem(BaseModel):
	user_id: str
	recommendations: list[CareerRecommendation]
	generated_at: str


class RecommendationHistoryResponse(BaseModel):
	history: list[RecommendationHistoryItem]


class RecommendationFeedbackRequest(BaseModel):
	role: str
	helpful: bool
	rating: int = 3
	feedback_tags: list[str] = []


class RecommendationExplainRequest(BaseModel):
	interests: list[str]
	skills: list[str]
	education_level: str


class FeatureContribution(BaseModel):
	feature: str
	value: float


class RecommendationExplanation(BaseModel):
	role: str
	confidence: float
	contributions: list[FeatureContribution]
	label: str


class RecommendationExplainResponse(BaseModel):
	explanations: list[RecommendationExplanation]
