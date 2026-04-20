"""Lightweight in-memory TF-IDF vector store used by the local RAG pipeline."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from __future__ import annotations

import logging
from typing import Sequence

from app.rag.knowledge_base import KnowledgeChunk


logger = logging.getLogger(__name__)


class InMemoryVectorStore:
	"""Simple TF-IDF backed store for local RAG retrieval."""

	def __init__(self) -> None:
		self._chunks: list[KnowledgeChunk] = []
		self._vectorizer = None
		self._matrix = None
		self._char_vectorizer = None
		self._char_matrix = None
		self._vector_search_enabled = True

	def set_chunks(self, chunks: Sequence[KnowledgeChunk]) -> None:
		"""Rebuild the TF-IDF index from the supplied chunks."""
		self._chunks = list(chunks)
		if not self._chunks:
			self._vectorizer = None
			self._matrix = None
			self._char_vectorizer = None
			self._char_matrix = None
			return

		if not self._vector_search_enabled:
			self._vectorizer = None
			self._matrix = None
			self._char_vectorizer = None
			self._char_matrix = None
			return

		try:
			from sklearn.feature_extraction.text import TfidfVectorizer
		except Exception as exc:
			logger.warning("Disabling vector search because sklearn import failed: %s", exc)
			self._vector_search_enabled = False
			self._vectorizer = None
			self._matrix = None
			self._char_vectorizer = None
			self._char_matrix = None
			return

		corpus = [f"{chunk.title} {chunk.text}" for chunk in self._chunks]
		try:
			self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
			self._matrix = self._vectorizer.fit_transform(corpus)
			# Char n-gram index improves robustness to tokenization mismatch and phrasing variation.
			self._char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
			self._char_matrix = self._char_vectorizer.fit_transform(corpus)
		except Exception as exc:
			logger.warning("Disabling vector search because TF-IDF index build failed: %s", exc)
			self._vector_search_enabled = False
			self._vectorizer = None
			self._matrix = None
			self._char_vectorizer = None
			self._char_matrix = None

	def search(self, query: str, top_k: int) -> list[tuple[float, KnowledgeChunk]]:
		"""Return top-k positively scored chunks for a query using cosine similarity."""
		if not query.strip() or not self._chunks:
			return []

		if self._vectorizer is None or self._matrix is None:
			return []

		from sklearn.metrics.pairwise import cosine_similarity

		query_vector = self._vectorizer.transform([query])
		word_scores = cosine_similarity(query_vector, self._matrix).flatten()
		if self._char_vectorizer is not None and self._char_matrix is not None:
			char_query_vector = self._char_vectorizer.transform([query])
			char_scores = cosine_similarity(char_query_vector, self._char_matrix).flatten()
			scores = (0.75 * word_scores) + (0.25 * char_scores)
		else:
			scores = word_scores

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

