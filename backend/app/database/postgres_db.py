"""SQLAlchemy engine, session, and initialization helpers for relational storage."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
	"""Declarative base shared by all relational ORM models."""
	pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
	"""Yield a database session and ensure it is closed after request handling."""
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()


def init_db() -> None:
	"""Create configured relational tables after importing model metadata."""
	# Import models so SQLAlchemy can register metadata before table creation.
	from app.database import models  # noqa: F401

	Base.metadata.create_all(bind=engine)
