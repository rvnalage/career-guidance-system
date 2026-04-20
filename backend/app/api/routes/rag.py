"""RAG administration, retrieval, and telemetry routes for the knowledge-base pipeline."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.database.models import User
from app.dependencies import get_current_user
from app.schemas.rag import (
	RagTelemetryCombinedResponse,
	RagEvaluateRequest,
	RagEvaluateResponse,
	RagIngestRequest,
	RagIngestResponse,
	RagSearchResponse,
	RagStatusResponse,
	RagTelemetryTrendSeriesResponse,
	RagTelemetrySummaryResponse,
	RagTelemetryTrendsResponse,
)
from app.services.rag_service import (
	evaluate_retrieval,
	get_rag_citations,
	get_rag_status,
	get_rag_telemetry_trends_combined,
	get_rag_telemetry_trend_series,
	get_rag_telemetry_summary,
	get_rag_telemetry_trends,
	ingest_directory,
)

router = APIRouter()


@router.get("/status", response_model=RagStatusResponse)
async def rag_status() -> RagStatusResponse:
	"""Return current retrieval configuration and ingestion statistics."""
	return RagStatusResponse(**get_rag_status())


@router.post("/ingest", response_model=RagIngestResponse)
async def rag_ingest(payload: RagIngestRequest) -> RagIngestResponse:
	"""Ingest a caller-specified directory into the in-memory knowledge base."""
	result = ingest_directory(payload.directory_path)
	return RagIngestResponse(**result)


@router.post("/ingest/default", response_model=RagIngestResponse)
async def rag_ingest_default() -> RagIngestResponse:
	"""Ingest the default project document directory into the RAG pipeline."""
	result = ingest_directory(None)
	return RagIngestResponse(**result)


@router.get("/search", response_model=RagSearchResponse)
async def rag_search(
	query: str = Query(..., min_length=2),
	source_type: str | None = Query(default=None),
	topic: str | None = Query(default=None),
	min_education: str | None = Query(default=None),
	intent: str | None = Query(default=None),
	target_role: str | None = Query(default=None),
) -> RagSearchResponse:
	"""Search retrieved citations using optional metadata filters on top of the query text."""
	filters = {
		key: value
		for key, value in {
			"source_type": source_type,
			"topic": topic,
			"min_education": min_education,
		}.items()
		if value
	}
	return RagSearchResponse(
		query=query,
		results=get_rag_citations(
			query,
			metadata_filters=filters or None,
			intent=intent,
			target_role=target_role,
		),
	)


@router.post("/evaluate", response_model=RagEvaluateResponse)
async def rag_evaluate(payload: RagEvaluateRequest) -> RagEvaluateResponse:
	"""Evaluate retrieval quality using expected terms/source hints and return scored results."""
	result = evaluate_retrieval(
		payload.query,
		expected_terms=payload.expected_terms,
		expected_source_contains=payload.expected_source_contains,
		metadata_filters=payload.metadata_filters,
		top_k=payload.top_k,
		intent=payload.intent,
		target_role=payload.target_role,
		skill_gaps=payload.skill_gaps,
	)
	return RagEvaluateResponse(**result)


@router.get("/telemetry", response_model=RagTelemetrySummaryResponse)
async def rag_telemetry(
	user_id: str = Query(default="frontend-session-user"),
	limit: int = Query(default=100, ge=1, le=500),
) -> RagTelemetrySummaryResponse:
	"""Return recent per-user RAG telemetry aggregates from assistant-message metadata."""
	result = await get_rag_telemetry_summary(user_id.strip() or "frontend-session-user", limit=limit)
	return RagTelemetrySummaryResponse(**result)


@router.get("/telemetry/me", response_model=RagTelemetrySummaryResponse)
async def rag_telemetry_me(
	current_user: Annotated[User, Depends(get_current_user)],
	limit: int = Query(default=100, ge=1, le=500),
) -> RagTelemetrySummaryResponse:
	"""Return authenticated user's recent RAG telemetry aggregates."""
	result = await get_rag_telemetry_summary(current_user.id, limit=limit)
	return RagTelemetrySummaryResponse(**result)


