"""Tests for the LLM reply safety filter."""

from __future__ import annotations


def test_harmful_content_is_blocked(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "safety_filter_enabled", True)

    from app.services.safety_filter import apply_safety_filter

    result = apply_safety_filter("Here's how to perform a SQL injection attack on the login form.")
    assert result.blocked is True
    assert result.reason == "security_attack"
    # Fallback text should be career-guidance themed.
    assert "career" in result.text.lower()


def test_offtopic_content_gets_redirect(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "safety_filter_enabled", True)

    from app.services.safety_filter import apply_safety_filter

    result = apply_safety_filter("The best recipe for pasta carbonara uses guanciale and pecorino.")
    assert result.blocked is False
    assert result.reason is not None and "offtopic" in result.reason
    assert "career" in result.text.lower()


def test_clean_career_text_passes_through(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "safety_filter_enabled", True)

    from app.services.safety_filter import apply_safety_filter

    text = "To become a Data Scientist, focus on Python, statistics, and machine learning fundamentals."
    result = apply_safety_filter(text)
    assert result.blocked is False
    assert result.reason is None
    assert result.text == text


def test_disabled_filter_returns_input_unchanged(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "safety_filter_enabled", False)

    from app.services.safety_filter import apply_safety_filter

    harmful_text = "how to hack a system using malware"
    result = apply_safety_filter(harmful_text)
    assert result.text == harmful_text
    assert result.blocked is False


def test_repetition_guard_truncates(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "safety_filter_enabled", True)

    from app.services.safety_filter import apply_safety_filter

    # Repeat a trigram 5 times (above threshold of 4).
    phrase = "learn new skills"
    repeated = (phrase + " ") * 5 + "and grow professionally."
    result = apply_safety_filter(repeated)
    assert len(result.text) < len(repeated)
    assert result.blocked is False
