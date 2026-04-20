"""Pydantic schemas for job-market search results."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from pydantic import BaseModel


class JobMarketItem(BaseModel):
	"""Single job listing returned from the market service."""
	job_title: str
	company: str
	location: str
	category: str
	url: str
	published_at: str


class JobMarketResponse(BaseModel):
	"""Envelope for job-market search responses."""
	source: str
	query: str
	results: list[JobMarketItem]