@router.get("/telemetry/trends", response_model=RagTelemetryTrendsResponse)
async def rag_telemetry_trends(
	user_id: str = Query(default="frontend-session-user"),
	windows: str = Query(default="10,50,100"),
	limit: int | None = Query(default=None, ge=1, le=1000),
) -> RagTelemetryTrendsResponse:
	"""Return windowed per-user telemetry aggregates (for dashboards and trend cards)."""
	parsed_windows = [int(item.strip()) for item in windows.split(",") if item.strip().isdigit()]
	result = await get_rag_telemetry_trends(
		user_id.strip() or "frontend-session-user",
		windows=parsed_windows or [10, 50, 100],
		max_limit=limit,
	)
	return RagTelemetryTrendsResponse(**result)


@router.get("/telemetry/trends/me", response_model=RagTelemetryTrendsResponse)
async def rag_telemetry_trends_me(
	current_user: Annotated[User, Depends(get_current_user)],
	windows: str = Query(default="10,50,100"),
	limit: int | None = Query(default=None, ge=1, le=1000),
) -> RagTelemetryTrendsResponse:
	"""Return authenticated user's windowed telemetry aggregates."""
	parsed_windows = [int(item.strip()) for item in windows.split(",") if item.strip().isdigit()]
	result = await get_rag_telemetry_trends(
		current_user.id,
		windows=parsed_windows or [10, 50, 100],
		max_limit=limit,
	)
	return RagTelemetryTrendsResponse(**result)


@router.get("/telemetry/trends/series", response_model=RagTelemetryTrendSeriesResponse)
async def rag_telemetry_trends_series(
	user_id: str = Query(default="frontend-session-user"),
	windows: str = Query(default="10,50,100"),
	limit: int | None = Query(default=None, ge=1, le=1000),
) -> RagTelemetryTrendSeriesResponse:
	"""Return frontend-ready telemetry trend series with labels and metric arrays."""
	parsed_windows = [int(item.strip()) for item in windows.split(",") if item.strip().isdigit()]
	result = await get_rag_telemetry_trend_series(
		user_id.strip() or "frontend-session-user",
		windows=parsed_windows or [10, 50, 100],
		max_limit=limit,
	)
	return RagTelemetryTrendSeriesResponse(**result)


@router.get("/telemetry/trends/series/me", response_model=RagTelemetryTrendSeriesResponse)
async def rag_telemetry_trends_series_me(
	current_user: Annotated[User, Depends(get_current_user)],
	windows: str = Query(default="10,50,100"),
	limit: int | None = Query(default=None, ge=1, le=1000),
) -> RagTelemetryTrendSeriesResponse:
	"""Return authenticated user's frontend-ready telemetry trend series."""
	parsed_windows = [int(item.strip()) for item in windows.split(",") if item.strip().isdigit()]
	result = await get_rag_telemetry_trend_series(
		current_user.id,
		windows=parsed_windows or [10, 50, 100],
		max_limit=limit,
	)
	return RagTelemetryTrendSeriesResponse(**result)


@router.get("/telemetry/trends/combined", response_model=RagTelemetryCombinedResponse)
async def rag_telemetry_trends_combined(
	user_id: str = Query(default="frontend-session-user"),
	windows: str = Query(default="10,50,100"),
	limit: int | None = Query(default=None, ge=1, le=1000),
) -> RagTelemetryCombinedResponse:
	"""Return both telemetry buckets and frontend-ready chart series in one response."""
	parsed_windows = [int(item.strip()) for item in windows.split(",") if item.strip().isdigit()]
	result = await get_rag_telemetry_trends_combined(
		user_id.strip() or "frontend-session-user",
		windows=parsed_windows or [10, 50, 100],
		max_limit=limit,
	)
	return RagTelemetryCombinedResponse(**result)


@router.get("/telemetry/trends/combined/me", response_model=RagTelemetryCombinedResponse)
async def rag_telemetry_trends_combined_me(
	current_user: Annotated[User, Depends(get_current_user)],
	windows: str = Query(default="10,50,100"),
	limit: int | None = Query(default=None, ge=1, le=1000),
) -> RagTelemetryCombinedResponse:
	"""Return authenticated user's bucket and chart-series telemetry payload."""
	parsed_windows = [int(item.strip()) for item in windows.split(",") if item.strip().isdigit()]
	result = await get_rag_telemetry_trends_combined(
		current_user.id,
		windows=parsed_windows or [10, 50, 100],
		max_limit=limit,
	)
	return RagTelemetryCombinedResponse(**result)

