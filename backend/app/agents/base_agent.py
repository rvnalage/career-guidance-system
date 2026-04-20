"""Shared agent contract and lightweight extraction helpers for chat routing.

Concrete agents inherit these utility methods so role, skill, and timeline parsing
behavior stays consistent across different intent-specific response generators.
"""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
	name: str = "base"

	@abstractmethod
	def respond(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Return a domain-specific guidance response for the incoming message."""

	@abstractmethod
	def suggested_next_step(self, message: str, context: dict[str, Any] | None = None) -> str:
		"""Return the recommended next user action for this agent context."""

	def _normalized_text(self, message: str) -> str:
		"""Lowercase and trim message text before keyword extraction."""
		return message.lower().strip()

	def _extract_target_role(self, message: str, context: dict[str, Any] | None = None) -> str | None:
		"""Resolve the user's target role from explicit context first, then message text."""
		if context and isinstance(context.get("target_role"), str):
			role = context["target_role"].strip()
			if role:
				return role

		text = self._normalized_text(message)
		role_map = {
			"data scientist": ["data scientist", "data science"],
			"data analyst": ["data analyst", "analytics"],
			"data engineer": ["data engineer", "etl", "pipeline"],
			"ml engineer": ["ml engineer", "machine learning engineer", "mle"],
			"product analyst": ["product analyst", "product analytics"],
			"devops engineer": ["devops", "sre", "site reliability"],
			"ui/ux designer": ["ui/ux", "ux designer", "product designer"],
		}

		for role, keywords in role_map.items():
			if any(keyword in text for keyword in keywords):
				return role
		return None

	def _extract_timeline_weeks(self, message: str, context: dict[str, Any] | None = None) -> int | None:
		"""Infer a planning horizon in weeks from structured context or free-text time expressions."""
		if context and isinstance(context.get("timeline_weeks"), int):
			weeks = int(context["timeline_weeks"])
			if weeks > 0:
				return weeks

		text = self._normalized_text(message)
		match = re.search(r"(\d{1,2})\s*(week|weeks)", text)
		if match:
			return int(match.group(1))
		match = re.search(r"(\d{1,2})\s*(month|months)", text)
		if match:
			return int(match.group(1)) * 4
		return None

	def _extract_skill_keywords(self, message: str, context: dict[str, Any] | None = None) -> list[str]:
		"""Collect known skill tokens from context and message text for response personalization."""
		skills: list[str] = []
		if context and isinstance(context.get("skills"), list):
			for item in context["skills"]:
				text = str(item).strip().lower()
				if text:
					skills.append(text)

		text = self._normalized_text(message)
		skill_bank = [
			"python",
			"sql",
			"excel",
			"power bi",
			"tableau",
			"statistics",
			"machine learning",
			"deep learning",
			"nlp",
			"communication",
			"system design",
			"docker",
			"kubernetes",
			"aws",
		]
		for skill in skill_bank:
			if skill in text and skill not in skills:
				skills.append(skill)
		return skills

	def _extract_target_companies(self, context: dict[str, Any] | None = None) -> list[str]:
		"""Return cleaned target-company values when the client provides them in context."""
		if not context:
			return []
		companies = context.get("target_companies")
		if not isinstance(companies, list):
			return []
		result: list[str] = []
		for company in companies:
			text = str(company).strip()
			if text:
				result.append(text)
		return result

