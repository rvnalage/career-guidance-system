from app.xai.explainer import explain_recommendation


def test_explain_recommendation_returns_expected_shape_and_label():
	feature_map = {
		"skill_match": 0.8,
		"interest_match": 0.6,
		"education_fit": 1.0,
		"personalization_bonus": 0.05,
	}
	weights = {"skill": 0.5, "interest": 0.3, "education": 0.2}

	contributions, label = explain_recommendation(feature_map, weights)
	assert len(contributions) == 4
	assert {item[0] for item in contributions} == {
		"skill_match",
		"interest_match",
		"education_fit",
		"personalization_bonus",
	}
	assert label in {
		"SHAP contribution summary",
		"LIME contribution summary",
		"Weighted fallback contribution summary",
	}
