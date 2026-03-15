import asyncio

from app.database.models import User
from app.dependencies import get_current_user
from app.services.profile_service import get_user_profile


def _chat_auth_override_user() -> User:
	return User(
		id="chat-user-1",
		full_name="Chat Student",
		email="chat@example.com",
		hashed_password="hashed",
		interests="ai,data",
		target_roles="machine learning engineer",
	)


def test_chat_route_learning_intent(client):
	payload = {
		"user_id": "student-11",
		"message": "Can you give me a learning roadmap for data science?",
		"context": {},
	}
	response = client.post("/api/v1/chat/message", json=payload)
	assert response.status_code == 200
	body = response.json()
	assert "roadmap" in body["reply"].lower() or "skill" in body["reply"].lower()
	assert "relevant references" in body["reply"].lower()
	assert isinstance(body.get("rag_citations"), list)
	assert len(body.get("rag_citations", [])) >= 1
	assert "plan" in body["suggested_next_step"].lower() or "share" in body["suggested_next_step"].lower()


def test_chat_route_interview_intent(client):
	payload = {
		"user_id": "student-12",
		"message": "Help me prepare for technical interview",
		"context": {},
	}
	response = client.post("/api/v1/chat/message", json=payload)
	assert response.status_code == 200
	body = response.json()
	assert "interview" in body["reply"].lower()
	assert "role" in body["suggested_next_step"].lower() or "track" in body["suggested_next_step"].lower()


def test_chat_message_me_requires_auth(client):
	response = client.post("/api/v1/chat/message/me", json={"message": "Help with jobs", "context": {}})
	assert response.status_code == 401


def test_chat_message_me_with_auth(client):
	client.app.dependency_overrides[get_current_user] = _chat_auth_override_user
	try:
		response = client.post("/api/v1/chat/message/me", json={"message": "Help with interview prep", "context": {}})
		assert response.status_code == 200
		body = response.json()
		assert "reply" in body
		assert "suggested_next_step" in body
	finally:
		client.app.dependency_overrides.clear()


def test_chat_message_me_on_behalf_does_not_persist_profile(client):
	def _override_user() -> User:
		return User(
			id="chat-on-behalf-user",
			full_name="On Behalf User",
			email="onbehalf@example.com",
			hashed_password="hashed",
			interests="",
			target_roles="",
		)

	client.app.dependency_overrides[get_current_user] = _override_user
	try:
		response = client.post(
			"/api/v1/chat/message/me",
			json={
				"message": "I need guidance for my cousin",
				"context": {},
				"context_owner_type": "on_behalf",
				"skills": ["python"],
				"interests": ["data science"],
				"education_level": "master",
			},
		)
		assert response.status_code == 200
		profile = asyncio.run(get_user_profile("chat-on-behalf-user"))
		assert profile == {}
	finally:
		client.app.dependency_overrides.clear()


def test_chat_message_me_self_persists_profile_fields(client):
	def _override_user() -> User:
		return User(
			id="chat-self-user",
			full_name="Self User",
			email="self@example.com",
			hashed_password="hashed",
			interests="",
			target_roles="",
		)

	client.app.dependency_overrides[get_current_user] = _override_user
	try:
		response = client.post(
			"/api/v1/chat/message/me",
			json={
				"message": "I want career guidance for myself",
				"context": {},
				"context_owner_type": "self",
				"skills": ["python", "sql"],
				"interests": ["analytics"],
				"education_level": "master",
				"psychometric_dimensions": {"investigative": 5},
			},
		)
		assert response.status_code == 200
		profile = asyncio.run(get_user_profile("chat-self-user"))
		assert "python" in profile.get("skills", [])
		assert "analytics" in profile.get("interests", [])
	finally:
		client.app.dependency_overrides.clear()
