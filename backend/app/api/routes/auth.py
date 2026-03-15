"""Authentication routes for user registration and JWT issuance."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.schemas.common import MessageResponse
from app.schemas.user import TokenResponse, UserLoginRequest, UserRegisterRequest
from app.services.user_service import authenticate_user, create_user, get_user_by_email
from app.utils.helpers import create_access_token
from app.dependencies import get_database_session

router = APIRouter()


@router.post("/register", response_model=MessageResponse)
async def register_user(
	payload: UserRegisterRequest,
	db: Annotated[Session, Depends(get_database_session)],
) -> MessageResponse:
	"""Create a new user account after checking for duplicate email registration."""
	try:
		existing_user = get_user_by_email(db, payload.email)
	except SQLAlchemyError as exc:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail="Database unavailable. Please try again later.",
		) from exc

	if existing_user is not None:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

	try:
		create_user(db, payload)
	except SQLAlchemyError as exc:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail="Database unavailable. Please try again later.",
		) from exc
	return MessageResponse(message=f"User registered successfully: {payload.email}")


@router.post("/login", response_model=TokenResponse)
async def login_user(
	payload: UserLoginRequest,
	db: Annotated[Session, Depends(get_database_session)],
) -> TokenResponse:
	"""Authenticate a user and return a bearer token for protected endpoints."""
	try:
		user = authenticate_user(db, payload.email, payload.password)
	except SQLAlchemyError as exc:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail="Database unavailable. Please try again later.",
		) from exc

	if user is None:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

	token = create_access_token(subject=user.id)
	return TokenResponse(access_token=token)
