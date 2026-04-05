"""Train a collaborative-filtering recommender using truncated SVD on a user-role feedback matrix.

Design notes
------------
- Interaction matrix  : rows = users, cols = roles (from CAREER_PATHS role list)
- Entry value         : weighted sum of feedback signals per (user, role) pair
                        helpful(+1/-1) + normalised rating (rating-3)/10 * 2
- Decomposition       : sklearn TruncatedSVD (works on dense or sparse matrices,
                        no scipy dependency required)
- CF score            : reconstruct the full matrix, then look up the row for a
                        target user; unknown users fall back to role column means
- Output artefacts    : cf_model.pkl  (fitted SVD + row/col index maps + col means)
                        metrics.json  (explained variance, n_components, n_users, n_roles)
                        model_registry.json

Usage
-----
python train_cf_recommender.py \
    --dataset  ml-models/datasets/user_feedback_events.jsonl \
    --output-dir ml-models/pretrained/cf_model \
    --n-components 4 \
    --model-version 1.0.0 \
    --data-version 1.0.0
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Interaction matrix builder
# ---------------------------------------------------------------------------

def _load_feedback(dataset_path: Path) -> list[dict]:
    rows: list[dict] = []
    suffix = dataset_path.suffix.lower()
    if suffix == ".jsonl":
        with dataset_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    elif suffix == ".json":
        with dataset_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        rows = data if isinstance(data, list) else []
    else:
        import csv
        with dataset_path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    return rows


def _build_interaction_matrix(
    feedback_items: list[dict],
    role_list: list[str],
) -> tuple[np.ndarray, list[str], list[str]]:
    """Return (matrix, user_index, role_index) where matrix[i,j] = interaction score."""
    role_to_col = {r: j for j, r in enumerate(role_list)}

    # accumulator: user -> role -> (total_signal, count)
    acc: dict[str, dict[str, list[float]]] = {}
    for item in feedback_items:
        user_id = str(item.get("user_id", "")).strip()
        role = str(item.get("role", "")).strip()
        helpful = item.get("helpful", False)
        if isinstance(helpful, str):
            helpful = helpful.lower() in ("true", "1", "yes")
        rating = float(item.get("rating", 3))
        if not user_id or role not in role_to_col:
            continue
        signal = (1.0 if helpful else -1.0) + (rating - 3.0) / 5.0
        acc.setdefault(user_id, {}).setdefault(role, []).append(signal)

    user_index = sorted(acc.keys())
    n_users = len(user_index)
    n_roles = len(role_list)
    matrix = np.zeros((n_users, n_roles), dtype=np.float32)
    for i, uid in enumerate(user_index):
        for role, signals in acc[uid].items():
            j = role_to_col[role]
            matrix[i, j] = float(np.mean(signals))

    return matrix, user_index, role_list


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    feedback_items: list[dict],
    role_list: list[str],
    n_components: int = 4,
    random_seed: int = 42,
) -> dict:
    """Fit TruncatedSVD on the feedback matrix and return artefact bundle."""
    from sklearn.decomposition import TruncatedSVD

    matrix, user_index, role_index = _build_interaction_matrix(feedback_items, role_list)
    n_users, n_roles = matrix.shape

    # Clamp n_components if matrix is too small to avoid SVD failure.
    effective_k = min(n_components, n_users - 1, n_roles - 1, max(1, n_users))

    col_means = matrix.mean(axis=0)  # fallback scores for cold-start users

    svd = TruncatedSVD(n_components=effective_k, random_state=random_seed)
    latent = svd.fit_transform(matrix)          # shape (n_users, k)
    reconstructed = latent @ svd.components_    # shape (n_users, n_roles)
    explained_variance = float(svd.explained_variance_ratio_.sum())

    return {
        "svd": svd,
        "user_index": user_index,
        "role_index": role_index,
        "latent": latent,
        "reconstructed": reconstructed,
        "col_means": col_means,
        "n_components": effective_k,
        "explained_variance": explained_variance,
        "n_users": n_users,
        "n_roles": n_roles,
    }


# ---------------------------------------------------------------------------
# Artefact persistence
# ---------------------------------------------------------------------------

def save_artifacts(
    bundle: dict,
    output_dir: Path,
    model_version: str = "1.0.0",
    data_version: str = "1.0.0",
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    artefact = {
        "svd": bundle["svd"],
        "user_index": bundle["user_index"],
        "role_index": bundle["role_index"],
        "col_means": bundle["col_means"],
        "reconstructed": bundle["reconstructed"],
    }
    with (output_dir / "cf_model.pkl").open("wb") as fh:
        pickle.dump(artefact, fh, protocol=pickle.HIGHEST_PROTOCOL)

    metrics = {
        "n_components": bundle["n_components"],
        "n_users": bundle["n_users"],
        "n_roles": bundle["n_roles"],
        "explained_variance_ratio": round(bundle["explained_variance"], 6),
    }
    with (output_dir / "metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)

    registry = {
        "model_name": "cf_recommender",
        "model_version": model_version,
        "data_version": data_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "TruncatedSVD",
        "n_components": bundle["n_components"],
        "n_users": bundle["n_users"],
        "n_roles": bundle["n_roles"],
        "explained_variance_ratio": round(bundle["explained_variance"], 6),
        "artifacts": ["cf_model.pkl", "metrics.json"],
    }
    with (output_dir / "model_registry.json").open("w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2)

    print(f"[CF] Saved artefacts to {output_dir}")
    print(f"     Users: {bundle['n_users']}  Roles: {bundle['n_roles']}  k={bundle['n_components']}  "
          f"ExplainedVar: {bundle['explained_variance']:.4f}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_roles() -> list[str]:
    """Return canonical role list from constants when available at runtime."""
    try:
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root / "backend"))
        from app.utils.constants import CAREER_PATHS
        return [p["role"] for p in CAREER_PATHS]
    except Exception:
        return [
            "Software Engineer", "Data Scientist", "Product Manager",
            "UX Designer", "DevOps Engineer", "Data Analyst",
            "ML Engineer", "Backend Developer", "Frontend Developer",
            "Research Scientist", "Data Engineer", "Product Analyst",
        ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train CF recommender via TruncatedSVD.")
    parser.add_argument("--dataset", default="ml-models/datasets/user_feedback_events.jsonl")
    parser.add_argument("--output-dir", default="ml-models/pretrained/cf_model")
    parser.add_argument("--n-components", type=int, default=4)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--model-version", default="1.0.0")
    parser.add_argument("--data-version", default="1.0.0")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)
    if not dataset_path.exists():
        print(f"[CF] Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    feedback_items = _load_feedback(dataset_path)
    if not feedback_items:
        print("[CF] No feedback events found. Exiting.", file=sys.stderr)
        sys.exit(1)

    role_list = _default_roles()
    bundle = train(feedback_items, role_list, n_components=args.n_components, random_seed=args.random_seed)
    save_artifacts(bundle, output_dir, model_version=args.model_version, data_version=args.data_version)


if __name__ == "__main__":
    main()
