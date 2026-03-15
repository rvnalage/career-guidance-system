"""Small shared schemas reused across multiple API route modules."""

from pydantic import BaseModel


class MessageResponse(BaseModel):
	"""Simple single-message response payload."""
	message: str
