"""User CRUD and authentication helpers backed by the relational database."""

import uuid

from sqlalchemy.orm import Session

from app.database.models import User
from app.schemas.user import UserProfile, UserRegisterRequest
from app.utils.helpers import hash_password, verify_password


def _to_csv(values: list[str]) -> str:
	"""Serialize list fields for the current simple relational storage schema."""
	return ",".join([value.strip() for value in values if value.strip()])


def _from_csv(value: str) -> list[str]:
	"""Deserialize comma-separated profile fields into API-friendly lists."""
	if not value:
		return []
	return [item.strip() for item in value.split(",") if item.strip()]


def to_user_profile(user: User) -> UserProfile:
	"""Convert an ORM user model into the public user-profile schema."""
	return UserProfile(
		user_id=user.id,
		full_name=user.full_name,
		email=user.email,
		interests=_from_csv(user.interests),
		target_roles=_from_csv(user.target_roles),
	)


def get_user_by_email(db: Session, email: str) -> User | None:
	"""Return the first user matching the provided email address, if any."""
	return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: str) -> User | None:
	"""Return a user by primary key for auth and profile lookups."""
	return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, payload: UserRegisterRequest) -> User:
	"""Create and persist a new user with hashed password and normalized list fields."""
	user = User(
		id=str(uuid.uuid4()),
		full_name=payload.full_name,
		email=payload.email,
		hashed_password=hash_password(payload.password),
		interests=_to_csv(payload.interests),
		target_roles=_to_csv(payload.target_roles),
	)
	db.add(user)
	db.commit()
	db.refresh(user)
	return user


def update_user_profile(db: Session, user: User, payload: UserProfile) -> User:
	"""Update mutable profile fields for an existing user and return the refreshed model."""
	user.full_name = payload.full_name
	user.interests = _to_csv(payload.interests)
	user.target_roles = _to_csv(payload.target_roles)
	db.add(user)
	db.commit()
	db.refresh(user)
	return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
	"""Validate credentials and return the matching user only when password verification succeeds."""
	user = get_user_by_email(db, email)
	if user is None:
		return None
	if not verify_password(password, user.hashed_password):
		return None
	return user
