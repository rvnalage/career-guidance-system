"""High-level RAG orchestration for ingestion, retrieval, and citation formatting.

Developer Onboarding Notes:
- Layer: service orchestration (RAG core)
- Role in system: Owns ingest, retrieval, citation formatting, and retrieval telemetry.
- Main callers: `app.api.routes.rag`, `app.api.routes.chat`, `app.services.llm_service`.
- Reading order:
	1) `ingest_directory` and `get_rag_status` for corpus lifecycle,
	2) `retrieve_relevant_chunks` / `_retrieve_relevant_chunks_with_metrics` for query flow,
	3) `get_rag_payload_with_metrics` and telemetry functions for runtime observability.
"""


from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from app.config import settings
from app.services.history_service import get_user_history
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
	"""Build active vector index lazily.

	Significance:
		Delays vectorization cost until first retrieval, reducing startup overhead.

	Used by:
		`_retrieve_relevant_chunks_with_metrics`.
	"""
	global _VECTOR_INDEX_READY
	if _VECTOR_INDEX_READY:
		return
	VECTOR_STORE.set_chunks(_active_corpus())
	_VECTOR_INDEX_READY = True


def ingest_directory(directory_path: str | None = None) -> dict[str, Any]:
	"""Ingest disk documents and rebuild the active vector index.

	Args:
		directory_path: Optional custom path. When None, default ingest resolution is used.

	Returns:
		Ingestion summary including chunk counts, skipped stats, and target path.

	Significance:
		Single source of truth for corpus refresh. Updates both data (`DOC_CORPUS`)
		and observability metadata (`INGESTION_META`).

	Used by:
		- `app.main` startup auto-ingest
		- `app.api.routes.rag` ingest endpoints
	"""
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
	"""Return runtime RAG status snapshot.

	Significance:
		Primary diagnostics endpoint for corpus size, source coverage, and ingest health.

	Used by:
		`app.api.routes.rag.rag_status`.
	"""
	active_corpus = _active_corpus()
	unique_sources = {chunk.source for chunk in active_corpus if str(chunk.source).strip()}
	return {
		"enabled": settings.rag_enabled,
		"top_k": settings.rag_top_k,
		"candidate_pool_size": settings.rag_candidate_pool_size,
		"base_chunks": len(BASE_CORPUS),
		"document_chunks": len(DOC_CORPUS),
		"total_chunks": len(active_corpus),
		"total_sources": len(unique_sources),
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
	intent: str | None = None,
	target_role: str | None = None,
	skill_gaps: list[str] | None = None,
) -> list[KnowledgeChunk]:
	"""Retrieve top chunks for query using rewrite + rerank pipeline.

	Significance:
		Canonical read path used by context builders and citation APIs.

	Used by:
		`build_rag_context`, `get_rag_citations`, `evaluate_retrieval`.
	"""
	chunks, _ = _retrieve_relevant_chunks_with_metrics(
		query,
		top_k=top_k,
		metadata_filters=metadata_filters,
		intent=intent,
		target_role=target_role,
		skill_gaps=skill_gaps,
	)
	return chunks


def _retrieve_relevant_chunks_with_metrics(
	query: str,
	*,
	top_k: int | None = None,
	metadata_filters: dict[str, str] | None = None,
	intent: str | None = None,
	target_role: str | None = None,
	skill_gaps: list[str] | None = None,
) -> tuple[list[KnowledgeChunk], dict[str, Any]]:
	"""Retrieve chunks plus retrieval diagnostics.

	Significance:
		Adds telemetry fields (latency, fallback behavior, filters) so downstream
		routes can measure retrieval quality without duplicate lookups.

	Used by:
		`get_rag_payload_with_metrics`.
	"""
	started = perf_counter()
	if not settings.rag_enabled:
		return [], {
			"rag_enabled": False,
			"retrieval_ms": int((perf_counter() - started) * 1000),
			"retrieved_count": 0,
			"fallback_without_filters": False,
			"metadata_filters": {},
			"auto_filters_used": False,
			"query_chars": len(query),
			"rewritten_query": query,
			"top_titles": [],
		}
	_ensure_vector_index()
	rewritten_query = rewrite_query(
		query,
		intent=intent,
		target_role=target_role,
		skill_gaps=skill_gaps,
	)
	limit = top_k if top_k is not None else settings.rag_top_k
	auto_filters = infer_metadata_filters(rewritten_query)
	resolved_filters = metadata_filters or auto_filters
	fallback_without_filters = False
	results = RETRIEVER.retrieve(
		query=rewritten_query,
		top_k=max(1, limit),
		fallback_chunks=_active_corpus(),
		metadata_filters=resolved_filters,
		candidate_pool_size=max(limit, settings.rag_candidate_pool_size),
	)
	if not results and not metadata_filters and auto_filters:
		fallback_without_filters = True
		results = RETRIEVER.retrieve(
			query=rewritten_query,
			top_k=max(1, limit),
			fallback_chunks=_active_corpus(),
			metadata_filters=None,
			candidate_pool_size=max(limit, settings.rag_candidate_pool_size),
		)
	metrics = {
		"rag_enabled": True,
		"retrieval_ms": int((perf_counter() - started) * 1000),
		"retrieved_count": len(results),
		"fallback_without_filters": fallback_without_filters,
		"metadata_filters": resolved_filters or {},
		"auto_filters_used": bool(auto_filters) and metadata_filters is None,
		"query_chars": len(query),
		"rewritten_query": rewritten_query,
		"intent": intent,
		"target_role": target_role,
		"skill_gap_count": len(skill_gaps or []),
		"top_titles": [chunk.title for chunk in results[:3]],
	}
	return results, metrics


