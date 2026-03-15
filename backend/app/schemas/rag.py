"""Pydantic schemas for RAG ingestion, search, status, and citation responses."""

from pydantic import BaseModel, Field


class RagIngestRequest(BaseModel):
	"""Payload describing an optional directory to ingest into the knowledge base."""
	directory_path: str | None = None


class RagCitation(BaseModel):
	"""Single citation item returned from RAG retrieval."""
	title: str
	source: str
	source_type: str
	snippet: str
	metadata: dict[str, str] = Field(default_factory=dict)


class RagSearchResponse(BaseModel):
	"""Envelope for RAG search results."""
	query: str
	results: list[RagCitation] = Field(default_factory=list)


class RagStatusResponse(BaseModel):
	"""Current status snapshot of the RAG pipeline and ingested corpus."""
	enabled: bool
	top_k: int
	candidate_pool_size: int
	base_chunks: int
	document_chunks: int
	total_chunks: int
	last_ingested_at: str | None = None
	ingested_files: list[str] = Field(default_factory=list)
	skipped_noisy_chunks: int = 0
	skipped_duplicate_chunks: int = 0


class RagIngestResponse(BaseModel):
	"""Result summary returned after a directory ingestion operation."""
	target_path: str
	ingested_files: list[str] = Field(default_factory=list)
	ingested_chunks: int
	skipped_files: list[str] = Field(default_factory=list)
	skipped_noisy_chunks: int = 0
	skipped_duplicate_chunks: int = 0
