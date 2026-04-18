"""Market-data routes for retrieving current job listings from the external job source."""

from fastapi import APIRouter

from app.schemas.market import JobMarketResponse
from app.services.market_service import fetch_job_market_data_async

router = APIRouter()


@router.get("/jobs", response_model=JobMarketResponse)
async def get_market_jobs(search: str = "data", limit: int = 10) -> JobMarketResponse:
	"""Fetch a limited set of job listings matching the provided search term."""
	source, items = await fetch_job_market_data_async(search, limit)
	return JobMarketResponse(source=source, query=search, results=items)
