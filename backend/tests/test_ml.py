from app.schemas.recommendation import RecommendationRequest
from app.services.recommendation_service import generate_career_recommendations


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
