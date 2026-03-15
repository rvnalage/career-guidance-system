"""Job-market retrieval helpers with graceful fallback when the external API fails."""

from typing import Any

import requests

from app.config import settings
from app.schemas.market import JobMarketItem


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
	"""Fetch market jobs from the configured API and fall back to local sample data on failure."""
	params = {"search": query.strip(), "limit": max(1, min(50, limit))}
	try:
		response = requests.get(settings.job_market_api_url, params=params, timeout=8)
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
			return "remotive", items
	except Exception:
		pass

	return "fallback", _fallback_jobs(query)
