"""Security and token helper functions used by authentication and request validation."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import Any

from jose import JWTError, jwt

from app.config import settings

PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 310000


def _b64encode(value: bytes) -> str:
	"""Encode bytes using URL-safe base64 without trailing padding."""
	return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
	"""Decode URL-safe base64 values while restoring required padding."""
	padding = "=" * (-len(value) % 4)
	return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
	"""Hash a password using PBKDF2-HMAC-SHA256 with a per-password random salt."""
	salt = secrets.token_bytes(16)
	dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
	return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(dk)}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
	"""Verify a plaintext password against PBKDF2 or legacy bcrypt/passlib hashes."""
	if hashed_password.startswith(f"{PBKDF2_PREFIX}$"):
		parts = hashed_password.split("$")
		if len(parts) != 4:
			return False
		try:
			iterations = int(parts[1])
			salt = _b64decode(parts[2])
			expected = _b64decode(parts[3])
		except (ValueError, TypeError):
			return False

		actual = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
		return hmac.compare_digest(actual, expected)

	# Legacy fallback for previously created passlib/bcrypt hashes.
	try:
		from passlib.context import CryptContext

		legacy_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
		return legacy_context.verify(plain_password, hashed_password)
	except Exception:
		return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
	"""Create a signed JWT access token containing the user subject and expiry."""
	expire_delta = timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
	expire = datetime.now(timezone.utc) + expire_delta
	to_encode: dict[str, Any] = {"sub": subject, "exp": expire}
	return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
	"""Decode a JWT token and return payload data, or None when validation fails."""
	try:
		payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
		return payload
	except JWTError:
		return None

