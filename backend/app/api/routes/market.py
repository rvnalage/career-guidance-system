from fastapi import APIRouter

from app.schemas.market import JobMarketResponse
from app.services.market_service import fetch_job_market_data

router = APIRouter()


@router.get("/jobs", response_model=JobMarketResponse)
async def get_market_jobs(search: str = "data", limit: int = 10) -> JobMarketResponse:
	source, items = fetch_job_market_data(search, limit)
	return JobMarketResponse(source=source, query=search, results=items)
