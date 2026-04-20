"""Pydantic schemas for RAG ingestion, search, status, and citation responses."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


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
	total_sources: int = 0
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


class RagEvaluateRequest(BaseModel):
	"""Payload for evaluating retrieval quality against expected terms/sources."""
	query: str = Field(min_length=2)
	top_k: int | None = Field(default=None, ge=1, le=25)
	expected_terms: list[str] = Field(default_factory=list)
	expected_source_contains: list[str] = Field(default_factory=list)
	metadata_filters: dict[str, str] | None = None
	intent: str | None = None
	target_role: str | None = None
	skill_gaps: list[str] = Field(default_factory=list)


class RagEvaluateResponse(BaseModel):
	"""Retrieval quality metrics and matched citations for evaluation runs."""
	query: str
	retrieved_count: int
	term_coverage: float | None = None
	source_recall_at_k: float | None = None
	matched_terms: list[str] = Field(default_factory=list)
	matched_sources: list[str] = Field(default_factory=list)
	results: list[RagCitation] = Field(default_factory=list)


class RagTelemetrySummaryResponse(BaseModel):
	"""Aggregated retrieval telemetry over recent assistant messages for a user."""
	user_id: str
	samples: int
	retrieval_ms_avg: float
	retrieval_ms_p50: float
	retrieval_ms_p95: float
	retrieved_count_avg: float
	retrieved_count_p50: float
	retrieved_count_p95: float
	auto_filters_rate: float
	fallback_without_filters_rate: float
	non_empty_retrieval_rate: float
	last_observed_at: str | None = None


class RagTelemetryWindow(BaseModel):
	"""Telemetry aggregate for one trailing-message window."""
	window: int
	user_id: str
	samples: int
	retrieval_ms_avg: float
	retrieval_ms_p50: float
	retrieval_ms_p95: float
	retrieved_count_avg: float
	retrieved_count_p50: float
	retrieved_count_p95: float
	auto_filters_rate: float
	fallback_without_filters_rate: float
	non_empty_retrieval_rate: float
	last_observed_at: str | None = None


class RagTelemetryTrendsResponse(BaseModel):
	"""Windowed telemetry aggregates suitable for dashboard trend cards/charts."""
	user_id: str
	total_samples: int
	windows: list[RagTelemetryWindow] = Field(default_factory=list)


class RagTelemetryTrendSeriesResponse(BaseModel):
	"""Frontend-ready trend payload with aligned labels and metric arrays."""
	user_id: str
	total_samples: int
	windows: list[int] = Field(default_factory=list)
	labels: list[str] = Field(default_factory=list)
	samples: list[int] = Field(default_factory=list)
	retrieval_ms_avg: list[float] = Field(default_factory=list)
	retrieved_count_avg: list[float] = Field(default_factory=list)
	non_empty_retrieval_rate: list[float] = Field(default_factory=list)
	auto_filters_rate: list[float] = Field(default_factory=list)
	fallback_without_filters_rate: list[float] = Field(default_factory=list)


class RagTelemetryCombinedResponse(BaseModel):
	"""Combined telemetry payload containing bucket windows and aligned chart series."""
	user_id: str
	total_samples: int
	windows: list[RagTelemetryWindow] = Field(default_factory=list)
	series: RagTelemetryTrendSeriesResponse

