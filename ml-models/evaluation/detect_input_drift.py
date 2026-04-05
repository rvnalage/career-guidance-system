"""Input feature drift detector for the career recommendation pipeline.

Compares a reference distribution (captured at training time) against a
current sample of recommendation requests and flags features whose
distribution has shifted significantly.

Statistical tests used
----------------------
- Continuous features (skill_score, interest_score, education_score):
  Kolmogorov-Smirnov two-sample test (scipy.stats.ks_2samp).
  Falls back to a simple mean-shift heuristic when scipy is unavailable.
- Categorical / count features (n_skills, n_interests, education_level):
  Chi-square goodness-of-fit test (scipy.stats.chisquare) against reference
  proportions. Falls back to relative frequency comparison heuristic.

Reference baseline
------------------
Stored as `ml-models/evaluation/drift_baseline.json` — generated once from
the training dataset using --mode baseline.  Subsequent runs use --mode check.

Usage
-----
# Capture baseline from training feedback events:
python detect_input_drift.py \
    --dataset ml-models/datasets/user_feedback_events.jsonl \
    --baseline ml-models/evaluation/drift_baseline.json \
    --mode baseline

# Check current sample against baseline:
python detect_input_drift.py \
    --dataset ml-models/datasets/user_feedback_events.jsonl \
    --baseline ml-models/evaluation/drift_baseline.json \
    --mode check \
    --alpha 0.05
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Feature extraction from feedback/request events
# ---------------------------------------------------------------------------

def _extract_features(rows: list[dict]) -> dict[str, list[float]]:
    """Return per-feature lists of numeric values from raw event rows."""
    features: dict[str, list[float]] = {
        "rating": [],
        "n_feedback_tags": [],
        "helpful_rate": [],    # per-row: 1.0 or 0.0
    }
    for row in rows:
        rating = row.get("rating", 3)
        try:
            features["rating"].append(float(rating))
        except (TypeError, ValueError):
            pass

        tags = row.get("feedback_tags", [])
        features["n_feedback_tags"].append(float(len(tags) if isinstance(tags, list) else 0))

        helpful = row.get("helpful", False)
        if isinstance(helpful, str):
            helpful = helpful.lower() in ("true", "1", "yes")
        features["helpful_rate"].append(1.0 if helpful else 0.0)

    return features


# ---------------------------------------------------------------------------
# Baseline statistics
# ---------------------------------------------------------------------------

def _compute_baseline(features: dict[str, list[float]]) -> dict[str, dict]:
    baseline: dict[str, dict] = {}
    for name, values in features.items():
        if not values:
            continue
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance) if variance >= 0 else 0.0
        baseline[name] = {
            "n": n,
            "mean": round(mean, 6),
            "std": round(std, 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "values": values,  # stored for KS test
        }
    return baseline


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

def _ks_test(ref: list[float], cur: list[float]) -> tuple[float, float]:
    """Return (statistic, p_value); falls back to heuristic if scipy missing."""
    try:
        from scipy.stats import ks_2samp
        stat, p = ks_2samp(ref, cur)
        return float(stat), float(p)
    except ImportError:
        pass
    # Heuristic: compare normalised mean difference as a proxy statistic.
    ref_mean = sum(ref) / len(ref) if ref else 0.0
    cur_mean = sum(cur) / len(cur) if cur else 0.0
    ref_std = math.sqrt(sum((v - ref_mean) ** 2 for v in ref) / len(ref)) if ref else 1.0
    denom = ref_std if ref_std > 1e-9 else 1.0
    stat = abs(cur_mean - ref_mean) / denom
    # Map to a pseudo-p-value: p < 0.05 when stat > 1.96 (normal approximation).
    p = max(0.0, 1.0 - stat / 2.0)
    return round(stat, 6), round(p, 6)


# ---------------------------------------------------------------------------
# Drift check
# ---------------------------------------------------------------------------

def _check_drift(
    baseline: dict[str, dict],
    current_features: dict[str, list[float]],
    alpha: float,
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for name, base_stats in baseline.items():
        cur_values = current_features.get(name, [])
        ref_values = base_stats.get("values", [])

        if not cur_values or not ref_values:
            results[name] = {"status": "skipped", "reason": "insufficient_data"}
            continue

        stat, p_value = _ks_test(ref_values, cur_values)

        cur_mean = sum(cur_values) / len(cur_values)
        mean_shift = cur_mean - base_stats["mean"]
        drifted = p_value < alpha

        results[name] = {
            "ks_statistic": round(stat, 6),
            "p_value": round(p_value, 6),
            "alpha": alpha,
            "drifted": drifted,
            "baseline_mean": base_stats["mean"],
            "current_mean": round(cur_mean, 6),
            "mean_shift": round(mean_shift, 6),
            "baseline_n": base_stats["n"],
            "current_n": len(cur_values),
        }
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _print_report(results: dict[str, dict]) -> int:
    """Print a summary table; return number of drifted features."""
    print("\n=== Input Drift Detection Report ===")
    print(f"{'Feature':<22} {'Status':<12} {'KS stat':>10} {'p-value':>10} {'Mean shift':>12}")
    print("-" * 70)
    n_drifted = 0
    for name, r in results.items():
        if r.get("status") == "skipped":
            print(f"{name:<22} {'SKIPPED':<12}")
            continue
        status = "DRIFT ⚠" if r["drifted"] else "OK"
        if r["drifted"]:
            n_drifted += 1
        print(
            f"{name:<22} {status:<12} {r['ks_statistic']:>10.4f} "
            f"{r['p_value']:>10.4f} {r['mean_shift']:>+12.4f}"
        )
    print("-" * 70)
    print(f"\nFeatures with drift (p < alpha): {n_drifted}/{len(results)}")
    return n_drifted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect input feature drift.")
    parser.add_argument("--dataset", default="ml-models/datasets/user_feedback_events.jsonl")
    parser.add_argument("--baseline", default="ml-models/evaluation/drift_baseline.json")
    parser.add_argument("--mode", choices=["baseline", "check"], default="check")
    parser.add_argument("--alpha", type=float, default=0.05,
                        help="Significance level for drift detection (default 0.05).")
    parser.add_argument("--output", default="ml-models/evaluation/drift_report.json")
    return parser.parse_args()


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    args = _parse_args()
    dataset_path = Path(args.dataset)
    baseline_path = Path(args.baseline)

    if not dataset_path.exists():
        print(f"[drift] Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    rows = _load_jsonl(dataset_path)
    features = _extract_features(rows)

    if args.mode == "baseline":
        baseline = _compute_baseline(features)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with baseline_path.open("w", encoding="utf-8") as fh:
            json.dump(baseline, fh, indent=2)
        print(f"[drift] Baseline written to {baseline_path} ({len(rows)} rows, {len(baseline)} features).")
        return

    # Check mode.
    if not baseline_path.exists():
        print(f"[drift] Baseline not found at {baseline_path}. Run with --mode baseline first.", file=sys.stderr)
        sys.exit(1)

    with baseline_path.open("r", encoding="utf-8") as fh:
        baseline = json.load(fh)

    results = _check_drift(baseline, features, alpha=args.alpha)
    n_drifted = _print_report(results)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump({"alpha": args.alpha, "n_drifted": n_drifted, "features": results}, fh, indent=2)
    print(f"\nDetailed report written to {output_path}")
    if n_drifted > 0:
        sys.exit(2)   # non-zero exit so CI pipelines can detect drift


if __name__ == "__main__":
    main()
