"""Build role-level user preference features from recommendation feedback history.

This script transforms feedback events into tabular training rows for
phase-2 user preference modeling.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROLES = [
	"Data Analyst",
	"Machine Learning Engineer",
	"Backend Developer",
	"Cloud DevOps Engineer",
	"UI/UX Designer",
]


def _normalized_tags(raw_tags: list[object]) -> list[str]:
	result: list[str] = []
	for item in raw_tags:
		text = str(item).strip().lower()
		if text:
			result.append(text)
	return result


def _safe_mean(values: list[float]) -> float:
	if not values:
		return 0.0
	return float(sum(values) / len(values))


def _role_features(feedback_items: list[dict], role: str) -> dict[str, float]:
	role_text = role.strip().lower()
	role_items = [
		item
		for item in feedback_items
		if str(item.get("role", "")).strip().lower() == role_text
	]
	all_count = len(feedback_items)
	role_count = len(role_items)
	if role_count == 0:
		return {
			"role_feedback_count": 0.0,
			"role_feedback_ratio": 0.0,
			"role_helpful_rate": 0.0,
			"role_avg_rating_norm": 0.5,
			"tag_skills_rate": 0.0,
			"tag_interests_rate": 0.0,
			"tag_education_rate": 0.0,
		}

	helpful_values = [1.0 if bool(item.get("helpful", False)) else 0.0 for item in role_items]
	rating_values = [max(1, min(5, int(item.get("rating", 3)))) for item in role_items]
	rating_norm = [float((value - 1) / 4) for value in rating_values]

	tag_skills = 0
	tag_interests = 0
	tag_education = 0
	for item in role_items:
		tags = _normalized_tags(item.get("feedback_tags", []))
		if "skills" in tags:
			tag_skills += 1
		if "interests" in tags:
			tag_interests += 1
		if "education" in tags:
			tag_education += 1

	return {
		"role_feedback_count": float(role_count),
		"role_feedback_ratio": float(role_count / max(1, all_count)),
		"role_helpful_rate": _safe_mean(helpful_values),
		"role_avg_rating_norm": _safe_mean(rating_norm),
		"tag_skills_rate": float(tag_skills / role_count),
		"tag_interests_rate": float(tag_interests / role_count),
		"tag_education_rate": float(tag_education / role_count),
	}


def _load_feedback(path: Path) -> list[dict]:
	if not path.exists():
		raise FileNotFoundError(f"Feedback source not found: {path}")
	if path.suffix.lower() == ".jsonl":
		rows: list[dict] = []
		with path.open("r", encoding="utf-8") as fp:
			for line in fp:
				line = line.strip()
				if line:
					rows.append(json.loads(line))
		return rows
	if path.suffix.lower() == ".json":
		with path.open("r", encoding="utf-8") as fp:
			payload = json.load(fp)
			if isinstance(payload, list):
				return [item for item in payload if isinstance(item, dict)]
			raise ValueError("JSON feedback file must be an array of objects")
	if path.suffix.lower() == ".csv":
		frame = pd.read_csv(path)
		return frame.to_dict(orient="records")
	raise ValueError("Unsupported input format. Use .jsonl, .json, or .csv")


def _to_dataset(feedback_rows: list[dict]) -> pd.DataFrame:
	groups: dict[str, list[dict]] = {}
	for item in feedback_rows:
		user_id = str(item.get("user_id", "")).strip()
		if not user_id:
			continue
		groups.setdefault(user_id, []).append(item)

	records: list[dict] = []
	for user_id, items in groups.items():
		for role in ROLES:
			features = _role_features(items, role)
			role_items = [
				entry
				for entry in items
				if str(entry.get("role", "")).strip().lower() == role.lower()
			]
			positive = False
			for entry in role_items:
				rating = max(1, min(5, int(entry.get("rating", 3))))
				if bool(entry.get("helpful", False)) and rating >= 4:
					positive = True
					break

			record = {
				"user_id": user_id,
				"role": role,
				**features,
				"target": 1 if positive else 0,
			}
			records.append(record)

	return pd.DataFrame(records)


def parse_args() -> argparse.Namespace:
	repo_root = Path(__file__).resolve().parents[2]
	parser = argparse.ArgumentParser(description="Build user preference feature dataset")
	parser.add_argument(
		"--feedback-source",
		type=Path,
		default=repo_root / "ml-models" / "datasets" / "user_feedback_events.jsonl",
		help="Path to feedback events (.jsonl, .json, .csv)",
	)
	parser.add_argument(
		"--output-csv",
		type=Path,
		default=repo_root / "ml-models" / "datasets" / "user_features.csv",
		help="Output feature dataset csv path",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	feedback_rows = _load_feedback(args.feedback_source)
	frame = _to_dataset(feedback_rows)
	if frame.empty:
		raise ValueError("No usable rows produced from feedback source")
	args.output_csv.parent.mkdir(parents=True, exist_ok=True)
	frame.to_csv(args.output_csv, index=False)
	print(f"Wrote {len(frame)} rows to {args.output_csv}")


if __name__ == "__main__":
	main()
