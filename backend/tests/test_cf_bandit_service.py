"""Tests for CF service and bandit service."""

from __future__ import annotations

import json
import pickle
import random
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np


# ---------------------------------------------------------------------------
# CF service tests
# ---------------------------------------------------------------------------

def test_score_cf_roles_disabled(monkeypatch):
    """Return empty dict when CF is disabled."""
    from app.config import settings
    monkeypatch.setattr(settings, "cf_model_enabled", False)

    import importlib
    import app.services.cf_service as cf_mod
    importlib.reload(cf_mod)

    result = cf_mod.score_cf_roles("user_1", ["Software Engineer", "Data Scientist"])
    assert result == {}


def test_score_cf_roles_cold_start(monkeypatch, tmp_path):
    """Unknown user falls back to column means and returns normalised scores."""
    from app.config import settings
    monkeypatch.setattr(settings, "cf_model_enabled", True)
    monkeypatch.setattr(settings, "cf_model_artifact_path", str(tmp_path))

    # Build a minimal fake artefact.
    roles = ["Software Engineer", "Data Scientist", "UX Designer"]
    fake_artefact = {
        "user_index": ["known_user"],
        "role_index": roles,
        "col_means": np.array([0.8, 0.3, 0.5], dtype=np.float32),
        "reconstructed": np.array([[0.9, 0.2, 0.6]], dtype=np.float32),
    }
    model_path = tmp_path / "cf_model.pkl"
    with model_path.open("wb") as fh:
        pickle.dump(fake_artefact, fh)

    import importlib
    import app.services.cf_service as cf_mod
    # Reset module-level cache to force reload.
    cf_mod._CF_CACHE = None
    cf_mod._CF_LOAD_ATTEMPTED = False

    result = cf_mod.score_cf_roles("unknown_user", roles)
    assert set(result.keys()) == set(roles)
    # All values in [0, 1].
    assert all(0.0 <= v <= 1.0 for v in result.values())


def test_score_cf_roles_known_user(monkeypatch, tmp_path):
    """Known user gets their reconstructed row, cold-start user gets column means."""
    from app.config import settings
    monkeypatch.setattr(settings, "cf_model_enabled", True)
    monkeypatch.setattr(settings, "cf_model_artifact_path", str(tmp_path))

    roles = ["Software Engineer", "Data Scientist"]
    fake_artefact = {
        "user_index": ["alice"],
        "role_index": roles,
        "col_means": np.array([0.4, 0.4], dtype=np.float32),
        "reconstructed": np.array([[1.0, 0.0]], dtype=np.float32),
    }
    model_path = tmp_path / "cf_model.pkl"
    with model_path.open("wb") as fh:
        pickle.dump(fake_artefact, fh)

    import importlib
    import app.services.cf_service as cf_mod
    cf_mod._CF_CACHE = None
    cf_mod._CF_LOAD_ATTEMPTED = False

    result = cf_mod.score_cf_roles("alice", roles)
    # After min-max normalisation of [1.0, 0.0]: SE → 1.0, DS → 0.0.
    assert result["Software Engineer"] == 1.0
    assert result["Data Scientist"] == 0.0


# ---------------------------------------------------------------------------
# Bandit service tests
# ---------------------------------------------------------------------------

def test_rerank_recommendations_disabled(monkeypatch):
    """Bandit disabled → original order preserved."""
    from app.config import settings
    monkeypatch.setattr(settings, "bandit_enabled", False)

    import importlib
    import app.services.bandit_service as bandit_mod
    importlib.reload(bandit_mod)

    roles = ["A", "B", "C"]
    assert bandit_mod.rerank_recommendations(roles) == roles


def test_rerank_exploit_uses_arm_mean(monkeypatch, tmp_path):
    """Exploitation path sorts by descending arm mean."""
    from app.config import settings
    monkeypatch.setattr(settings, "bandit_enabled", True)
    monkeypatch.setattr(settings, "bandit_artifact_path", str(tmp_path))
    monkeypatch.setattr(settings, "bandit_epsilon", 0.0)  # always exploit

    import importlib
    import app.services.bandit_service as bandit_mod
    importlib.reload(bandit_mod)

    # Seed state: C is best, then A, then B.
    state = {
        "A": {"count": 10, "reward_sum": 7.0},   # mean 0.7
        "B": {"count": 10, "reward_sum": 3.0},   # mean 0.3
        "C": {"count": 10, "reward_sum": 9.0},   # mean 0.9
    }
    bandit_mod._BANDIT_STATE = state

    rng = random.Random(0)
    result = bandit_mod.rerank_recommendations(["A", "B", "C"], rng=rng)
    assert result == ["C", "A", "B"]


def test_record_feedback_updates_state(monkeypatch, tmp_path):
    """record_feedback correctly increments count and reward_sum."""
    from app.config import settings
    monkeypatch.setattr(settings, "bandit_enabled", True)
    monkeypatch.setattr(settings, "bandit_artifact_path", str(tmp_path))

    import importlib
    import app.services.bandit_service as bandit_mod
    importlib.reload(bandit_mod)
    bandit_mod._BANDIT_STATE = {}

    bandit_mod.record_feedback("Software Engineer", helpful=True, rating=5)
    state = bandit_mod._BANDIT_STATE
    arm = state.get("Software Engineer", {})
    assert arm["count"] == 1
    # reward = 0.5 * 1.0 + 0.5 * (5-1)/4 = 0.5 + 0.5 = 1.0
    assert abs(arm["reward_sum"] - 1.0) < 1e-6
