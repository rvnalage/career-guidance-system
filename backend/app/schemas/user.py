"""Pydantic request and response schemas for authentication and user profile APIs."""

from pydantic import BaseModel


class UserRegisterRequest(BaseModel):
	"""Payload used to register a new user account."""
	full_name: str
	email: str
	password: str
	interests: list[str] = []
	target_roles: list[str] = []


class UserLoginRequest(BaseModel):
	"""Credentials payload used for JWT login."""
	email: str
	password: str


class UserProfile(BaseModel):
	"""Public representation of a user profile returned by the API."""
	user_id: str
	full_name: str
	email: str
	interests: list[str] = []
	target_roles: list[str] = []


class TokenResponse(BaseModel):
	"""Bearer token response returned after successful authentication."""
	access_token: str
	token_type: str = "bearer"
