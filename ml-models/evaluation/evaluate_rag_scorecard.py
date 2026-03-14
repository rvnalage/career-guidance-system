from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

import requests


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def _keyword_hit(snippets: str, expected_keywords: list[str]) -> bool:
    haystack = snippets.lower()
    return any(keyword.lower() in haystack for keyword in expected_keywords)


def evaluate(base_api_url: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    query_rows: list[dict[str, Any]] = []
    source_hits: list[int] = []
    topic_hits: list[int] = []
    keyword_hits: list[int] = []

    for row in rows:
        query = str(row.get("query", "")).strip()
        if not query:
            continue

        response = requests.get(
            f"{base_api_url.rstrip('/')}/rag/search",
            params={"query": query},
            timeout=20,
        )
        response.raise_for_status()
        results = response.json().get("results", [])

        result_sources = {str(item.get("source", "")) for item in results}
        result_topics = {str(item.get("metadata", {}).get("topic", "")) for item in results}
        snippets = " ".join(str(item.get("snippet", "")) for item in results)

        expected_sources = set(str(v) for v in row.get("expected_sources", []))
        expected_topics = set(str(v) for v in row.get("expected_topics", []))
        expected_keywords = [str(v) for v in row.get("expected_keywords", [])]

        source_ok = int(bool(expected_sources.intersection(result_sources)))
        topic_ok = int(bool(expected_topics.intersection(result_topics)))
        keyword_ok = int(_keyword_hit(snippets, expected_keywords)) if expected_keywords else 1

        source_hits.append(source_ok)
        topic_hits.append(topic_ok)
        keyword_hits.append(keyword_ok)

        query_rows.append(
            {
                "query": query,
                "result_count": len(results),
                "source_hit": source_ok,
                "topic_hit": topic_ok,
                "keyword_hit": keyword_ok,
                "top_result": results[0]["title"] if results else None,
            }
        )

    return {
        "summary": {
            "queries": len(query_rows),
            "source_hit_rate": round(mean(source_hits), 3) if source_hits else 0.0,
            "topic_hit_rate": round(mean(topic_hits), 3) if topic_hits else 0.0,
            "keyword_hit_rate": round(mean(keyword_hits), 3) if keyword_hits else 0.0,
        },
        "rows": query_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval scorecard metrics")
    parser.add_argument("--api-url", default="http://localhost:8000/api/v1")
    parser.add_argument(
        "--dataset",
        default="ml-models/datasets/rag_eval_dataset_template.jsonl",
        help="JSONL file with query + expected_sources/topics/keywords",
    )
    parser.add_argument(
        "--output",
        default="ml-models/evaluation/rag_scorecard_results.json",
        help="Where to save scorecard output JSON",
    )
    args = parser.parse_args()

    dataset = _load_dataset(Path(args.dataset))
    report = evaluate(args.api_url, dataset)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    print(json.dumps(report["summary"], indent=2, ensure_ascii=True))
    print(f"Saved scorecard: {output_path}")


if __name__ == "__main__":
    main()
