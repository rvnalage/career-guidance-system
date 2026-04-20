"""Relational ORM models used by the authentication and profile flows."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.postgres_db import Base


class User(Base):
	"""Minimal user record storing identity, credentials, and seed profile fields."""
	__tablename__ = "users"

	id: Mapped[str] = mapped_column(String(36), primary_key=True)
	full_name: Mapped[str] = mapped_column(String(120), nullable=False)
	email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
	hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
	interests: Mapped[str] = mapped_column(String(500), default="", nullable=False)
	target_roles: Mapped[str] = mapped_column(String(500), default="", nullable=False)

