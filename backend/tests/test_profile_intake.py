import asyncio

from app.database.models import User
from app.dependencies import get_current_user
from app.services.profile_service import get_user_profile


def test_profile_intake_upload_requires_auth(client):
	response = client.post("/api/v1/profile-intake/upload")
	assert response.status_code == 401


def test_profile_intake_upload_self_persists_profile(client):
	def _override_user() -> User:
		return User(
			id="profile-intake-self-user",
			full_name="Profile Self",
			email="profile-self@example.com",
			hashed_password="hashed",
			interests="",
			target_roles="",
		)

	client.app.dependency_overrides[get_current_user] = _override_user
	try:
		files = [
			(
				"files",
				(
					"profile.txt",
					"I am an MTech student with Python and SQL skills. I like analytics and data science. investigative: 5",
					"text/plain",
				),
			)
		]
		response = client.post(
			"/api/v1/profile-intake/upload",
			data={"owner_type": "self"},
			files=files,
		)
		assert response.status_code == 200
		body = response.json()
		assert body["persisted_to_user_profile"] is True
		assert body["files_processed"] == 1
		assert "python" in body["extracted_profile"]["skills"]

		profile = asyncio.run(get_user_profile("profile-intake-self-user"))
		assert "python" in profile.get("skills", [])
	finally:
		client.app.dependency_overrides.clear()


def test_profile_intake_upload_on_behalf_does_not_persist(client):
	def _override_user() -> User:
		return User(
			id="profile-intake-behalf-user",
			full_name="Profile Behalf",
			email="profile-behalf@example.com",
			hashed_password="hashed",
			interests="",
			target_roles="",
		)

	client.app.dependency_overrides[get_current_user] = _override_user
	try:
		files = [
			(
				"files",
				(
					"other.txt",
					"This profile is for someone else with Python and AI interests.",
					"text/plain",
				),
			)
		]
		response = client.post(
			"/api/v1/profile-intake/upload",
			data={"owner_type": "on_behalf"},
			files=files,
		)
		assert response.status_code == 200
		body = response.json()
		assert body["persisted_to_user_profile"] is False
		assert body["files_processed"] == 1

		profile = asyncio.run(get_user_profile("profile-intake-behalf-user"))
		assert profile == {}
	finally:
		client.app.dependency_overrides.clear()
