"""Query normalization helpers that expand shorthand terms before retrieval."""

from __future__ import annotations

import re


_SYNONYM_MAP: dict[str, str] = {
	"ai": "machine learning",
	"ml": "machine learning",
	"m l": "machine learning",
	"devops": "cloud devops",
	"ui ux": "ui ux designer",
	"ux": "ui ux",
	"ms": "master",
	"mtech": "master",
	"resume": "portfolio",
	"cv": "portfolio",
	"job prep": "interview preparation",
}


def rewrite_query(query: str) -> str:
	"""Normalize shorthand and synonyms to improve retrieval recall."""
	text = " ".join(query.lower().strip().split())
	if not text:
		return ""

	for source, target in _SYNONYM_MAP.items():
		text = re.sub(rf"\b{re.escape(source)}\b", target, text)

	return text