def build_rag_context(
	query: str,
	metadata_filters: dict[str, str] | None = None,
	*,
	intent: str | None = None,
	target_role: str | None = None,
	skill_gaps: list[str] | None = None,
) -> str:
	"""Render retrieved chunks into a compact bullet-list context string for prompting."""
	chunks = retrieve_relevant_chunks(
		query,
		metadata_filters=metadata_filters,
		intent=intent,
		target_role=target_role,
		skill_gaps=skill_gaps,
	)
	return build_rag_context_from_chunks(chunks)


def build_rag_context_from_chunks(chunks: list[KnowledgeChunk]) -> str:
	"""Render an already retrieved chunk list into the prompt context format."""
	if not chunks:
		return ""
	lines = [f"- {chunk.title}: {chunk.text}" for chunk in chunks]
	return "\n".join(lines)


def get_rag_citations(
	query: str,
	metadata_filters: dict[str, str] | None = None,
	*,
	intent: str | None = None,
	target_role: str | None = None,
	skill_gaps: list[str] | None = None,
) -> list[dict[str, Any]]:
	"""Convert retrieved chunks into API-friendly citation dictionaries."""
	chunks = retrieve_relevant_chunks(
		query,
		metadata_filters=metadata_filters,
		intent=intent,
		target_role=target_role,
		skill_gaps=skill_gaps,
	)
	return build_rag_citations_from_chunks(chunks)


def build_rag_citations_from_chunks(chunks: list[KnowledgeChunk]) -> list[dict[str, Any]]:
	"""Convert an already retrieved chunk list into API-friendly citation dictionaries."""
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


