"""Collaborative-filtering runtime inference service.

Loads the artefacts produced by train_cf_recommender.py and returns per-role
CF scores for a requesting user.  If the model is disabled, missing, or the
user is unknown (cold-start), the service returns an empty dict so callers
can safely treat CF as an additive optional signal.
"""

from __future__ import annotations

import pickle
import threading
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_CF_LOCK = threading.Lock()
_CF_CACHE: Optional[dict] = None    # lazily loaded artefact bundle
_CF_LOAD_ATTEMPTED: bool = False    # so we warn only once on missing file


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _resolve(path_text: str) -> Path:
    p = Path(path_text.strip())
    return p if p.is_absolute() else _repo_root() / p


def _load_cf_artefact() -> Optional[dict]:
    """Load and cache CF model artefact bundle (thread-safe, called at most once)."""
    global _CF_CACHE, _CF_LOAD_ATTEMPTED

    with _CF_LOCK:
        if _CF_CACHE is not None:
            return _CF_CACHE
        if _CF_LOAD_ATTEMPTED:
            return None
        _CF_LOAD_ATTEMPTED = True

        model_path = _resolve(settings.cf_model_artifact_path) / "cf_model.pkl"
        if not model_path.exists():
            logger.warning("CF model artefact not found at %s — scoring skipped.", model_path)
            return None

        try:
            with model_path.open("rb") as fh:
                artefact = pickle.load(fh)
            _CF_CACHE = artefact
            logger.info("CF model loaded from %s (%d users, %d roles).",
                        model_path, len(artefact["user_index"]), len(artefact["role_index"]))
            return _CF_CACHE
        except Exception:
            logger.exception("Failed to load CF model artefact from %s.", model_path)
            return None


def score_cf_roles(user_id: str, roles: list[str]) -> dict[str, float]:
    """Return a per-role CF affinity score in [0, 1] for *user_id*.

    Returns an empty dict when:
    - cf_model_enabled is False
    - artefact file is missing
    - *user_id* is not in the training set (cold-start)

    Scores are min-max normalised across the requested *roles* so they are
    directly comparable to content-based scores.
    """
    if not settings.cf_model_enabled:
        return {}

    artefact = _load_cf_artefact()
    if artefact is None:
        return {}

    user_index: list[str] = artefact["user_index"]
    role_index: list[str] = artefact["role_index"]
    col_means: np.ndarray = artefact["col_means"]
    reconstructed: np.ndarray = artefact["reconstructed"]

    role_to_col = {r: j for j, r in enumerate(role_index)}
    requested_cols = [role_to_col[r] for r in roles if r in role_to_col]

    if not requested_cols:
        return {}

    if user_id in user_index:
        row_idx = user_index.index(user_id)
        raw_scores = reconstructed[row_idx, requested_cols]
    else:
        # Cold-start: use the column mean (global role popularity proxy).
        raw_scores = col_means[requested_cols]

    # Min-max normalise to [0, 1].
    s_min, s_max = float(raw_scores.min()), float(raw_scores.max())
    if s_max > s_min:
        normed = (raw_scores - s_min) / (s_max - s_min)
    else:
        normed = np.full_like(raw_scores, 0.5)

    result: dict[str, float] = {}
    for norm_score, col_idx in zip(normed.tolist(), requested_cols):
        result[role_index[col_idx]] = round(float(norm_score), 6)

    return result
