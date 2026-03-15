"""Schemas for profile signal extraction from uploaded files."""

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedProfile(BaseModel):
	"""Structured profile fields inferred from uploaded documents."""
	skills: list[str] = Field(default_factory=list)
	interests: list[str] = Field(default_factory=list)
	target_role: str | None = None
	education_level: str | None = None
	psychometric_dimensions: dict[str, int] = Field(default_factory=dict)


class ProfileIntakeResponse(BaseModel):
	"""Response describing extracted profile data and persistence outcome."""
	owner_type: Literal["self", "on_behalf"]
	files_processed: int
	skipped_files: list[str] = Field(default_factory=list)
	extracted_profile: ExtractedProfile
	persisted_to_user_profile: bool
	message: str