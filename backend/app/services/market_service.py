"""Job-market retrieval helpers with graceful fallback when the external API fails."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


import asyncio
import time
from typing import Any

import httpx

from app.config import settings
from app.schemas.market import JobMarketItem

# Simple in-memory TTL cache for async Remotive lookups: key -> (timestamp, (source, items)).
_job_cache: dict[str, tuple[float, tuple[str, list[JobMarketItem]]]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _fallback_jobs(query: str) -> list[JobMarketItem]:
	"""Return deterministic sample jobs so the UI remains usable without live market data."""
	query_hint = query.strip() or "technology"
	return [
		JobMarketItem(
			job_title=f"Junior {query_hint.title()} Analyst",
			company="Career Labs",
			location="Remote",
			category="Data",
			url="https://example.com/jobs/1",
			published_at="N/A",
		),
		JobMarketItem(
			job_title=f"{query_hint.title()} Associate",
			company="Future Skills Pvt Ltd",
			location="Hybrid",
			category="Engineering",
			url="https://example.com/jobs/2",
			published_at="N/A",
		),
	]


def fetch_job_market_data(query: str, limit: int = 10) -> tuple[str, list[JobMarketItem]]:
	"""Sync wrapper â€” kept for any non-async callers; delegates to async implementation."""
	return asyncio.get_event_loop().run_until_complete(fetch_job_market_data_async(query, limit))


async def fetch_job_market_data_async(query: str, limit: int = 10) -> tuple[str, list[JobMarketItem]]:
	"""Fetch jobs asynchronously, prefer cached/live Remotive results, and fall back to deterministic samples."""
	cache_key = f"{query.strip().lower()}:{limit}"
	cached = _job_cache.get(cache_key)
	if cached and (time.monotonic() - cached[0]) < _CACHE_TTL_SECONDS:
		return cached[1]

	params = {"search": query.strip(), "limit": max(1, min(50, limit))}
	result: tuple[str, list[JobMarketItem]]
	try:
		async with httpx.AsyncClient(timeout=8.0) as client:
			response = await client.get(settings.job_market_api_url, params=params)
			response.raise_for_status()
			payload: dict[str, Any] = response.json()
			jobs = payload.get("jobs", [])
			items: list[JobMarketItem] = []
			for job in jobs[: params["limit"]]:
				items.append(
					JobMarketItem(
						job_title=str(job.get("title", "Unknown role")),
						company=str(job.get("company_name", "Unknown company")),
						location=str(job.get("candidate_required_location", "Remote")),
						category=str(job.get("category", "General")),
						url=str(job.get("url", "")),
						published_at=str(job.get("publication_date", "")),
					)
				)
			if items:
				result = ("remotive", items)
				_job_cache[cache_key] = (time.monotonic(), result)
				return result
	except Exception:
		pass

	result = ("fallback", _fallback_jobs(query))
	return result

