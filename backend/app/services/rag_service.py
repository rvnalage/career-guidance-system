from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.utils.constants import CAREER_PATHS


@dataclass(frozen=True)
class KnowledgeChunk:
	title: str
	text: str
	source: str
	source_type: str = "internal"


EXTRA_KNOWLEDGE = [
	KnowledgeChunk(
		title="Interview Preparation",
		text=(
			"Strong interview performance usually needs role-specific question practice, "
			"project storytelling using impact metrics, and revision checklists."
		),
		source="internal_guide/interview",
		source_type="internal",
	),
	KnowledgeChunk(
		title="Learning Roadmap",
		text=(
			"Students progress faster with phased plans: foundations, applied projects, "
			"portfolio publication, and mock interviews."
		),
		source="internal_guide/learning_path",
		source_type="internal",
	),
	KnowledgeChunk(
		title="Job Search Strategy",
		text=(
			"Job matching should combine skills fit, interests fit, and education fit, "
			"then refine using feedback from prior recommendations."
		),
		source="internal_guide/job_matching",
		source_type="internal",
	),
]


def _tokenize(value: str) -> set[str]:
	return set(re.findall(r"[a-z0-9]+", value.lower()))


def _build_corpus() -> list[KnowledgeChunk]:
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
				source_type="internal",
			)
		)
	return corpus + EXTRA_KNOWLEDGE


BASE_CORPUS = _build_corpus()
DOC_CORPUS: list[KnowledgeChunk] = []
INGESTION_META = {
	"last_ingested_at": None,
	"ingested_files": [],
}


def _chunk_text(text: str, chunk_size: int = 900) -> list[str]:
	clean = " ".join(text.split())
	if not clean:
		return []
	chunks: list[str] = []
	start = 0
	while start < len(clean):
		end = min(len(clean), start + chunk_size)
		chunks.append(clean[start:end])
		start = end
	return chunks


def _read_text_file(file_path: Path) -> str:
	return file_path.read_text(encoding="utf-8", errors="ignore")


def _default_one_note_extract_path() -> Path:
	backend_root = Path(__file__).resolve().parents[2]
	candidates = [
		backend_root.parent / "one_note_extract",
		backend_root.parent.parent / "one_note_extract",
	]
	for candidate in candidates:
		if candidate.exists() and candidate.is_dir():
			return candidate
	return candidates[0]


def ingest_directory(directory_path: str | None = None) -> dict[str, Any]:
	target_path = Path(directory_path).expanduser() if directory_path else _default_one_note_extract_path()
	if not target_path.exists() or not target_path.is_dir():
		return {
			"ingested_files": [],
			"ingested_chunks": 0,
			"skipped_files": [],
			"target_path": str(target_path),
		}

	DOC_CORPUS.clear()
	ingested_files: list[str] = []
	skipped_files: list[str] = []

	for file_path in sorted(target_path.rglob("*")):
		if not file_path.is_file():
			continue
		if file_path.suffix.lower() != ".txt":
			skipped_files.append(str(file_path))
			continue

		text = _read_text_file(file_path)
		chunks = _chunk_text(text)
		if not chunks:
			continue

		ingested_files.append(str(file_path))
		for index, chunk in enumerate(chunks, start=1):
			DOC_CORPUS.append(
				KnowledgeChunk(
					title=f"Document Chunk {index}: {file_path.name}",
					text=chunk,
					source=str(file_path),
					source_type="document",
				)
			)

	INGESTION_META["last_ingested_at"] = datetime.now(timezone.utc).isoformat()
	INGESTION_META["ingested_files"] = ingested_files

	return {
		"ingested_files": ingested_files,
		"ingested_chunks": len(DOC_CORPUS),
		"skipped_files": skipped_files,
		"target_path": str(target_path),
	}


def get_rag_status() -> dict[str, Any]:
	return {
		"enabled": settings.rag_enabled,
		"top_k": settings.rag_top_k,
		"base_chunks": len(BASE_CORPUS),
		"document_chunks": len(DOC_CORPUS),
		"total_chunks": len(BASE_CORPUS) + len(DOC_CORPUS),
		"last_ingested_at": INGESTION_META.get("last_ingested_at"),
		"ingested_files": INGESTION_META.get("ingested_files", []),
	}


def _active_corpus() -> list[KnowledgeChunk]:
	return BASE_CORPUS + DOC_CORPUS


def retrieve_relevant_chunks(query: str, top_k: int | None = None) -> list[KnowledgeChunk]:
	if not settings.rag_enabled:
		return []

	query_tokens = _tokenize(query)
	if not query_tokens:
		return []

	scored: list[tuple[int, KnowledgeChunk]] = []
	for chunk in _active_corpus():
		chunk_tokens = _tokenize(f"{chunk.title} {chunk.text}")
		overlap = len(query_tokens.intersection(chunk_tokens))
		if overlap > 0:
			scored.append((overlap, chunk))

	scored.sort(key=lambda item: item[0], reverse=True)
	limit = top_k if top_k is not None else settings.rag_top_k
	return [item[1] for item in scored[: max(1, limit)]]


def build_rag_context(query: str) -> str:
	chunks = retrieve_relevant_chunks(query)
	if not chunks:
		return ""
	lines = [f"- {chunk.title}: {chunk.text}" for chunk in chunks]
	return "\n".join(lines)


def get_rag_citations(query: str) -> list[dict[str, str]]:
	chunks = retrieve_relevant_chunks(query)
	citations: list[dict[str, str]] = []
	for chunk in chunks:
		citations.append(
			{
				"title": chunk.title,
				"source": chunk.source,
				"source_type": chunk.source_type,
				"snippet": chunk.text[:240],
			}
		)
	return citations
