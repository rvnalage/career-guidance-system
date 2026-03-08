from pydantic import BaseModel


class UserRegisterRequest(BaseModel):
	full_name: str
	email: str
	password: str
	interests: list[str] = []
	target_roles: list[str] = []


class UserLoginRequest(BaseModel):
	email: str
	password: str


class UserProfile(BaseModel):
	user_id: str
	full_name: str
	email: str
	interests: list[str] = []
	target_roles: list[str] = []


class TokenResponse(BaseModel):
	access_token: str
	token_type: str = "bearer"
