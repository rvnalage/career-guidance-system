from pydantic import BaseModel, Field


class RagIngestRequest(BaseModel):
	directory_path: str | None = None


class RagCitation(BaseModel):
	title: str
	source: str
	source_type: str
	snippet: str


class RagSearchResponse(BaseModel):
	query: str
	results: list[RagCitation] = Field(default_factory=list)


class RagStatusResponse(BaseModel):
	enabled: bool
	top_k: int
	base_chunks: int
	document_chunks: int
	total_chunks: int
	last_ingested_at: str | None = None
	ingested_files: list[str] = Field(default_factory=list)


class RagIngestResponse(BaseModel):
	target_path: str
	ingested_files: list[str] = Field(default_factory=list)
	ingested_chunks: int
	skipped_files: list[str] = Field(default_factory=list)
