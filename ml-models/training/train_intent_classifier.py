"""Train a lightweight intent classifier for phase-2 model-first routing.

This baseline trainer uses TF-IDF + Logistic Regression so training is fast,
reproducible, and compatible with local development constraints.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import pickle

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


@dataclass
class TrainResult:
	"""Returned metrics from a training run."""
	macro_f1: float
	samples_train: int
	samples_test: int
	labels: list[str]


def parse_args() -> argparse.Namespace:
	"""Parse command-line arguments for dataset and output paths."""
	default_repo = Path(__file__).resolve().parents[2]
	parser = argparse.ArgumentParser(description="Train intent classifier")
	parser.add_argument(
		"--dataset",
		type=Path,
		default=default_repo / "ml-models" / "datasets" / "intent_queries.csv",
		help="Path to CSV with query,intent columns",
	)
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=default_repo / "ml-models" / "pretrained" / "intent_model",
		help="Output directory for model artifacts",
	)
	parser.add_argument("--test-size", type=float, default=0.2)
	parser.add_argument("--random-seed", type=int, default=42)
	parser.add_argument("--model-version", type=str, default="v1")
	parser.add_argument("--data-version", type=str, default="unknown")
	return parser.parse_args()


def load_dataset(path: Path) -> tuple[list[str], list[str]]:
	"""Load and validate intent training data from CSV."""
	if not path.exists():
		raise FileNotFoundError(f"Dataset not found: {path}")
	frame = pd.read_csv(path)
	required = {"query", "intent"}
	missing = required.difference(frame.columns)
	if missing:
		raise ValueError(f"Missing required columns: {sorted(missing)}")

	frame = frame.dropna(subset=["query", "intent"])
	queries = [str(item).strip() for item in frame["query"].tolist()]
	intents = [str(item).strip() for item in frame["intent"].tolist()]
	rows = [(q, i) for q, i in zip(queries, intents) if q and i]
	if len(rows) < 20:
		raise ValueError("Need at least 20 labeled rows to train intent classifier")

	clean_queries = [item[0] for item in rows]
	clean_intents = [item[1] for item in rows]
	return clean_queries, clean_intents


def train_model(queries: list[str], intents: list[str], test_size: float, random_seed: int) -> tuple[Pipeline, TrainResult]:
	"""Train TF-IDF + logistic regression and return fitted pipeline and metrics."""
	label_set = sorted(set(intents))
	if len(label_set) < 2:
		raise ValueError("Intent dataset must contain at least 2 unique intent classes")

	x_train, x_test, y_train, y_test = train_test_split(
		queries,
		intents,
		test_size=test_size,
		random_state=random_seed,
		stratify=intents,
	)

	pipeline = Pipeline(
		steps=[
			("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=8000)),
			("clf", LogisticRegression(max_iter=500, class_weight="balanced")),
		]
	)
	pipeline.fit(x_train, y_train)

	y_pred = pipeline.predict(x_test)
	report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
	macro_f1 = float(report.get("macro avg", {}).get("f1-score", 0.0))
	result = TrainResult(
		macro_f1=round(macro_f1, 4),
		samples_train=len(x_train),
		samples_test=len(x_test),
		labels=label_set,
	)
	return pipeline, result


def save_artifacts(model: Pipeline, result: TrainResult, output_dir: Path, *, model_version: str, data_version: str, dataset_path: Path) -> None:
	"""Persist model and metadata files used by backend runtime inference."""
	output_dir.mkdir(parents=True, exist_ok=True)
	with (output_dir / "intent_model.pkl").open("wb") as fp:
		pickle.dump(model, fp)
	with (output_dir / "labels.json").open("w", encoding="utf-8") as fp:
		json.dump({"labels": result.labels}, fp, indent=2)
	with (output_dir / "metrics.json").open("w", encoding="utf-8") as fp:
		json.dump(
			{
				"macro_f1": result.macro_f1,
				"samples_train": result.samples_train,
				"samples_test": result.samples_test,
				"labels": result.labels,
			},
			fp,
			indent=2,
		)
	with (output_dir / "model_registry.json").open("w", encoding="utf-8") as fp:
		json.dump(
			{
				"model_name": "intent_classifier_tfidf_logreg",
				"version": model_version,
				"trained_at": datetime.now(timezone.utc).isoformat(),
				"data_version": data_version,
				"dataset_path": str(dataset_path),
				"metrics": {
					"macro_f1": result.macro_f1,
					"samples_train": result.samples_train,
					"samples_test": result.samples_test,
				},
			},
			fp,
			indent=2,
		)


def main() -> None:
	"""Execute full train/evaluate/save pipeline."""
	args = parse_args()
	queries, intents = load_dataset(args.dataset)
	model, result = train_model(queries, intents, args.test_size, args.random_seed)
	save_artifacts(
		model,
		result,
		args.output_dir,
		model_version=args.model_version,
		data_version=args.data_version,
		dataset_path=args.dataset,
	)
	print(f"Training complete. macro_f1={result.macro_f1}")
	print(f"Saved artifacts to: {args.output_dir}")


if __name__ == "__main__":
	main()
