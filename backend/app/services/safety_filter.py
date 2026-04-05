"""LLM reply safety filter.

Screens generated text for content that falls outside the career guidance
domain or could cause harm before it is returned to the user.

Design
------
- Pure-Python, no ML dependencies — safe to import unconditionally.
- Three check layers, applied in order:
    1. Harmful / sensitive topic patterns (block and replace with fallback).
    2. Off-topic patterns (warn and replace with fallback).
    3. Repetition guard (truncate if the same phrase repeats excessively).
- Configurable via env flag `SAFETY_FILTER_ENABLED` (default True).
- Returns a `SafetyResult` named tuple: (text, blocked, reason).

All patterns are lower-cased regex strings compiled once at import.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Patterns that trigger an immediate block and replacement.
_HARMFUL_PATTERNS: list[tuple[str, str]] = [
    # (compiled_pattern_src, reason_label)
    (r"\b(suicide|self[- ]harm|kill (myself|yourself|himself|herself))\b", "self_harm"),
    (r"\b(hack|exploit|sql injection|xss|malware|ransomware|phishing)\b", "security_attack"),
    (r"\b(illegal|piracy|crack (the )?software|warez)\b", "illegal_content"),
    (r"\b(sexual|pornograph|nude|naked|explicit content)\b", "explicit_content"),
    (r"\b(drug|narcotic|cocaine|heroin|meth(amphetamine)?)\b", "controlled_substance"),
    (r"\b(bomb|terrorist|weapon|firearm|assassination)\b", "violence"),
]

# Patterns that suggest the reply drifted away from career guidance.
_OFFTOPIC_PATTERNS: list[tuple[str, str]] = [
    (r"\b(recipe|cooking|ingredient|bake|fry)\b", "cooking"),
    (r"\b(sports score|football match|cricket|nba|nfl game)\b", "sports_news"),
    (r"\b(stock price|crypto|bitcoin|trading signal)\b", "finance_trading"),
    (r"\b(celebrity gossip|movie review|box office)\b", "entertainment"),
    (r"\b(political party|vote for|election result)\b", "politics"),
    (r"\b(relationship advice|dating|marriage counseling)\b", "personal_relationships"),
]

# Safety-rail fallback text when a reply is blocked.
_BLOCK_FALLBACK = (
    "I'm here to help with career guidance topics such as career planning, skill development, "
    "and job search strategies. Please ask me something related to your career goals."
)

# Off-topic soft fallback — appended as a redirect, not a full replacement.
_OFFTOPIC_REDIRECT = (
    " (I noticed this may be outside my career guidance scope. "
    "Feel free to ask me about career paths, skills, or interview preparation.)"
)

# Maximum times a trigram (3-word window) may repeat before truncation.
_MAX_TRIGRAM_REPEATS = 4


# ---------------------------------------------------------------------------
# Pre-compile all patterns
# ---------------------------------------------------------------------------

_HARMFUL_COMPILED = [
    (re.compile(pattern, re.IGNORECASE), label)
    for pattern, label in _HARMFUL_PATTERNS
]
_OFFTOPIC_COMPILED = [
    (re.compile(pattern, re.IGNORECASE), label)
    for pattern, label in _OFFTOPIC_PATTERNS
]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class SafetyResult(NamedTuple):
    text: str
    blocked: bool
    reason: Optional[str]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_harmful(text: str) -> Optional[str]:
    for pattern, label in _HARMFUL_COMPILED:
        if pattern.search(text):
            return label
    return None


def _check_offtopic(text: str) -> Optional[str]:
    for pattern, label in _OFFTOPIC_COMPILED:
        if pattern.search(text):
            return label
    return None


def _check_repetition(text: str) -> str:
    """Truncate text at the point where a trigram repeats too many times."""
    words = text.split()
    if len(words) < 6:
        return text
    trigram_counts: dict[tuple[str, ...], int] = {}
    for i in range(len(words) - 2):
        trigram = (words[i].lower(), words[i + 1].lower(), words[i + 2].lower())
        trigram_counts[trigram] = trigram_counts.get(trigram, 0) + 1
        if trigram_counts[trigram] >= _MAX_TRIGRAM_REPEATS:
            truncated = " ".join(words[: i + 3])
            logger.debug("Safety filter truncated repetitive text at word index %d.", i)
            return truncated
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_safety_filter(text: str) -> SafetyResult:
    """Screen *text* through all safety layers and return a SafetyResult.

    If `SAFETY_FILTER_ENABLED` is False, returns the input unchanged.
    """
    if not settings.safety_filter_enabled:
        return SafetyResult(text=text, blocked=False, reason=None)

    if not text or not text.strip():
        return SafetyResult(text=text, blocked=False, reason=None)

    # Layer 1: harmful content — full replacement.
    harmful_label = _check_harmful(text)
    if harmful_label:
        logger.warning("Safety filter blocked reply (reason=%s).", harmful_label)
        return SafetyResult(text=_BLOCK_FALLBACK, blocked=True, reason=harmful_label)

    # Layer 2: off-topic — soft redirect appended.
    offtopic_label = _check_offtopic(text)
    if offtopic_label:
        logger.info("Safety filter flagged off-topic reply (reason=%s).", offtopic_label)
        redirected = text.rstrip() + _OFFTOPIC_REDIRECT
        return SafetyResult(text=redirected, blocked=False, reason=f"offtopic:{offtopic_label}")

    # Layer 3: repetition guard.
    cleaned = _check_repetition(text)

    return SafetyResult(text=cleaned, blocked=False, reason=None)
