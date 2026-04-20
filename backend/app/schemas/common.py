"""Small shared schemas reused across multiple API route modules."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from pydantic import BaseModel


class MessageResponse(BaseModel):
	"""Simple single-message response payload."""
	message: str

