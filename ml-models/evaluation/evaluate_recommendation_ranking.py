"""Offline evaluator for recommendation ranking quality.

Expected input JSONL rows:
{
  "relevant_roles": ["Machine Learning Engineer", "Data Analyst"],
  "predicted_roles": ["Data Analyst", "Backend Developer", ...]
}
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _dcg(relevance: list[int], k: int) -> float:
	score = 0.0
	for i, rel in enumerate(relevance[:k], start=1):
		score += (2**rel - 1) / math.log2(i + 1)
	return score


def _recall_at_k(relevant: set[str], predicted: list[str], k: int) -> float:
	if not relevant:
		return 0.0
	hits = len(relevant.intersection(predicted[:k]))
	return hits / len(relevant)


def _average_precision_at_k(relevant: set[str], predicted: list[str], k: int) -> float:
	if not relevant:
		return 0.0
	hit_count = 0
	precision_sum = 0.0
	for i, role in enumerate(predicted[:k], start=1):
		if role in relevant:
			hit_count += 1
			precision_sum += hit_count / i
	return precision_sum / min(len(relevant), k)


def _ndcg_at_k(relevant: set[str], predicted: list[str], k: int) -> float:
	pred_rel = [1 if role in relevant else 0 for role in predicted[:k]]
	ideal_rel = sorted(pred_rel, reverse=True)
	idcg = _dcg(ideal_rel, k)
	if idcg == 0:
		return 0.0
	return _dcg(pred_rel, k) / idcg


def parse_args() -> argparse.Namespace:
	repo_root = Path(__file__).resolve().parents[2]
	parser = argparse.ArgumentParser(description="Evaluate recommendation ranking")
	parser.add_argument(
		"--dataset",
		type=Path,
		default=repo_root / "ml-models" / "datasets" / "recommendation_eval.jsonl",
		help="Path to eval dataset jsonl",
	)
	parser.add_argument("--k", type=int, default=3)
	return parser.parse_args()


def load_rows(path: Path) -> list[dict]:
	if not path.exists():
		raise FileNotFoundError(f"Eval dataset not found: {path}")
	rows: list[dict] = []
	with path.open("r", encoding="utf-8") as fp:
		for line in fp:
			line = line.strip()
			if line:
				rows.append(json.loads(line))
	return rows


def main() -> None:
	args = parse_args()
	rows = load_rows(args.dataset)
	if not rows:
		raise ValueError("Evaluation dataset is empty")

	recalls: list[float] = []
	maps: list[float] = []
	ndcgs: list[float] = []
	for row in rows:
		relevant = {str(role) for role in row.get("relevant_roles", [])}
		predicted = [str(role) for role in row.get("predicted_roles", [])]
		recalls.append(_recall_at_k(relevant, predicted, args.k))
		maps.append(_average_precision_at_k(relevant, predicted, args.k))
		ndcgs.append(_ndcg_at_k(relevant, predicted, args.k))

	metrics = {
		"samples": len(rows),
		"k": args.k,
		"recall_at_k": round(sum(recalls) / len(recalls), 4),
		"map_at_k": round(sum(maps) / len(maps), 4),
		"ndcg_at_k": round(sum(ndcgs) / len(ndcgs), 4),
	}
	print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
	main()
