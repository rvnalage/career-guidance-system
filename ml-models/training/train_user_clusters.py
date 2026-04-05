"""Train optional user clusters from aggregated feedback features.

This script clusters users to support phase-2 segmentation experiments.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import pickle

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


FEATURE_COLUMNS = [
	"role_feedback_count",
	"role_feedback_ratio",
	"role_helpful_rate",
	"role_avg_rating_norm",
	"tag_skills_rate",
	"tag_interests_rate",
	"tag_education_rate",
]


def parse_args() -> argparse.Namespace:
	repo_root = Path(__file__).resolve().parents[2]
	parser = argparse.ArgumentParser(description="Train user clustering model")
	parser.add_argument(
		"--dataset",
		type=Path,
		default=repo_root / "ml-models" / "datasets" / "user_features.csv",
		help="Role-level feature dataset",
	)
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=repo_root / "ml-models" / "pretrained" / "user_modeling",
		help="Artifact output directory",
	)
	parser.add_argument("--clusters", type=int, default=3)
	parser.add_argument("--random-seed", type=int, default=42)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	if not args.dataset.exists():
		raise FileNotFoundError(f"Dataset not found: {args.dataset}")

	frame = pd.read_csv(args.dataset)
	missing = [column for column in ["user_id", *FEATURE_COLUMNS] if column not in frame.columns]
	if missing:
		raise ValueError(f"Dataset missing columns: {missing}")

	user_frame = frame.groupby("user_id", as_index=False)[FEATURE_COLUMNS].mean()
	if len(user_frame) < max(3, args.clusters):
		raise ValueError("Need at least as many users as clusters and minimum 3 users")

	x = user_frame[FEATURE_COLUMNS].fillna(0.0)
	model = KMeans(n_clusters=args.clusters, random_state=args.random_seed, n_init=20)
	labels = model.fit_predict(x)
	score = float(silhouette_score(x, labels)) if len(set(labels)) > 1 else 0.0

	args.output_dir.mkdir(parents=True, exist_ok=True)
	artifact_path = args.output_dir / "user_clusters.pkl"
	with artifact_path.open("wb") as fp:
		pickle.dump({"model": model, "feature_names": FEATURE_COLUMNS}, fp)

	metrics = {
		"silhouette_score": score,
		"num_users": int(len(user_frame)),
		"clusters": int(args.clusters),
	}
	with (args.output_dir / "cluster_metrics.json").open("w", encoding="utf-8") as fp:
		json.dump(metrics, fp, indent=2)

	print(f"Clustering complete. silhouette_score={score:.4f}")
	print(f"Saved artifacts to: {artifact_path}")


if __name__ == "__main__":
	main()
