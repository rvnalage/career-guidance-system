"""Query normalization helpers that expand shorthand terms before retrieval."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from __future__ import annotations

import re


_SYNONYM_MAP: dict[str, str] = {
	"ai": "machine learning",
	"ml": "machine learning",
	"m l": "machine learning",
	"data science": "data scientist",
	"data scientist": "data scientist",
	"devops": "cloud devops",
	"ui ux": "ui ux designer",
	"ux": "ui ux",
	"ms": "master",
	"mtech": "master",
	"resume": "portfolio",
	"cv": "portfolio",
	"job prep": "interview preparation",
	"pm": "project manager",
	"dba": "database administrator",
	"ux researcher": "ux researcher",
	"cyber security": "cybersecurity",
	"fpa": "finance analyst",
}


_INTENT_HINTS: dict[str, str] = {
	"interview_prep": "interview preparation technical round hr round mock interview",
	"learning_path": "learning roadmap upskilling study plan milestones",
	"job_matching": "job matching role fit eligibility openings application strategy",
	"networking": "networking outreach referral alumni linkedin informational interview",
	"recommendation": "career recommendation role fit skill alignment",
	"career_assessment": "career assessment strengths interests transition planning",
}


_ROLE_QUERY_HINTS: dict[str, str] = {
	"data scientist": "data scientist",
	"data analyst": "data analyst",
	"ml engineer": "ml engineer",
	"machine learning engineer": "ml engineer",
	"data engineer": "data engineer",
	"backend developer": "backend developer",
	"devops engineer": "devops engineer",
	"ui ux designer": "ui/ux designer",
	"ui ux": "ui/ux designer",
	"product analyst": "product analyst",
	"research scientist": "research scientist",
	"business analyst": "business analyst",
	"digital marketing specialist": "digital marketing specialist",
	"project manager": "project manager",
	"qa automation engineer": "qa automation engineer",
	"cybersecurity analyst": "cybersecurity analyst",
	"ai product manager": "ai product manager",
	"ux researcher": "ux researcher",
	"database administrator": "database administrator",
	"system administrator": "system administrator",
	"technical support specialist": "technical support specialist",
	"operations coordinator": "operations coordinator",
	"finance analyst": "finance analyst",
	"supply chain analyst": "supply chain analyst",
}


def _infer_role_hint_from_query(text: str) -> str | None:
	"""Infer a normalized role hint from free-form query text for better role-aware retrieval."""
	normalized = " ".join(text.lower().split())
	for token, role in _ROLE_QUERY_HINTS.items():
		if token in normalized:
			return role
	return None


def rewrite_query(
	query: str,
	*,
	intent: str | None = None,
	target_role: str | None = None,
	skill_gaps: list[str] | None = None,
) -> str:
	"""Normalize query and append intent/role hints to improve retrieval recall and precision."""
	text = " ".join(query.lower().strip().split())
	if not text:
		return ""

	for source, target in _SYNONYM_MAP.items():
		text = re.sub(rf"\b{re.escape(source)}\b", target, text)

	if intent:
		intent_hint = _INTENT_HINTS.get(intent.strip().lower())
		if intent_hint:
			text = f"{text} {intent_hint}".strip()

	resolved_role = target_role.strip() if isinstance(target_role, str) and target_role.strip() else _infer_role_hint_from_query(text)
	if resolved_role:
		role_text = " ".join(resolved_role.lower().split())
		if role_text:
			text = f"{text} {role_text} role guide".strip()

	if skill_gaps:
		gap_terms = [" ".join(item.lower().split()) for item in skill_gaps if str(item).strip()]
		if gap_terms:
			text = f"{text} {' '.join(gap_terms[:4])}".strip()

	return text

