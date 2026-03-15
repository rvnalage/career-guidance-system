"""High-level RAG orchestration for ingestion, retrieval, and citation formatting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.rag.knowledge_base import KnowledgeChunk, build_base_corpus, load_document_chunks
from app.rag.query_rewriter import rewrite_query
from app.rag.retriever import Retriever
from app.rag.vector_store import InMemoryVectorStore


BASE_CORPUS = build_base_corpus()
DOC_CORPUS: list[KnowledgeChunk] = []
VECTOR_STORE = InMemoryVectorStore()
RETRIEVER = Retriever(VECTOR_STORE)

INGESTION_META = {
	"last_ingested_at": None,
	"ingested_files": [],
	"skipped_noisy_chunks": 0,
	"skipped_duplicate_chunks": 0,
}
_VECTOR_INDEX_READY = False


def _ensure_vector_index() -> None:
	"""Build the active vector index on demand so app startup stays lightweight."""
	global _VECTOR_INDEX_READY
	if _VECTOR_INDEX_READY:
		return
	VECTOR_STORE.set_chunks(_active_corpus())
	_VECTOR_INDEX_READY = True


def ingest_directory(directory_path: str | None = None) -> dict[str, Any]:
	"""Ingest document chunks from disk and refresh the active in-memory vector index."""
	global _VECTOR_INDEX_READY
	result = load_document_chunks(directory_path)
	DOC_CORPUS.clear()
	DOC_CORPUS.extend(result["ingested_chunks"])
	VECTOR_STORE.set_chunks(_active_corpus())
	_VECTOR_INDEX_READY = True

	INGESTION_META["last_ingested_at"] = datetime.now(timezone.utc).isoformat()
	INGESTION_META["ingested_files"] = result["ingested_files"]
	INGESTION_META["skipped_noisy_chunks"] = result.get("skipped_noisy_chunks", 0)
	INGESTION_META["skipped_duplicate_chunks"] = result.get("skipped_duplicate_chunks", 0)

	return {
		"ingested_files": result["ingested_files"],
		"ingested_chunks": len(DOC_CORPUS),
		"skipped_files": result["skipped_files"],
		"skipped_noisy_chunks": result.get("skipped_noisy_chunks", 0),
		"skipped_duplicate_chunks": result.get("skipped_duplicate_chunks", 0),
		"target_path": result["target_path"],
	}


def get_rag_status() -> dict[str, Any]:
	"""Return current RAG configuration and latest ingestion metadata."""
	return {
		"enabled": settings.rag_enabled,
		"top_k": settings.rag_top_k,
		"candidate_pool_size": settings.rag_candidate_pool_size,
		"base_chunks": len(BASE_CORPUS),
		"document_chunks": len(DOC_CORPUS),
		"total_chunks": len(BASE_CORPUS) + len(DOC_CORPUS),
		"last_ingested_at": INGESTION_META.get("last_ingested_at"),
		"ingested_files": INGESTION_META.get("ingested_files", []),
		"skipped_noisy_chunks": INGESTION_META.get("skipped_noisy_chunks", 0),
		"skipped_duplicate_chunks": INGESTION_META.get("skipped_duplicate_chunks", 0),
	}


def _active_corpus() -> list[KnowledgeChunk]:
	"""Return the combined built-in and dynamically ingested corpus."""
	return BASE_CORPUS + DOC_CORPUS


def retrieve_relevant_chunks(
	query: str,
	top_k: int | None = None,
	metadata_filters: dict[str, str] | None = None,
) -> list[KnowledgeChunk]:
	"""Retrieve top chunks for a query using rewriting, reranking, and optional metadata filters."""
	if not settings.rag_enabled:
		return []
	_ensure_vector_index()
	rewritten_query = rewrite_query(query)
	limit = top_k if top_k is not None else settings.rag_top_k
	auto_filters = infer_metadata_filters(rewritten_query)
	resolved_filters = metadata_filters or auto_filters
	results = RETRIEVER.retrieve(
		query=rewritten_query,
		top_k=max(1, limit),
		fallback_chunks=_active_corpus(),
		metadata_filters=resolved_filters,
		candidate_pool_size=max(limit, settings.rag_candidate_pool_size),
	)
	if not results and not metadata_filters and auto_filters:
		return RETRIEVER.retrieve(
			query=rewritten_query,
			top_k=max(1, limit),
			fallback_chunks=_active_corpus(),
			metadata_filters=None,
			candidate_pool_size=max(limit, settings.rag_candidate_pool_size),
		)
	return results


def build_rag_context(query: str, metadata_filters: dict[str, str] | None = None) -> str:
	"""Render retrieved chunks into a compact bullet-list context string for prompting."""
	chunks = retrieve_relevant_chunks(query, metadata_filters=metadata_filters)
	if not chunks:
		return ""
	lines = [f"- {chunk.title}: {chunk.text}" for chunk in chunks]
	return "\n".join(lines)


def get_rag_citations(
	query: str,
	metadata_filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
	"""Convert retrieved chunks into API-friendly citation dictionaries."""
	chunks = retrieve_relevant_chunks(query, metadata_filters=metadata_filters)
	citations: list[dict[str, Any]] = []
	for chunk in chunks:
		citations.append(
			{
				"title": chunk.title,
				"source": chunk.source,
				"source_type": chunk.source_type,
				"snippet": chunk.text[:240],
				"metadata": chunk.metadata,
			}
		)
	return citations


def infer_metadata_filters(query: str) -> dict[str, str]:
	"""Infer coarse metadata filters from query wording to improve retrieval precision."""
	text = query.lower()
	filters: dict[str, str] = {}

	if "document" in text or "notes" in text:
		filters["topic"] = "document"
	elif "interview" in text:
		filters["topic"] = "interview"
	elif "roadmap" in text or "learning" in text:
		filters["topic"] = "learning"

	if any(token in text for token in ["role", "career", "job", "fit"]):
		if "bachelor" in text:
			filters["min_education"] = "bachelor"
		elif "master" in text or "mtech" in text:
			filters["min_education"] = "master"

	return filters
