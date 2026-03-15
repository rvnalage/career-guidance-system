from app.services.profile_service import merge_context_with_profile, summarize_profile


def test_merge_context_with_profile_combines_skills_and_role():
	context = {"skills": ["Python"], "interests": ["AI"]}
	profile = {
		"skills": ["sql", "python"],
		"interests": ["data"],
		"target_role": "data scientist",
	}
	merged = merge_context_with_profile(context, profile)
	assert set(merged["skills"]) == {"python", "sql"}
	assert set(merged["interests"]) == {"ai", "data"}
	assert merged["target_role"] == "data scientist"


def test_summarize_profile_contains_key_fields():
	profile = {
		"target_role": "ml engineer",
		"skills": ["python", "sql"],
		"interests": ["ai"],
		"last_intent": "learning_path",
	}
	summary = summarize_profile(profile)
	assert "target_role=ml engineer" in summary
	assert "skills=python, sql" in summary
	assert "last_intent=learning_path" in summary
