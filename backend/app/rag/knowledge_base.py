"""Knowledge-base construction and document chunk ingestion helpers for RAG."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


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
	"""Split text into sentence-aware overlapping chunks for better semantic coherence."""
	if not text or not text.strip():
		return []
	if overlap < 0:
		overlap = 0
	if overlap >= chunk_size:
		overlap = max(0, chunk_size // 4)

	paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
	if not paragraphs:
		paragraphs = [text.strip()]

	sentences: list[str] = []
	for paragraph in paragraphs:
		normalized = " ".join(paragraph.split())
		parts = re.split(r"(?<=[.!?])\s+", normalized)
		for part in parts:
			sentence = part.strip()
			if sentence:
				sentences.append(sentence)

	if not sentences:
		clean = " ".join(text.split())
		if not clean:
			return []
		sentences = [clean]

	chunks: list[str] = []
	current_sentences: list[str] = []
	current_len = 0
	for sentence in sentences:
		sentence_len = len(sentence)
		if current_sentences and current_len + 1 + sentence_len > chunk_size:
			chunk = " ".join(current_sentences).strip()
			if chunk:
				chunks.append(chunk)
			if overlap > 0:
				overlap_sentences: list[str] = []
				overlap_len = 0
				for candidate in reversed(current_sentences):
					candidate_len = len(candidate) + (1 if overlap_sentences else 0)
					if overlap_len + candidate_len > overlap:
						break
					overlap_sentences.insert(0, candidate)
					overlap_len += candidate_len
				current_sentences = overlap_sentences
				current_len = len(" ".join(current_sentences)) if current_sentences else 0
			else:
				current_sentences = []
				current_len = 0

		if current_sentences:
			current_sentences.append(sentence)
			current_len = len(" ".join(current_sentences))
		else:
			current_sentences = [sentence]
			current_len = sentence_len

	if current_sentences:
		chunk = " ".join(current_sentences).strip()
		if chunk:
			chunks.append(chunk)
	return chunks


def _infer_topic_from_text(text: str) -> str:
	"""Infer a coarse topic label from text for retrieval metadata filtering."""
	value = text.lower()
	if any(token in value for token in ["interview", "mock", "technical round", "hr round"]):
		return "interview"
	if any(token in value for token in ["roadmap", "learning", "upskill", "course", "study"]):
		return "learning"
	if any(token in value for token in ["network", "outreach", "referral", "linkedin"]):
		return "networking"
	if any(token in value for token in ["job", "application", "resume", "portfolio"]):
		return "job_search"
	return "document"


def _infer_role_from_name(file_name: str) -> str | None:
	"""Infer role hint from file names to support role-aware filtering and reranking."""
	name = file_name.lower().replace("-", "_").replace(" ", "_")
	role_aliases = {
		"data_scientist": "data scientist",
		"data_science": "data scientist",
		"data_analyst": "data analyst",
		"data_analysis": "data analyst",
		"ml_engineer": "ml engineer",
		"machine_learning_engineer": "ml engineer",
		"data_engineer": "data engineer",
		"backend_developer": "backend developer",
		"devops_engineer": "devops engineer",
		"ui_ux": "ui/ux designer",
		"product_analyst": "product analyst",
		"research_track": "research scientist",
		"business_analyst": "business analyst",
		"digital_marketing": "digital marketing specialist",
		"project_manager": "project manager",
		"automation_testing": "qa automation engineer",
		"cybersecurity": "cybersecurity analyst",
		"ai_product_manager": "ai product manager",
		"ux_researcher": "ux researcher",
		"database_administrator": "database administrator",
		"system_administrator": "system administrator",
		"technical_support": "technical support specialist",
		"operations_coordinator": "operations coordinator",
		"finance_analyst": "finance analyst",
		"supply_chain_analyst": "supply chain analyst",
	}
	for token, role in role_aliases.items():
		if token in name:
			return role
	return None


def _infer_role_from_text(text: str) -> str | None:
	"""Infer role hint from chunk content when filenames are generic (for example interview docs)."""
	value = " ".join(text.lower().split())
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
		"system administrator": "system administrator",
		"technical support specialist": "technical support specialist",
		"operations coordinator": "operations coordinator",
		"finance analyst": "finance analyst",
		"supply chain analyst": "supply chain analyst",
	}
	for token, role in role_aliases.items():
		if token in value:
			return role
	return None


def _infer_min_education(text: str) -> str | None:
	"""Infer coarse minimum education metadata when explicit level terms appear."""
	lower = text.lower()
	if any(token in lower for token in ["phd", "doctorate"]):
		return "phd"
	if any(token in lower for token in ["master", "mtech", "ms"]):
		return "master"
	if any(token in lower for token in ["bachelor", "btech", "undergraduate"]):
		return "bachelor"
	return None


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

			role_hint = _infer_role_from_name(file_path.name) or _infer_role_from_text(f"{file_path.name} {chunk}")
			topic_hint = _infer_topic_from_text(f"{file_path.name} {chunk}")
			min_education_hint = _infer_min_education(f"{file_path.name} {chunk}")
			metadata: dict[str, str] = {
				"topic": topic_hint,
				"file_name": file_path.name.lower(),
				"chunk_index": str(index),
			}
			if role_hint:
				metadata["role"] = role_hint
			if min_education_hint:
				metadata["min_education"] = min_education_hint

			ingested_chunks.append(
				KnowledgeChunk(
					title=f"Document Chunk {index}: {file_path.name}",
					text=chunk,
					source=str(file_path),
					source_type="document",
					metadata=metadata,
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

