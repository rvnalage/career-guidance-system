"""Run RAG evaluation manifest cases and report pass/fail against quality gates."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
	sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


@dataclass
class CaseResult:
	"""Evaluation status and metrics for one manifest case."""

	case_id: str
	status: str
	term_coverage: float | None
	source_recall_at_k: float | None
	retrieved_count: int
	detail: str


def _repo_root_from_script() -> Path:
	"""Resolve repository root from backend/scripts location."""
	return Path(__file__).resolve().parents[2]


def _load_manifest(path: Path) -> dict[str, Any]:
	"""Load and parse evaluation manifest JSON."""
	with path.open("r", encoding="utf-8") as handle:
		return json.load(handle)


def _to_float(value: Any) -> float | None:
	"""Convert numeric-like values to float when present."""
	if value is None:
		return None
	try:
		return float(value)
	except (TypeError, ValueError):
		return None


def run_manifest(manifest_path: Path, top_k_override: int | None = None) -> tuple[list[CaseResult], dict[str, Any]]:
	"""Execute enabled manifest cases against /api/v1/rag/evaluate endpoint."""
	manifest = _load_manifest(manifest_path)
	defaults = manifest.get("defaults", {})
	quality_gates = defaults.get("quality_gates", {})
	term_min = _to_float(quality_gates.get("term_coverage_min")) or 0.0
	source_min = _to_float(quality_gates.get("source_recall_at_k_min")) or 0.0
	default_top_k = int(defaults.get("top_k", 4))

	results: list[CaseResult] = []
	with TestClient(app) as client:
		for case in manifest.get("cases", []):
			if not case.get("enabled", False):
				continue

			payload = {
				"query": case.get("query", ""),
				"intent": case.get("intent"),
				"target_role": case.get("target_role"),
				"expected_terms": case.get("expected_terms", []),
				"expected_source_contains": case.get("expected_source_contains", []),
				"top_k": top_k_override if top_k_override is not None else default_top_k,
			}

			response = client.post("/api/v1/rag/evaluate", json=payload)
			case_id = str(case.get("id", "unknown"))
			if response.status_code != 200:
				results.append(
					CaseResult(
						case_id=case_id,
						status="error",
						term_coverage=None,
						source_recall_at_k=None,
						retrieved_count=0,
						detail=f"HTTP {response.status_code}",
					)
				)
				continue

			body = response.json()
			term_coverage = _to_float(body.get("term_coverage"))
			source_recall_at_k = _to_float(body.get("source_recall_at_k"))
			retrieved_count = int(body.get("retrieved_count", 0))

			passes_term = term_coverage is not None and term_coverage >= term_min
			passes_source = source_recall_at_k is not None and source_recall_at_k >= source_min
			status = "pass" if passes_term and passes_source else "fail"
			detail = f"term>={term_min:.2f}, source>={source_min:.2f}"

			results.append(
				CaseResult(
					case_id=case_id,
					status=status,
					term_coverage=term_coverage,
					source_recall_at_k=source_recall_at_k,
					retrieved_count=retrieved_count,
					detail=detail,
				)
			)

	return results, {"term_coverage_min": term_min, "source_recall_at_k_min": source_min}


def _format_metric(value: float | None) -> str:
	"""Render optional metric values in report output."""
	return "n/a" if value is None else f"{value:.3f}"


def main() -> int:
	"""CLI entrypoint for running manifest evaluations."""
	root = _repo_root_from_script()
	default_manifest = root / "rag" / "knowledge" / "eval_manifest.json"

	parser = argparse.ArgumentParser(description="Run RAG evaluation manifest cases")
	parser.add_argument("--manifest", type=Path, default=default_manifest, help="Path to eval_manifest.json")
	parser.add_argument("--top-k", type=int, default=None, help="Override top_k for all enabled cases")
	args = parser.parse_args()

	manifest_path = args.manifest if args.manifest.is_absolute() else (Path.cwd() / args.manifest).resolve()
	if not manifest_path.exists():
		print(f"Manifest file not found: {manifest_path}")
		return 2

	results, gates = run_manifest(manifest_path, top_k_override=args.top_k)
	if not results:
		print("No enabled cases found in manifest.")
		return 0

	print(f"Quality gates: term_coverage>={gates['term_coverage_min']:.2f}, source_recall_at_k>={gates['source_recall_at_k_min']:.2f}")
	print("-")
	for item in results:
		print(
			f"{item.status.upper():5} | {item.case_id:40} | "
			f"term={_format_metric(item.term_coverage)} | "
			f"source={_format_metric(item.source_recall_at_k)} | "
			f"retrieved={item.retrieved_count}"
		)

	failed = [item for item in results if item.status != "pass"]
	print("-")
	print(f"Summary: {len(results) - len(failed)} passed, {len(failed)} failed, {len(results)} total enabled cases")
	return 1 if failed else 0


if __name__ == "__main__":
	raise SystemExit(main())
