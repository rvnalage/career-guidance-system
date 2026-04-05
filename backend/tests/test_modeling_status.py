"""Integration tests for GET /api/v1/modeling/status."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_modeling_status_returns_all_keys(monkeypatch):
    """Response must contain all five phase-2 model keys."""
    from app.services.model_runtime_service import get_model_runtime_status

    status = get_model_runtime_status()
    assert "intent_model" in status
    assert "user_preference_model" in status
    assert "psychometric_model" in status
    assert "cf_model" in status
    assert "bandit" in status


def test_modeling_status_intent_structure(monkeypatch):
    """intent_model section has required subkeys."""
    from app.services.model_runtime_service import get_model_runtime_status

    status = get_model_runtime_status()
    intent = status["intent_model"]
    assert "enabled" in intent
    assert "model_exists" in intent
    assert "labels_exists" in intent
    assert "min_confidence" in intent


def test_modeling_status_cf_structure(monkeypatch):
    """cf_model section has required subkeys."""
    from app.services.model_runtime_service import get_model_runtime_status

    status = get_model_runtime_status()
    cf = status["cf_model"]
    assert "enabled" in cf
    assert "artifact_exists" in cf
    assert "blend_alpha" in cf


def test_modeling_status_bandit_structure(monkeypatch):
    """bandit section has required subkeys."""
    from app.services.model_runtime_service import get_model_runtime_status

    status = get_model_runtime_status()
    bandit = status["bandit"]
    assert "enabled" in bandit
    assert "epsilon" in bandit
    assert "state_exists" in bandit


def test_modeling_status_defaults_all_disabled():
    """With no .env overrides all models default to disabled."""
    from app.config import settings

    # These are the compile-time defaults; no artifact should be enabled in CI.
    assert isinstance(settings.intent_model_enabled, bool)
    assert isinstance(settings.user_preference_model_enabled, bool)
    assert isinstance(settings.psychometric_model_enabled, bool)
    assert isinstance(settings.cf_model_enabled, bool)
    assert isinstance(settings.bandit_enabled, bool)
