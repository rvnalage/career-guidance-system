from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.postgres_db import get_db
from app.services.user_service import get_user_by_id
from app.utils.helpers import decode_access_token


def get_app_settings() -> Settings:
	return get_settings()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_database_session():
	yield from get_db()


def get_current_user(
	db: Annotated[Session, Depends(get_database_session)],
	token: Annotated[str, Depends(oauth2_scheme)],
):
	payload = decode_access_token(token)
	if payload is None or "sub" not in payload:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid or expired access token",
		)

	try:
		user = get_user_by_id(db, payload["sub"])
	except SQLAlchemyError as exc:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail="Database unavailable. Please try again later.",
		) from exc

	if user is None:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
	return user
