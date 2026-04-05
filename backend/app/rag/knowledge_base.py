"""Knowledge-base construction and document chunk ingestion helpers for RAG."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

from app.utils.constants import CAREER_PATHS


@dataclass(frozen=True)
class KnowledgeChunk:
	"""Single retrievable knowledge unit with source and metadata for reranking and citation."""
	title: str
	text: str
	source: str
	source_type: str = "internal"
	metadata: dict[str, str] = field(default_factory=dict)


EXTRA_KNOWLEDGE: list[KnowledgeChunk] = [
	KnowledgeChunk(
		title="Interview Preparation",
		text=(
			"Strong interview performance usually needs role-specific question practice, "
			"project storytelling using impact metrics, and revision checklists."
		),
		source="internal_guide/interview",
		metadata={"topic": "interview", "level": "general"},
	),
	KnowledgeChunk(
		title="Learning Roadmap",
		text=(
			"Students progress faster with phased plans: foundations, applied projects, "
			"portfolio publication, and mock interviews."
		),
		source="internal_guide/learning_path",
		metadata={"topic": "learning", "level": "general"},
	),
	KnowledgeChunk(
		title="Job Search Strategy",
		text=(
			"Job matching should combine skills fit, interests fit, and education fit, "
			"then refine using feedback from prior recommendations."
		),
		source="internal_guide/job_matching",
		metadata={"topic": "job_search", "level": "general"},
	),
]


def build_base_corpus() -> list[KnowledgeChunk]:
	"""Build the built-in knowledge corpus from static career definitions and curated extras."""
	corpus: list[KnowledgeChunk] = []
	for path in CAREER_PATHS:
		text = (
			f"Role {path['role']}. "
			f"Required skills: {', '.join(path['required_skills'])}. "
			f"Related interests: {', '.join(path['related_interests'])}. "
			f"Minimum education: {path['min_education']}. "
			f"Description: {path['description']}"
		)
		corpus.append(
			KnowledgeChunk(
				title=f"Role Guide: {path['role']}",
				text=text,
				source="app.utils.constants.CAREER_PATHS",
				metadata={
					"topic": "career_path",
					"role": path["role"].lower(),
					"min_education": path["min_education"].lower(),
				},
			)
		)
	return corpus + EXTRA_KNOWLEDGE


def default_one_note_extract_path() -> Path:
	"""Resolve the default directory containing external text documents for ingestion."""
	backend_root = Path(__file__).resolve().parents[3]  # Go up to project root
	candidates = [
		backend_root / "rag" / "knowledge",  # New location in career-guidance-system
		backend_root / "one_note_extract",   # Fallback to old location
	]
	for candidate in candidates:
		if candidate.exists() and candidate.is_dir():
			return candidate
	return candidates[0]


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 120) -> list[str]:
	"""Split long text into overlapping chunks suitable for simple local retrieval."""
	clean = " ".join(text.split())
	if not clean:
		return []
	if overlap < 0:
		overlap = 0
	if overlap >= chunk_size:
		overlap = max(0, chunk_size // 4)

	chunks: list[str] = []
	start = 0
	step = max(1, chunk_size - overlap)
	while start < len(clean):
		end = min(len(clean), start + chunk_size)
		chunks.append(clean[start:end])
		if end >= len(clean):
			break
		start += step
	return chunks


def load_document_chunks(directory_path: str | None = None) -> dict[str, Any]:
	"""Load text files from disk, filter noisy chunks, and return ingest-ready knowledge chunks."""
	target_path = Path(directory_path).expanduser() if directory_path else default_one_note_extract_path()
	if not target_path.exists() or not target_path.is_dir():
		return {
			"target_path": str(target_path),
			"ingested_files": [],
			"ingested_chunks": [],
			"skipped_files": [],
		}

	ingested_files: list[str] = []
	skipped_files: list[str] = []
	ingested_chunks: list[KnowledgeChunk] = []
	seen_chunk_fingerprints: set[str] = set()
	skipped_noisy_chunks = 0
	skipped_duplicate_chunks = 0

	for file_path in sorted(target_path.rglob("*")):
		if not file_path.is_file():
			continue

		if file_path.suffix.lower() != ".txt":
			skipped_files.append(str(file_path))
			continue

		text = file_path.read_text(encoding="utf-8", errors="ignore")
		chunks = chunk_text(text)
		if not chunks:
			continue

		ingested_files.append(str(file_path))
		for index, chunk in enumerate(chunks, start=1):
			chunk_text_normalized = " ".join(chunk.lower().split())
			if len(chunk_text_normalized) < 80:
				skipped_noisy_chunks += 1
				continue

			alnum_ratio = _alnum_ratio(chunk_text_normalized)
			if alnum_ratio < 0.65:
				skipped_noisy_chunks += 1
				continue

			fingerprint = _fingerprint(chunk_text_normalized)
			if fingerprint in seen_chunk_fingerprints:
				skipped_duplicate_chunks += 1
				continue
			seen_chunk_fingerprints.add(fingerprint)

			ingested_chunks.append(
				KnowledgeChunk(
					title=f"Document Chunk {index}: {file_path.name}",
					text=chunk,
					source=str(file_path),
					source_type="document",
					metadata={
						"topic": "document",
						"file_name": file_path.name.lower(),
						"chunk_index": str(index),
					},
				)
			)

	return {
		"target_path": str(target_path),
		"ingested_files": ingested_files,
		"ingested_chunks": ingested_chunks,
		"skipped_files": skipped_files,
		"skipped_duplicate_chunks": skipped_duplicate_chunks,
		"skipped_noisy_chunks": skipped_noisy_chunks,
	}


def _alnum_ratio(text: str) -> float:
	"""Estimate text cleanliness by measuring the share of alphanumeric or space characters."""
	if not text:
		return 0.0
	alnum_count = sum(char.isalnum() or char.isspace() for char in text)
	return alnum_count / len(text)


def _fingerprint(text: str) -> str:
	"""Generate a compact normalized token fingerprint for duplicate-chunk detection."""
	# Compact near-duplicate detector using first N normalized tokens.
	tokens = re.findall(r"[a-z0-9]+", text)
	return " ".join(tokens[:80])
