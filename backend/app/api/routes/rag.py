from fastapi import APIRouter, Query

from app.schemas.rag import RagIngestRequest, RagIngestResponse, RagSearchResponse, RagStatusResponse
from app.services.rag_service import get_rag_citations, get_rag_status, ingest_directory

router = APIRouter()


@router.get("/status", response_model=RagStatusResponse)
async def rag_status() -> RagStatusResponse:
	return RagStatusResponse(**get_rag_status())


@router.post("/ingest", response_model=RagIngestResponse)
async def rag_ingest(payload: RagIngestRequest) -> RagIngestResponse:
	result = ingest_directory(payload.directory_path)
	return RagIngestResponse(**result)


@router.post("/ingest/default", response_model=RagIngestResponse)
async def rag_ingest_default() -> RagIngestResponse:
	result = ingest_directory(None)
	return RagIngestResponse(**result)


@router.get("/search", response_model=RagSearchResponse)
async def rag_search(
	query: str = Query(..., min_length=2),
	source_type: str | None = Query(default=None),
	topic: str | None = Query(default=None),
	min_education: str | None = Query(default=None),
) -> RagSearchResponse:
	filters = {
		key: value
		for key, value in {
			"source_type": source_type,
			"topic": topic,
			"min_education": min_education,
		}.items()
		if value
	}
	return RagSearchResponse(query=query, results=get_rag_citations(query, metadata_filters=filters or None))
