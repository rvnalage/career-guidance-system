"""Manifest-level tests for RAG retrieval quality checks."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.services.rag_service import evaluate_retrieval


MANIFEST_PATH = Path(__file__).resolve().parents[2] / "rag" / "knowledge" / "eval_manifest.json"


REQUIRED_CASE_KEYS = {
	"id",
	"enabled",
	"query",
	"intent",
	"target_role",
	"expected_terms",
	"expected_source_contains",
}


def _load_manifest() -> dict:
	"""Read eval manifest JSON from repository knowledge folder."""
	with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
		return json.load(handle)


def test_rag_eval_manifest_has_valid_shape():
	manifest = _load_manifest()
	assert isinstance(manifest, dict)
	assert manifest.get("version")
	assert isinstance(manifest.get("defaults"), dict)
	assert isinstance(manifest.get("cases"), list)
	assert len(manifest["cases"]) >= 1

	defaults = manifest["defaults"]
	assert int(defaults.get("top_k", 0)) >= 1
	gates = defaults.get("quality_gates", {})
	assert 0 <= float(gates.get("term_coverage_min", 0.0)) <= 1
	assert 0 <= float(gates.get("source_recall_at_k_min", 0.0)) <= 1

	for case in manifest["cases"]:
		missing = REQUIRED_CASE_KEYS.difference(case.keys())
		assert not missing, f"missing case keys: {sorted(missing)}"
		assert isinstance(case["id"], str) and case["id"].strip()
		assert isinstance(case["enabled"], bool)
		assert isinstance(case["query"], str) and len(case["query"].strip()) >= 2
		assert isinstance(case["intent"], str) and case["intent"].strip()
		assert isinstance(case["target_role"], str) and case["target_role"].strip()
		assert isinstance(case["expected_terms"], list)
		assert isinstance(case["expected_source_contains"], list)


@pytest.mark.skipif(
	os.getenv("RAG_MANIFEST_ENFORCE", "0") != "1",
	reason="Set RAG_MANIFEST_ENFORCE=1 to enforce enabled-case quality gates.",
)
def test_rag_eval_manifest_enabled_cases_meet_quality_gates():
	manifest = _load_manifest()
	defaults = manifest.get("defaults", {})
	top_k = int(defaults.get("top_k", 4))
	gates = defaults.get("quality_gates", {})
	term_min = float(gates.get("term_coverage_min", 0.6))
	source_min = float(gates.get("source_recall_at_k_min", 0.7))

	enabled_cases = [case for case in manifest.get("cases", []) if case.get("enabled", False)]
	assert enabled_cases, "No enabled cases found in eval manifest"

	failures: list[str] = []
	for case in enabled_cases:
		result = evaluate_retrieval(
			case["query"],
			expected_terms=case.get("expected_terms", []),
			expected_source_contains=case.get("expected_source_contains", []),
			top_k=top_k,
			intent=case.get("intent"),
			target_role=case.get("target_role"),
		)
		term_coverage = result.get("term_coverage")
		source_recall_at_k = result.get("source_recall_at_k")

		term_ok = isinstance(term_coverage, (int, float)) and float(term_coverage) >= term_min
		source_ok = isinstance(source_recall_at_k, (int, float)) and float(source_recall_at_k) >= source_min
		if not (term_ok and source_ok):
			failures.append(
				f"{case['id']}: term={term_coverage}, source={source_recall_at_k}, "
				f"required term>={term_min}, source>={source_min}"
			)

	assert not failures, "\n" + "\n".join(failures)
