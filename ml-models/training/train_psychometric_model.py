"""Train a simple psychometric primary-domain predictor.

The artifact is optional at runtime and is used to prioritize domain ordering
in psychometric recommendations.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pickle

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split


FEATURE_COLUMNS = [
	"investigative",
	"realistic",
	"artistic",
	"social",
	"enterprising",
	"conventional",
]


DEFAULT_SYNTHETIC_ROWS = [
	{"investigative": 0.9, "realistic": 0.2, "artistic": 0.3, "social": 0.2, "enterprising": 0.4, "conventional": 0.4, "primary_domain": "Data Science"},
	{"investigative": 0.8, "realistic": 0.3, "artistic": 0.2, "social": 0.3, "enterprising": 0.4, "conventional": 0.3, "primary_domain": "AI/ML"},
	{"investigative": 0.7, "realistic": 0.6, "artistic": 0.2, "social": 0.3, "enterprising": 0.3, "conventional": 0.4, "primary_domain": "Research"},
	{"investigative": 0.3, "realistic": 0.8, "artistic": 0.2, "social": 0.3, "enterprising": 0.4, "conventional": 0.4, "primary_domain": "DevOps"},
	{"investigative": 0.2, "realistic": 0.8, "artistic": 0.3, "social": 0.2, "enterprising": 0.3, "conventional": 0.4, "primary_domain": "Cloud Operations"},
	{"investigative": 0.2, "realistic": 0.7, "artistic": 0.3, "social": 0.3, "enterprising": 0.2, "conventional": 0.4, "primary_domain": "Embedded Systems"},
	{"investigative": 0.3, "realistic": 0.2, "artistic": 0.9, "social": 0.5, "enterprising": 0.5, "conventional": 0.3, "primary_domain": "UI/UX"},
	{"investigative": 0.2, "realistic": 0.2, "artistic": 0.8, "social": 0.5, "enterprising": 0.4, "conventional": 0.3, "primary_domain": "Creative Technology"},
	{"investigative": 0.2, "realistic": 0.2, "artistic": 0.7, "social": 0.6, "enterprising": 0.5, "conventional": 0.3, "primary_domain": "Content Design"},
	{"investigative": 0.3, "realistic": 0.2, "artistic": 0.4, "social": 0.9, "enterprising": 0.6, "conventional": 0.3, "primary_domain": "Teaching"},
	{"investigative": 0.2, "realistic": 0.2, "artistic": 0.4, "social": 0.8, "enterprising": 0.5, "conventional": 0.4, "primary_domain": "Counseling"},
	{"investigative": 0.2, "realistic": 0.2, "artistic": 0.3, "social": 0.8, "enterprising": 0.6, "conventional": 0.4, "primary_domain": "People Operations"},
	{"investigative": 0.4, "realistic": 0.2, "artistic": 0.3, "social": 0.5, "enterprising": 0.9, "conventional": 0.5, "primary_domain": "Product Management"},
	{"investigative": 0.5, "realistic": 0.2, "artistic": 0.2, "social": 0.5, "enterprising": 0.8, "conventional": 0.6, "primary_domain": "Business Analysis"},
	{"investigative": 0.4, "realistic": 0.2, "artistic": 0.2, "social": 0.4, "enterprising": 0.8, "conventional": 0.6, "primary_domain": "Consulting"},
	{"investigative": 0.5, "realistic": 0.4, "artistic": 0.2, "social": 0.3, "enterprising": 0.4, "conventional": 0.9, "primary_domain": "Operations"},
	{"investigative": 0.6, "realistic": 0.3, "artistic": 0.2, "social": 0.3, "enterprising": 0.4, "conventional": 0.8, "primary_domain": "Finance Analytics"},
	{"investigative": 0.4, "realistic": 0.3, "artistic": 0.2, "social": 0.3, "enterprising": 0.3, "conventional": 0.8, "primary_domain": "QA Process"},
]


def parse_args() -> argparse.Namespace:
	repo_root = Path(__file__).resolve().parents[2]
	parser = argparse.ArgumentParser(description="Train psychometric model")
	parser.add_argument(
		"--dataset",
		type=Path,
		default=repo_root / "ml-models" / "datasets" / "psychometric_labeled.csv",
		help="Input labeled dataset (optional; synthetic fallback if missing)",
	)
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=repo_root / "ml-models" / "pretrained" / "psychometric_model",
		help="Output directory for model artifact",
	)
	parser.add_argument("--test-size", type=float, default=0.25)
	parser.add_argument("--random-seed", type=int, default=42)
	parser.add_argument("--model-version", type=str, default="v1")
	parser.add_argument("--data-version", type=str, default="unknown")
	return parser.parse_args()


def load_dataset(path: Path) -> pd.DataFrame:
	if path.exists():
		frame = pd.read_csv(path)
	else:
		frame = pd.DataFrame(DEFAULT_SYNTHETIC_ROWS)

	missing = [column for column in [*FEATURE_COLUMNS, "primary_domain"] if column not in frame.columns]
	if missing:
		raise ValueError(f"Dataset missing columns: {missing}")
	return frame


def main() -> None:
	args = parse_args()
	frame = load_dataset(args.dataset)
	x = frame[FEATURE_COLUMNS].clip(lower=0.0, upper=1.0)
	y = frame["primary_domain"].astype(str)

	x_train, x_test, y_train, y_test = train_test_split(
		x,
		y,
		test_size=args.test_size,
		random_state=args.random_seed,
		stratify=y,
	)

	model = RandomForestClassifier(
		n_estimators=220,
		max_depth=8,
		min_samples_leaf=1,
		random_state=args.random_seed,
	)
	model.fit(x_train, y_train)
	y_pred = model.predict(x_test)
	report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

	domains = sorted(y.unique().tolist())
	args.output_dir.mkdir(parents=True, exist_ok=True)
	artifact_path = args.output_dir / "psychometric_model.pkl"
	with artifact_path.open("wb") as fp:
		pickle.dump({"model": model, "domains": domains, "feature_names": FEATURE_COLUMNS}, fp)

	metrics = {
		"macro_f1": float(report.get("macro avg", {}).get("f1-score", 0.0)),
		"accuracy": float(report.get("accuracy", 0.0)),
		"samples_train": int(len(x_train)),
		"samples_test": int(len(x_test)),
		"domain_count": int(len(domains)),
	}
	with (args.output_dir / "metrics.json").open("w", encoding="utf-8") as fp:
		json.dump(metrics, fp, indent=2)
	with (args.output_dir / "model_registry.json").open("w", encoding="utf-8") as fp:
		json.dump(
			{
				"model_name": "psychometric_domain_classifier",
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
	print(f"Saved artifact to: {artifact_path}")


if __name__ == "__main__":
	main()
