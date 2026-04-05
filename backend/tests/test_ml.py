import asyncio

from app.schemas.recommendation import RecommendationRequest
from app.services.recommendation_service import generate_career_recommendations, get_personalization_profile


def test_generate_career_recommendations_returns_top_three():
	payload = RecommendationRequest(
		user_id="student-1",
		interests=["AI", "Data Science", "Software"],
		skills=["Python", "Machine Learning", "SQL", "Pandas"],
		education_level="master",
	)

	results = generate_career_recommendations(payload)

	assert len(results) == 3
	assert results[0].role == "Machine Learning Engineer"
	assert 0.0 <= results[0].confidence <= 1.0


def test_recommendation_confidence_sorted_descending():
	payload = RecommendationRequest(
		user_id="student-2",
		interests=["Design", "Creativity"],
		skills=["Figma", "Wireframing", "Prototyping"],
		education_level="bachelor",
	)

	results = generate_career_recommendations(payload)
	confidences = [result.confidence for result in results]

	assert confidences == sorted(confidences, reverse=True)
	assert results[0].role == "UI/UX Designer"


def test_get_personalization_profile_blends_model_scores(monkeypatch):
	from app.services import recommendation_service

	class _Cursor:
		def sort(self, *_args, **_kwargs):
			return self

		async def to_list(self, length=500):  # noqa: ARG002
			return [
				{"role": "Data Analyst", "helpful": True, "rating": 5, "feedback_tags": ["skills"]},
			]

	class _Collection:
		def find(self, *_args, **_kwargs):
			return _Cursor()

	async def _run():
		monkeypatch.setattr(recommendation_service, "get_feedback_collection", lambda: _Collection())
		monkeypatch.setattr(
			recommendation_service,
			"score_role_preferences",
			lambda *_args, **_kwargs: {"Data Analyst": 1.0},
		)
		profile = await get_personalization_profile("user-1")
		assert "Data Analyst" in profile["role_bonus"]
		assert profile["role_bonus"]["Data Analyst"] > 0

	asyncio.run(_run())
