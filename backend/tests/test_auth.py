import asyncio

from app.database.models import User
from app.dependencies import get_current_user
from app.services.history_service import append_message


def _auth_override_user() -> User:
	return User(
		id="test-user-1",
		full_name="Test Student",
		email="test@example.com",
		hashed_password="hashed",
		interests="ai,data",
		target_roles="machine learning engineer",
	)


def test_history_me_requires_auth(client):
	response = client.get("/api/v1/history/me")
	assert response.status_code == 401


def test_clear_history_me_requires_auth(client):
	response = client.delete("/api/v1/history/me")
	assert response.status_code == 401


def test_dashboard_me_requires_auth(client):
	response = client.get("/api/v1/dashboard/summary/me")
	assert response.status_code == 401


def test_dashboard_report_me_requires_auth(client):
	response = client.get("/api/v1/dashboard/report/me")
	assert response.status_code == 401


def test_recommendation_history_me_requires_auth(client):
	response = client.get("/api/v1/recommendations/history/me")
	assert response.status_code == 401


def test_recommendation_feedback_me_requires_auth(client):
	response = client.post(
		"/api/v1/recommendations/feedback/me",
		json={"role": "Data Analyst", "helpful": True, "rating": 5, "feedback_tags": ["skills"]},
	)
	assert response.status_code == 401


def test_recommendation_explain_me_requires_auth(client):
	response = client.post(
		"/api/v1/recommendations/explain/me",
		json={"interests": ["AI"], "skills": ["Python"], "education_level": "master"},
	)
	assert response.status_code == 401


def test_clear_recommendation_history_me_requires_auth(client):
	response = client.delete("/api/v1/recommendations/history/me")
	assert response.status_code == 401


def test_generate_recommendation_requires_auth(client):
	payload = {
		"user_id": "ignored",
		"interests": ["AI"],
		"skills": ["Python"],
		"education_level": "master",
	}
	response = client.post("/api/v1/recommendations/generate", json=payload)
	assert response.status_code == 401


def test_psychometric_score_me_requires_auth(client):
	response = client.post("/api/v1/psychometric/score/me", json={"dimensions": {"investigative": 5}})
	assert response.status_code == 401


def test_psychometric_profile_me_requires_auth(client):
	response = client.get("/api/v1/psychometric/profile/me")
	assert response.status_code == 401


def test_history_me_with_auth_returns_user_history(client):
	client.app.dependency_overrides[get_current_user] = _auth_override_user
	try:
		asyncio.run(append_message("test-user-1", "user", "I need interview prep"))
		asyncio.run(append_message("test-user-1", "assistant", "Let's begin interview preparation."))
		response = client.get("/api/v1/history/me")
		assert response.status_code == 200
		body = response.json()
		assert body["user_id"] == "test-user-1"
		assert len(body["messages"]) >= 1
	finally:
		client.app.dependency_overrides.clear()


def test_clear_history_me_with_auth(client):
	client.app.dependency_overrides[get_current_user] = _auth_override_user
	try:
		asyncio.run(append_message("test-user-1", "user", "Temporary message"))
		clear_response = client.delete("/api/v1/history/me")
		assert clear_response.status_code == 200
		clear_body = clear_response.json()
		assert clear_body["user_id"] == "test-user-1"
		assert "deleted_count" in clear_body

		history_response = client.get("/api/v1/history/me")
		assert history_response.status_code == 200
		assert history_response.json()["messages"] == []
	finally:
		client.app.dependency_overrides.clear()


def test_recommendation_generate_and_history_me_with_auth(client):
	client.app.dependency_overrides[get_current_user] = _auth_override_user
	try:
		payload = {
			"interests": ["AI", "Data Science"],
			"skills": ["Python", "Machine Learning", "SQL"],
			"education_level": "master",
		}
		generate_response = client.post("/api/v1/recommendations/generate", json=payload)
		assert generate_response.status_code == 200
		assert len(generate_response.json()["recommendations"]) == 3

		history_response = client.get("/api/v1/recommendations/history/me")
		assert history_response.status_code == 200
		history = history_response.json()["history"]
		assert len(history) >= 1
		assert history[0]["user_id"] == "test-user-1"
	finally:
		client.app.dependency_overrides.clear()