def get_rag_payload(
	query: str,
	metadata_filters: dict[str, str] | None = None,
	*,
	intent: str | None = None,
	target_role: str | None = None,
	skill_gaps: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
	"""Retrieve once and return both prompt context and citations to avoid duplicate retrieval work."""
	chunks = retrieve_relevant_chunks(
		query,
		metadata_filters=metadata_filters,
		intent=intent,
		target_role=target_role,
		skill_gaps=skill_gaps,
	)
	return build_rag_context_from_chunks(chunks), build_rag_citations_from_chunks(chunks)


def get_rag_payload_with_metrics(
	query: str,
	metadata_filters: dict[str, str] | None = None,
	*,
	intent: str | None = None,
	target_role: str | None = None,
	skill_gaps: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
	"""Return context, citations, and retrieval metrics in one pass.

	Significance:
		Avoids duplicate retrieval work in chat flow while preserving telemetry.

	Used by:
		`app.api.routes.chat` for response assembly + telemetry persistence.
	"""
	chunks, metrics = _retrieve_relevant_chunks_with_metrics(
		query,
		metadata_filters=metadata_filters,
		intent=intent,
		target_role=target_role,
		skill_gaps=skill_gaps,
	)
	return build_rag_context_from_chunks(chunks), build_rag_citations_from_chunks(chunks), metrics


def evaluate_retrieval(
	query: str,
	*,
	expected_terms: list[str] | None = None,
	expected_source_contains: list[str] | None = None,
	metadata_filters: dict[str, str] | None = None,
	top_k: int | None = None,
	intent: str | None = None,
	target_role: str | None = None,
	skill_gaps: list[str] | None = None,
) -> dict[str, Any]:
	"""Compute retrieval quality metrics for test/eval workflows.

	Significance:
		Backs manifest-based quality gates (`term_coverage`, `source_recall_at_k`).

	Used by:
		`app.api.routes.rag.rag_evaluate`, manifest scripts/tests.
	"""
	chunks = retrieve_relevant_chunks(
		query,
		top_k=top_k,
		metadata_filters=metadata_filters,
		intent=intent,
		target_role=target_role,
		skill_gaps=skill_gaps,
	)
	citations = build_rag_citations_from_chunks(chunks)
	combined = " ".join([f"{chunk.title} {chunk.text}".lower() for chunk in chunks])

	expected_terms = [term.strip().lower() for term in (expected_terms or []) if term and term.strip()]
	matched_terms = [term for term in expected_terms if term in combined]
	term_coverage = (len(matched_terms) / len(expected_terms)) if expected_terms else None

	expected_sources = [item.strip().lower() for item in (expected_source_contains or []) if item and item.strip()]
	actual_sources = [str(chunk.source).lower() for chunk in chunks]
	matched_sources = [needle for needle in expected_sources if any(needle in source for source in actual_sources)]
	source_recall_at_k = (len(matched_sources) / len(expected_sources)) if expected_sources else None

	return {
		"query": query,
		"retrieved_count": len(chunks),
		"term_coverage": term_coverage,
		"source_recall_at_k": source_recall_at_k,
		"matched_terms": matched_terms,
		"matched_sources": matched_sources,
		"results": citations,
	}


def _percentile(values: list[int], q: float) -> float:
	"""Compute percentile using nearest-rank interpolation for small telemetry samples."""
	if not values:
		return 0.0
	sorted_values = sorted(values)
	if len(sorted_values) == 1:
		return float(sorted_values[0])
	position = q * (len(sorted_values) - 1)
	lower = int(position)
	upper = min(len(sorted_values) - 1, lower + 1)
	weight = position - lower
	return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


async def get_rag_telemetry_summary(user_id: str, limit: int = 100) -> dict[str, Any]:
	"""Aggregate per-user retrieval telemetry over recent assistant turns.

	Used by:
		`app.api.routes.rag` telemetry summary endpoints.
	"""
	history = await get_user_history(user_id, limit=max(1, limit))
	entries = _extract_rag_metric_entries(history)
	return _build_rag_telemetry_aggregate(user_id, entries)


def _extract_rag_metric_entries(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Extract assistant-turn RAG telemetry entries from chat history documents."""
	entries: list[dict[str, Any]] = []
	for item in history:
		if str(item.get("role", "")).lower() != "assistant":
			continue
		rag_metrics = item.get("rag_metrics")
		if isinstance(rag_metrics, dict):
			entries.append({"metrics": rag_metrics, "timestamp": item.get("timestamp")})
	return entries


def _build_rag_telemetry_aggregate(user_id: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
	"""Build aggregate statistics from extracted telemetry entries."""

	if not entries:
		return {
			"user_id": user_id,
			"samples": 0,
			"retrieval_ms_avg": 0.0,
			"retrieval_ms_p50": 0.0,
			"retrieval_ms_p95": 0.0,
			"retrieved_count_avg": 0.0,
			"retrieved_count_p50": 0.0,
			"retrieved_count_p95": 0.0,
			"auto_filters_rate": 0.0,
			"fallback_without_filters_rate": 0.0,
			"non_empty_retrieval_rate": 0.0,
			"last_observed_at": None,
		}

	retrieval_ms_values = [int(entry["metrics"].get("retrieval_ms", 0)) for entry in entries]
	retrieved_count_values = [int(entry["metrics"].get("retrieved_count", 0)) for entry in entries]
	auto_filters_true = sum(1 for entry in entries if bool(entry["metrics"].get("auto_filters_used", False)))
	fallback_true = sum(1 for entry in entries if bool(entry["metrics"].get("fallback_without_filters", False)))
	non_empty = sum(1 for value in retrieved_count_values if value > 0)
	samples = len(entries)

	return {
		"user_id": user_id,
		"samples": samples,
		"retrieval_ms_avg": round(sum(retrieval_ms_values) / samples, 2),
		"retrieval_ms_p50": round(_percentile(retrieval_ms_values, 0.50), 2),
		"retrieval_ms_p95": round(_percentile(retrieval_ms_values, 0.95), 2),
		"retrieved_count_avg": round(sum(retrieved_count_values) / samples, 2),
		"retrieved_count_p50": round(_percentile(retrieved_count_values, 0.50), 2),
		"retrieved_count_p95": round(_percentile(retrieved_count_values, 0.95), 2),
		"auto_filters_rate": round(auto_filters_true / samples, 4),
		"fallback_without_filters_rate": round(fallback_true / samples, 4),
		"non_empty_retrieval_rate": round(non_empty / samples, 4),
		"last_observed_at": entries[-1].get("timestamp"),
	}


async def get_rag_telemetry_trends(
	user_id: str,
	*,
	windows: list[int] | None = None,
	max_limit: int | None = None,
) -> dict[str, Any]:
	"""Return windowed telemetry aggregates (for example last 10/50/100 turns) for dashboard trends."""
	requested_windows = windows or [10, 50, 100]
	resolved_windows = sorted({max(1, int(value)) for value in requested_windows})
	limit = max_limit if max_limit is not None else max(resolved_windows)
	history = await get_user_history(user_id, limit=max(1, limit))
	entries = _extract_rag_metric_entries(history)

	buckets: list[dict[str, Any]] = []
	for window in resolved_windows:
		window_entries = entries[-window:]
		aggregated = _build_rag_telemetry_aggregate(user_id, window_entries)
		aggregated["window"] = window
		buckets.append(aggregated)

	return {
		"user_id": user_id,
		"total_samples": len(entries),
		"windows": buckets,
	}


async def get_rag_telemetry_trend_series(
	user_id: str,
	*,
	windows: list[int] | None = None,
	max_limit: int | None = None,
) -> dict[str, Any]:
	"""Return chart-friendly telemetry series arrays keyed by metric name."""
	trends = await get_rag_telemetry_trends(user_id, windows=windows, max_limit=max_limit)
	buckets = trends.get("windows", [])

	labels = [f"last_{int(bucket.get('window', 0))}" for bucket in buckets]
	window_values = [int(bucket.get("window", 0)) for bucket in buckets]

	return {
		"user_id": user_id,
		"total_samples": int(trends.get("total_samples", 0)),
		"windows": window_values,
		"labels": labels,
		"samples": [int(bucket.get("samples", 0)) for bucket in buckets],
		"retrieval_ms_avg": [float(bucket.get("retrieval_ms_avg", 0.0)) for bucket in buckets],
		"retrieved_count_avg": [float(bucket.get("retrieved_count_avg", 0.0)) for bucket in buckets],
		"non_empty_retrieval_rate": [float(bucket.get("non_empty_retrieval_rate", 0.0)) for bucket in buckets],
		"auto_filters_rate": [float(bucket.get("auto_filters_rate", 0.0)) for bucket in buckets],
		"fallback_without_filters_rate": [
			float(bucket.get("fallback_without_filters_rate", 0.0)) for bucket in buckets
		],
	}


async def get_rag_telemetry_trends_combined(
	user_id: str,
	*,
	windows: list[int] | None = None,
	max_limit: int | None = None,
) -> dict[str, Any]:
	"""Return both bucket and chart-series telemetry views in a single payload."""
	trends = await get_rag_telemetry_trends(user_id, windows=windows, max_limit=max_limit)
	series = await get_rag_telemetry_trend_series(user_id, windows=windows, max_limit=max_limit)
	return {
		"user_id": user_id,
		"total_samples": int(trends.get("total_samples", 0)),
		"windows": trends.get("windows", []),
		"series": series,
	}


def infer_metadata_filters(query: str) -> dict[str, str]:
	"""Infer lightweight metadata filters from query text.

	Significance:
		Improves precision when users provide implicit intent/role hints.

	Used by:
		`_retrieve_relevant_chunks_with_metrics` auto-filter path.
	"""
	text = query.lower()
	filters: dict[str, str] = {}
	role_aliases = {
		"data scientist": "data scientist",
		"data science": "data scientist",
		"data analyst": "data analyst",
		"ml engineer": "ml engineer",
		"machine learning engineer": "ml engineer",
		"data engineer": "data engineer",
		"backend developer": "backend developer",
		"devops engineer": "devops engineer",
		"ui ux designer": "ui/ux designer",
		"ui ux": "ui/ux designer",
		"product analyst": "product analyst",
		"research scientist": "research scientist",
		"business analyst": "business analyst",
		"digital marketing specialist": "digital marketing specialist",
		"project manager": "project manager",
		"qa automation engineer": "qa automation engineer",
		"cybersecurity analyst": "cybersecurity analyst",
		"ai product manager": "ai product manager",
		"ux researcher": "ux researcher",
		"database administrator": "database administrator",
		"dba": "database administrator",
		"system administrator": "system administrator",
		"technical support specialist": "technical support specialist",
		"operations coordinator": "operations coordinator",
		"finance analyst": "finance analyst",
		"supply chain analyst": "supply chain analyst",
	}

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

	for token, normalized_role in role_aliases.items():
		if token in text:
			filters["role"] = normalized_role
			break

	return filters

