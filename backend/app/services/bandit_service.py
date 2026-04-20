"""Epsilon-greedy contextual bandit for recommendation arm exploration.

The bandit maintains per-role (arm) statistics â€” cumulative reward and pull
count â€” persisted as a lightweight JSON file.  On each recommendation request
it can reorder the top-K candidates by blending the UCB-style arm mean with
the existing content score, occasionally exploring lower-ranked arms.

Design choices
--------------
- State file  : JSON (human-readable, no binary dependency)
- Update hook : called from the feedback endpoint after a user rates a result
- Exploration : pure epsilon-greedy; epsilon=0.1 by default (configurable)
- Thread-safe : threading.Lock guards state mutations
- Cold-start  : new arms start with mean=0.5, count=0 (neutral prior)
"""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from __future__ import annotations

import json
import random
import threading
from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_BANDIT_LOCK = threading.Lock()
_BANDIT_STATE: Optional[dict[str, dict]] = None   # {arm_id: {count, reward_sum}}
_STATE_LOAD_ATTEMPTED: bool = False


# ---------------------------------------------------------------------------
# State persistence helpers
# ---------------------------------------------------------------------------

def _state_path() -> Path:
    p = Path(settings.bandit_artifact_path.strip())
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[4] / p
    p.mkdir(parents=True, exist_ok=True)
    return p / "bandit_state.json"


def _load_state() -> dict[str, dict]:
    """Load bandit state from disk; return empty dict on any error."""
    global _BANDIT_STATE, _STATE_LOAD_ATTEMPTED
    if _BANDIT_STATE is not None:
        return _BANDIT_STATE
    _STATE_LOAD_ATTEMPTED = True
    path = _state_path()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as fh:
                _BANDIT_STATE = json.load(fh)
            logger.info("Bandit state loaded from %s (%d arms).", path, len(_BANDIT_STATE))
        except Exception:
            logger.exception("Failed to load bandit state from %s; starting fresh.", path)
            _BANDIT_STATE = {}
    else:
        _BANDIT_STATE = {}
    return _BANDIT_STATE


def _save_state(state: dict[str, dict]) -> None:
    """Persist bandit state to disk (called while the lock is held)."""
    try:
        with _state_path().open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
    except Exception:
        logger.exception("Failed to persist bandit state.")


# ---------------------------------------------------------------------------
# Core bandit operations
# ---------------------------------------------------------------------------

def _arm_mean(arm_stats: dict) -> float:
    """Return empirical mean reward; default 0.5 for unseen arms."""
    count = arm_stats.get("count", 0)
    if count <= 0:
        return 0.5
    return float(arm_stats.get("reward_sum", 0.0)) / count


def record_feedback(role: str, helpful: bool, rating: int) -> None:
    """Update arm statistics for *role* based on a single feedback event.

    Call this from the feedback endpoint.  The reward signal is:
        reward = 0.5 * helpful_flag + 0.5 * (rating - 1) / 4
    which maps a (helpful=True, rating=5) event to 1.0 and
    (helpful=False, rating=1) to 0.0.
    """
    if not settings.bandit_enabled:
        return

    reward = 0.5 * (1.0 if helpful else 0.0) + 0.5 * max(0.0, min(1.0, (int(rating) - 1) / 4.0))

    with _BANDIT_LOCK:
        state = _load_state()
        arm = state.setdefault(role, {"count": 0, "reward_sum": 0.0})
        arm["count"] = arm.get("count", 0) + 1
        arm["reward_sum"] = float(arm.get("reward_sum", 0.0)) + reward
        _save_state(state)
        logger.debug("Bandit arm '%s' updated: count=%d reward_sum=%.4f",
                     role, arm["count"], arm["reward_sum"])


def rerank_recommendations(
    roles_ordered: list[str],
    rng: Optional[random.Random] = None,
) -> list[str]:
    """Return *roles_ordered* potentially reordered by epsilon-greedy exploration.

    With probability epsilon the list is shuffled to explore; otherwise it is
    sorted by descending arm mean while preserving relative content-based order
    for arms with equal statistics (stable sort).

    Parameters
    ----------
    roles_ordered:
        Top-K role names as produced by the content-based ranker, highest first.
    rng:
        Optional seeded Random instance for deterministic tests.
    """
    if not settings.bandit_enabled or not roles_ordered:
        return roles_ordered

    epsilon = float(settings.bandit_epsilon)
    rng = rng or random.Random()

    if rng.random() < epsilon:
        # Exploration: random shuffle.
        shuffled = list(roles_ordered)
        rng.shuffle(shuffled)
        logger.debug("Bandit explore: %s", shuffled)
        return shuffled

    # Exploitation: sort descending by arm mean, keeping original order as tiebreaker.
    with _BANDIT_LOCK:
        state = _load_state()

    indexed = [(i, role, _arm_mean(state.get(role, {}))) for i, role in enumerate(roles_ordered)]
    indexed.sort(key=lambda x: (-x[2], x[0]))  # high mean first, stable on orig index
    result = [role for _, role, _ in indexed]
    logger.debug("Bandit exploit rerank: %s", result)
    return result


def get_arm_stats() -> dict[str, dict]:
    """Return a snapshot of all arm statistics (for observability endpoints)."""
    if not settings.bandit_enabled:
        return {}
    with _BANDIT_LOCK:
        state = _load_state()
    return {
        role: {"count": s.get("count", 0), "mean_reward": round(_arm_mean(s), 4)}
        for role, s in state.items()
    }

