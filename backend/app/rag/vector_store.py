"""Lightweight in-memory TF-IDF vector store used by the local RAG pipeline."""

from __future__ import annotations

from typing import Sequence

from app.rag.knowledge_base import KnowledgeChunk


class InMemoryVectorStore:
	"""Simple TF-IDF backed store for local RAG retrieval."""

	def __init__(self) -> None:
		self._chunks: list[KnowledgeChunk] = []
		self._vectorizer = None
		self._matrix = None

	def set_chunks(self, chunks: Sequence[KnowledgeChunk]) -> None:
		"""Rebuild the TF-IDF index from the supplied chunks."""
		self._chunks = list(chunks)
		if not self._chunks:
			self._vectorizer = None
			self._matrix = None
			return

		# Lazy imports avoid hard failures when optional heavy deps are unavailable.
		from sklearn.feature_extraction.text import TfidfVectorizer

		corpus = [f"{chunk.title} {chunk.text}" for chunk in self._chunks]
		self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
		self._matrix = self._vectorizer.fit_transform(corpus)

	def search(self, query: str, top_k: int) -> list[tuple[float, KnowledgeChunk]]:
		"""Return top-k positively scored chunks for a query using cosine similarity."""
		if not query.strip() or not self._chunks:
			return []

		if self._vectorizer is None or self._matrix is None:
			return []

		from sklearn.metrics.pairwise import cosine_similarity

		query_vector = self._vectorizer.transform([query])
		scores = cosine_similarity(query_vector, self._matrix).flatten()

		ranked_indices = sorted(range(len(scores)), key=lambda idx: float(scores[idx]), reverse=True)
		results: list[tuple[float, KnowledgeChunk]] = []
		for idx in ranked_indices:
			score = float(scores[idx])
			if score <= 0:
				continue
			results.append((score, self._chunks[idx]))
			if len(results) >= max(1, top_k):
				break
		return results