def test_clear_recommendation_history_me_with_auth(client):
	client.app.dependency_overrides[get_current_user] = _auth_override_user
	try:
		payload = {
			"interests": ["AI", "Data Science"],
			"skills": ["Python", "Machine Learning", "SQL"],
			"education_level": "master",
		}
		client.post("/api/v1/recommendations/generate", json=payload)

		clear_response = client.delete("/api/v1/recommendations/history/me")
		assert clear_response.status_code == 200
		clear_body = clear_response.json()
		assert clear_body["user_id"] == "test-user-1"
		assert "deleted_count" in clear_body

		history_response = client.get("/api/v1/recommendations/history/me")
		assert history_response.status_code == 200
		assert history_response.json()["history"] == []
	finally:
		client.app.dependency_overrides.clear()


def test_dashboard_summary_me_with_auth(client):
	client.app.dependency_overrides[get_current_user] = _auth_override_user
	try:
		client.post(
			"/api/v1/recommendations/generate",
			json={
				"interests": ["AI", "Software"],
				"skills": ["Python", "FastAPI", "SQL"],
				"education_level": "master",
			},
		)
		response = client.get("/api/v1/dashboard/summary/me")
		assert response.status_code == 200
		body = response.json()
		assert body["user_id"] == "test-user-1"
		assert "top_roles" in body
		assert "profile_completion" in body
	finally:
		client.app.dependency_overrides.clear()


def test_dashboard_report_me_with_auth(client):
	client.app.dependency_overrides[get_current_user] = _auth_override_user
	try:
		client.post(
			"/api/v1/recommendations/generate",
			json={
				"interests": ["AI", "Software"],
				"skills": ["Python", "FastAPI", "SQL"],
				"education_level": "master",
			},
		)
		response = client.get("/api/v1/dashboard/report/me")
		assert response.status_code == 200
		body = response.json()
		assert "generated_at" in body
		assert "summary" in body
		assert "recent_chat_messages" in body
		assert "latest_recommendations" in body
		assert "recommendation_history" in body
	finally:
		client.app.dependency_overrides.clear()


def test_recommendation_explain_and_feedback_with_auth(client):
	client.app.dependency_overrides[get_current_user] = _auth_override_user
	try:
		explain_response = client.post(
			"/api/v1/recommendations/explain/me",
			json={
				"interests": ["AI", "Software"],
				"skills": ["Python", "SQL"],
				"education_level": "master",
			},
		)
		assert explain_response.status_code == 200
		explain_body = explain_response.json()
		assert "explanations" in explain_body
		assert len(explain_body["explanations"]) >= 1
		assert "contributions" in explain_body["explanations"][0]

		feedback_response = client.post(
			"/api/v1/recommendations/feedback/me",
			json={
				"role": explain_body["explanations"][0]["role"],
				"helpful": True,
				"rating": 5,
				"feedback_tags": ["skills"],
			},
		)
		assert feedback_response.status_code == 200
		assert feedback_response.json()["message"] == "Feedback recorded"
	finally:
		client.app.dependency_overrides.clear()


def test_psychometric_profile_me_with_auth(client):
	client.app.dependency_overrides[get_current_user] = _auth_override_user
	try:
		score_response = client.post(
			"/api/v1/psychometric/score/me",
			json={
				"dimensions": {
					"investigative": 5,
					"social": 4,
					"enterprising": 3,
				}
			},
		)
		assert score_response.status_code == 200
		score_body = score_response.json()
		assert len(score_body["recommended_domains"]) >= 1

		profile_response = client.get("/api/v1/psychometric/profile/me")
		assert profile_response.status_code == 200
		profile_body = profile_response.json()
		assert profile_body["top_traits"] == score_body["top_traits"]
		assert profile_body["recommended_domains"] == score_body["recommended_domains"]
	finally:
		client.app.dependency_overrides.clear()
