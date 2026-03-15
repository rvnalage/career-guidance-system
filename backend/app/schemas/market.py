"""Pydantic schemas for job-market search results."""

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
