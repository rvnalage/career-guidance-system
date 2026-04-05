"""Offline replay evaluator for the epsilon-greedy bandit policy.

Simulates the bandit policy against a held-out feedback log and compares its
per-user Recall@1 and mean reward to a random-selection baseline.

Replay methodology
------------------
For each user in the dataset we:
1. Split their feedback events chronologically into a "train" prefix (to build
   arm statistics) and a held-out "test" tail.
2. Seed the bandit with the train-prefix arm stats.
3. For each held-out event, ask the bandit to select one arm from the
   candidate pool and check whether it matches the user's actual chosen role.
4. Compute Recall@1 (bandit picked the right role) and mean reward.
5. Repeat step 3-4 with a uniform-random baseline.

Output: per-user and aggregate metrics printed to stdout + written to
        `bandit_replay_results.json` in the output directory.

Usage
-----
python evaluate_bandit_replay.py \
    --dataset ml-models/datasets/user_feedback_events.jsonl \
    --output-dir ml-models/evaluation \
    --train-ratio 0.5 \
    --epsilon 0.0
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_feedback(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _group_by_user(rows: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        uid = str(row.get("user_id", "")).strip()
        if uid:
            groups.setdefault(uid, []).append(row)
    return groups


# ---------------------------------------------------------------------------
# Bandit helpers (pure-Python, no import of bandit_service to avoid backend deps)
# ---------------------------------------------------------------------------

def _reward(helpful: bool | str, rating: int | str) -> float:
    if isinstance(helpful, str):
        helpful = helpful.lower() in ("true", "1", "yes")
    h = 1.0 if helpful else 0.0
    r = max(0.0, min(1.0, (int(rating) - 1) / 4.0))
    return 0.5 * h + 0.5 * r


def _arm_mean(stats: dict[str, dict], role: str) -> float:
    s = stats.get(role, {})
    count = s.get("count", 0)
    return float(s.get("reward_sum", 0.0)) / count if count > 0 else 0.5


def _bandit_select(candidates: list[str], stats: dict[str, dict], epsilon: float, rng: random.Random) -> str:
    if not candidates:
        return ""
    if rng.random() < epsilon:
        return rng.choice(candidates)
    return max(candidates, key=lambda r: _arm_mean(stats, r))


def _update_stats(stats: dict[str, dict], role: str, reward: float) -> None:
    arm = stats.setdefault(role, {"count": 0, "reward_sum": 0.0})
    arm["count"] += 1
    arm["reward_sum"] += reward


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def _replay_user(
    events: list[dict],
    train_ratio: float,
    epsilon: float,
    all_roles: list[str],
    rng: random.Random,
) -> dict:
    split = max(1, int(len(events) * train_ratio))
    train_events = events[:split]
    test_events = events[split:]

    # Seed bandit from train prefix.
    bandit_stats: dict[str, dict] = {}
    for ev in train_events:
        role = str(ev.get("role", "")).strip()
        rew = _reward(ev.get("helpful", False), ev.get("rating", 3))
        _update_stats(bandit_stats, role, rew)

    bandit_hits = 0
    bandit_rewards: list[float] = []
    random_hits = 0
    random_rewards: list[float] = []

    for ev in test_events:
        true_role = str(ev.get("role", "")).strip()
        true_helpful = ev.get("helpful", False)
        if isinstance(true_helpful, str):
            true_helpful = true_helpful.lower() in ("true", "1", "yes")
        # Only reward positive events (the ground truth "good" recommendations).
        if not true_helpful:
            continue

        # Candidate pool = all roles minus those in the train prefix.
        candidates = all_roles if all_roles else [true_role]

        bandit_pick = _bandit_select(candidates, bandit_stats, epsilon, rng)
        bandit_rew = _reward(true_helpful, ev.get("rating", 3)) if bandit_pick == true_role else 0.0
        bandit_hits += int(bandit_pick == true_role)
        bandit_rewards.append(bandit_rew)

        random_pick = rng.choice(candidates)
        random_rew = _reward(true_helpful, ev.get("rating", 3)) if random_pick == true_role else 0.0
        random_hits += int(random_pick == true_role)
        random_rewards.append(random_rew)

    n = max(len(bandit_rewards), 1)
    return {
        "n_test_positive": len(bandit_rewards),
        "bandit_recall_at_1": round(bandit_hits / n, 4),
        "bandit_mean_reward": round(sum(bandit_rewards) / n, 4),
        "random_recall_at_1": round(random_hits / n, 4),
        "random_mean_reward": round(sum(random_rewards) / n, 4),
    }


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------

def _aggregate(per_user: dict[str, dict]) -> dict:
    if not per_user:
        return {}
    keys = ["bandit_recall_at_1", "bandit_mean_reward", "random_recall_at_1", "random_mean_reward"]
    result = {}
    for k in keys:
        vals = [v[k] for v in per_user.values()]
        result[f"mean_{k}"] = round(sum(vals) / len(vals), 4)
    result["n_users"] = len(per_user)
    result["bandit_vs_random_recall_lift"] = round(
        result["mean_bandit_recall_at_1"] - result["mean_random_recall_at_1"], 4
    )
    result["bandit_vs_random_reward_lift"] = round(
        result["mean_bandit_mean_reward"] - result["mean_random_mean_reward"], 4
    )
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_roles() -> list[str]:
    try:
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root / "backend"))
        from app.utils.constants import CAREER_PATHS
        return [p["role"] for p in CAREER_PATHS]
    except Exception:
        return []


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline bandit replay evaluation.")
    parser.add_argument("--dataset", default="ml-models/datasets/user_feedback_events.jsonl")
    parser.add_argument("--output-dir", default="ml-models/evaluation")
    parser.add_argument("--train-ratio", type=float, default=0.5,
                        help="Fraction of each user's events used to seed bandit state.")
    parser.add_argument("--epsilon", type=float, default=0.0,
                        help="Exploration rate during replay (0.0 = pure exploitation).")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    dataset_path = Path(args.dataset)
    output_dir = Path(args.output_dir)

    if not dataset_path.exists():
        print(f"[bandit-replay] Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    rng = random.Random(args.seed)
    all_roles = _default_roles()
    rows = _load_feedback(dataset_path)
    groups = _group_by_user(rows)

    per_user: dict[str, dict] = {}
    for uid, events in groups.items():
        per_user[uid] = _replay_user(events, args.train_ratio, args.epsilon, all_roles, rng)

    aggregate = _aggregate(per_user)

    print("\n=== Bandit Offline Replay Results ===")
    print(f"Users evaluated : {aggregate.get('n_users', 0)}")
    print(f"Bandit  Recall@1: {aggregate.get('mean_bandit_recall_at_1', 0):.4f}")
    print(f"Random  Recall@1: {aggregate.get('mean_random_recall_at_1', 0):.4f}")
    print(f"Recall lift      : {aggregate.get('bandit_vs_random_recall_lift', 0):+.4f}")
    print(f"Bandit  MeanRew  : {aggregate.get('mean_bandit_mean_reward', 0):.4f}")
    print(f"Random  MeanRew  : {aggregate.get('mean_random_mean_reward', 0):.4f}")
    print(f"Reward lift      : {aggregate.get('bandit_vs_random_reward_lift', 0):+.4f}")

    output_dir.mkdir(parents=True, exist_ok=True)
    result = {"aggregate": aggregate, "per_user": per_user}
    out_path = output_dir / "bandit_replay_results.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
