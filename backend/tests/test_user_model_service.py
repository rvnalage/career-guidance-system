from app.services.user_model_service import build_role_feature_vector


def test_build_role_feature_vector_with_matching_feedback():
	feedback_items = [
		{"role": "Data Analyst", "helpful": True, "rating": 5, "feedback_tags": ["skills", "interests"]},
		{"role": "Data Analyst", "helpful": False, "rating": 2, "feedback_tags": ["education"]},
		{"role": "Backend Developer", "helpful": True, "rating": 4, "feedback_tags": ["skills"]},
	]
	features = build_role_feature_vector(feedback_items, "Data Analyst")

	assert features["role_feedback_count"] == 2.0
	assert 0.0 <= features["role_helpful_rate"] <= 1.0
	assert 0.0 <= features["role_avg_rating_norm"] <= 1.0
	assert features["tag_skills_rate"] == 0.5
	assert features["tag_interests_rate"] == 0.5
	assert features["tag_education_rate"] == 0.5


def test_build_role_feature_vector_no_matching_feedback():
	features = build_role_feature_vector([], "Machine Learning Engineer")
	assert features["role_feedback_count"] == 0.0
	assert features["role_feedback_ratio"] == 0.0
	assert features["role_avg_rating_norm"] == 0.5
