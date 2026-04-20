"""Retriever that combines vector search, lexical overlap, and metadata-aware reranking."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from __future__ import annotations

import re

from app.rag.knowledge_base import KnowledgeChunk
from app.rag.vector_store import InMemoryVectorStore


def _tokenize(value: str) -> set[str]:
	"""Tokenize free text into lowercase alphanumeric terms for overlap scoring."""
	return set(re.findall(r"[a-z0-9]+", value.lower()))


def _metadata_score(query_tokens: set[str], chunk: KnowledgeChunk) -> float:
	"""Compute a lightweight bonus when query tokens overlap with chunk metadata values."""
	if not chunk.metadata:
		return 0.0
	text = " ".join(chunk.metadata.values())
	meta_tokens = _tokenize(text)
	if not meta_tokens:
		return 0.0
	overlap = len(query_tokens.intersection(meta_tokens))
	return overlap * 0.15


class Retriever:
	"""Thin retrieval orchestrator over the in-memory vector store."""
	def __init__(self, store: InMemoryVectorStore) -> None:
		self.store = store

	def retrieve(
		self,
		query: str,
		top_k: int,
		fallback_chunks: list[KnowledgeChunk],
		metadata_filters: dict[str, str] | None = None,
		candidate_pool_size: int = 20,
	) -> list[KnowledgeChunk]:
		"""Return the best matching chunks using vector retrieval plus deterministic reranking."""
		query_tokens = _tokenize(query)
		if not query_tokens:
			return []

		pool = max(candidate_pool_size, top_k)
		candidates = self.store.search(query=query, top_k=pool)
		if candidates:
			reranked: list[tuple[float, KnowledgeChunk]] = []
			for vector_score, chunk in candidates:
				if metadata_filters and not _passes_metadata_filters(chunk, metadata_filters):
					continue

				chunk_tokens = _tokenize(f"{chunk.title} {chunk.text}")
				lexical_overlap = len(query_tokens.intersection(chunk_tokens)) * 0.1
				score = vector_score + lexical_overlap + _metadata_score(query_tokens, chunk)
				reranked.append((score, chunk))

			reranked.sort(key=lambda item: item[0], reverse=True)
			return [item[1] for item in reranked[: max(1, top_k)]]

		# Deterministic fallback keeps behavior stable when vector scoring yields no match.
		scored: list[tuple[int, KnowledgeChunk]] = []
		for chunk in fallback_chunks:
			if metadata_filters and not _passes_metadata_filters(chunk, metadata_filters):
				continue

			chunk_tokens = _tokenize(f"{chunk.title} {chunk.text}")
			overlap = len(query_tokens.intersection(chunk_tokens))
			if overlap > 0:
				scored.append((overlap, chunk))

		scored.sort(key=lambda item: item[0], reverse=True)
		return [item[1] for item in scored[: max(1, top_k)]]


def _passes_metadata_filters(chunk: KnowledgeChunk, metadata_filters: dict[str, str]) -> bool:
	"""Check whether a chunk satisfies exact-match metadata filters."""
	if not metadata_filters:
		return True
	for key, expected_value in metadata_filters.items():
		actual = chunk.metadata.get(key, "").strip().lower()
		if actual != expected_value.strip().lower():
			return False
	return True

