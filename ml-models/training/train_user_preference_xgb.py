"""Train a user preference predictor from role-level feedback features.

The output artifact is consumed by backend/app/services/user_model_service.py.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pickle

import pandas as pd
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

try:
	from xgboost import XGBClassifier
except Exception:  # pragma: no cover - fallback for environments without xgboost
	XGBClassifier = None
	from sklearn.ensemble import RandomForestClassifier


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
	parser = argparse.ArgumentParser(description="Train user preference model")
	parser.add_argument(
		"--dataset",
		type=Path,
		default=repo_root / "ml-models" / "datasets" / "user_features.csv",
		help="Input feature dataset",
	)
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=repo_root / "ml-models" / "pretrained" / "user_modeling",
		help="Output directory for model artifacts",
	)
	parser.add_argument("--test-size", type=float, default=0.2)
	parser.add_argument("--random-seed", type=int, default=42)
	parser.add_argument("--model-version", type=str, default="v1")
	parser.add_argument("--data-version", type=str, default="unknown")
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	if not args.dataset.exists():
		raise FileNotFoundError(f"Dataset not found: {args.dataset}")

	frame = pd.read_csv(args.dataset)
	missing = [column for column in FEATURE_COLUMNS + ["target"] if column not in frame.columns]
	if missing:
		raise ValueError(f"Dataset missing columns: {missing}")

	x = frame[FEATURE_COLUMNS].fillna(0.0)
	y = frame["target"].astype(int)
	if y.nunique() < 2:
		raise ValueError("Target requires at least 2 classes")

	x_train, x_test, y_train, y_test = train_test_split(
		x,
		y,
		test_size=args.test_size,
		random_state=args.random_seed,
		stratify=y,
	)

	if XGBClassifier is not None:
		model = XGBClassifier(
			n_estimators=300,
			max_depth=5,
			learning_rate=0.08,
			subsample=0.9,
			colsample_bytree=0.9,
			objective="binary:logistic",
			eval_metric="logloss",
			random_state=args.random_seed,
		)
	else:
		model = RandomForestClassifier(
			n_estimators=250,
			max_depth=6,
			min_samples_leaf=2,
			random_state=args.random_seed,
		)
	model.fit(x_train, y_train)
	y_pred = model.predict(x_test)
	report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

	args.output_dir.mkdir(parents=True, exist_ok=True)
	artifact_path = args.output_dir / "user_preference_model.pkl"
	with artifact_path.open("wb") as fp:
		pickle.dump({"model": model, "feature_names": FEATURE_COLUMNS}, fp)

	metrics = {
		"macro_f1": float(report.get("macro avg", {}).get("f1-score", 0.0)),
		"accuracy": float(report.get("accuracy", 0.0)),
		"samples_train": int(len(x_train)),
		"samples_test": int(len(x_test)),
	}
	with (args.output_dir / "metrics.json").open("w", encoding="utf-8") as fp:
		json.dump(metrics, fp, indent=2)
	with (args.output_dir / "model_registry.json").open("w", encoding="utf-8") as fp:
		json.dump(
			{
				"model_name": "user_preference_classifier",
				"version": args.model_version,
				"trained_at": datetime.now(timezone.utc).isoformat(),
				"data_version": args.data_version,
				"dataset_path": str(args.dataset),
				"metrics": metrics,
			},
			fp,
			indent=2,
		)

	print(f"Training complete. macro_f1={metrics['macro_f1']:.4f}, accuracy={metrics['accuracy']:.4f}")
	print(f"Saved artifacts to: {artifact_path}")


if __name__ == "__main__":
	main()
