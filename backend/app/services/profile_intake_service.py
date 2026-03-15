"""Helpers for extracting profile signals from uploaded user files."""

from __future__ import annotations

import re
from typing import Any

from app.services.profile_service import ROLE_HINTS, SKILL_BANK
from app.utils.constants import CAREER_PATHS

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}
PSYCHOMETRIC_KEYS = {
	"investigative",
	"realistic",
	"artistic",
	"social",
	"enterprising",
	"conventional",
}
EDUCATION_KEYWORDS = {
	"phd": "phd",
	"doctorate": "phd",
	"master": "master",
	"mtech": "master",
	"bachelor": "bachelor",
	"btech": "bachelor",
	"diploma": "diploma",
	"high school": "high_school",
}


def _normalize_list(items: list[str]) -> list[str]:
	seen: set[str] = set()
	values: list[str] = []
	for item in items:
		text = str(item).strip().lower()
		if text and text not in seen:
			seen.add(text)
			values.append(text)
	return values


def _find_target_role(text: str) -> str | None:
	lower_text = text.lower()
	for role, hints in ROLE_HINTS.items():
		if any(hint in lower_text for hint in hints):
			return role
	return None


def _find_education(text: str) -> str | None:
	lower_text = text.lower()
	for keyword, normalized in EDUCATION_KEYWORDS.items():
		if keyword in lower_text:
			return normalized
	return None


def _find_skills_and_interests(text: str) -> tuple[list[str], list[str]]:
	lower_text = text.lower()
	skills = [skill for skill in SKILL_BANK if skill in lower_text]

	known_interests: set[str] = set()
	for path in CAREER_PATHS:
		for interest in path["related_interests"]:
			known_interests.add(str(interest).lower())
	interests = [interest for interest in known_interests if interest in lower_text]
	return _normalize_list(skills), _normalize_list(interests)


def _find_psychometric_dimensions(text: str) -> dict[str, int]:
	"""Parse simple `trait: score` or `trait = score` patterns from free text."""
	parsed: dict[str, int] = {}
	for match in re.finditer(r"([a-zA-Z_ ]+)\s*[:=]\s*([1-5])", text):
		trait = match.group(1).strip().lower()
		value = int(match.group(2))
		if trait in PSYCHOMETRIC_KEYS:
			parsed[trait] = value
	return parsed


def extract_profile_signals(text: str) -> dict[str, Any]:
	"""Extract structured profile fields from unstructured text."""
	target_role = _find_target_role(text)
	education_level = _find_education(text)
	skills, interests = _find_skills_and_interests(text)
	psychometric_dimensions = _find_psychometric_dimensions(text)
	return {
		"skills": skills,
		"interests": interests,
		"target_role": target_role,
		"education_level": education_level,
		"psychometric_dimensions": psychometric_dimensions,
	}


def merge_extracted_signals(items: list[dict[str, Any]]) -> dict[str, Any]:
	"""Combine extracted signals from multiple files into one profile candidate."""
	skills: list[str] = []
	interests: list[str] = []
	target_role: str | None = None
	education_level: str | None = None
	psychometric_dimensions: dict[str, int] = {}

	for item in items:
		skills.extend(item.get("skills", []))
		interests.extend(item.get("interests", []))
		if not target_role and item.get("target_role"):
			target_role = item["target_role"]
		if not education_level and item.get("education_level"):
			education_level = item["education_level"]
		for key, value in item.get("psychometric_dimensions", {}).items():
			psychometric_dimensions[key] = int(value)

	return {
		"skills": _normalize_list(skills),
		"interests": _normalize_list(interests),
		"target_role": target_role,
		"education_level": education_level,
		"psychometric_dimensions": psychometric_dimensions,
	}