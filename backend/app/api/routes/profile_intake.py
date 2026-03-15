"""Profile intake routes for extracting user context from uploaded files."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.database.models import User
from app.dependencies import get_current_user
from app.schemas.profile_intake import ExtractedProfile, ProfileIntakeResponse
from app.schemas.psychometric import PsychometricRequest
from app.services.profile_intake_service import (
	SUPPORTED_TEXT_EXTENSIONS,
	extract_profile_signals,
	merge_extracted_signals,
)
from app.services.profile_service import apply_profile_patch
from app.services.psychometric_service import save_user_psychometric_profile

router = APIRouter()


@router.post("/upload", response_model=ProfileIntakeResponse)
async def upload_profile_files(
	files: list[UploadFile] = File(...),
	owner_type: Literal["self", "on_behalf"] = Form("self"),
	current_user: User = Depends(get_current_user),
) -> ProfileIntakeResponse:
	"""Extract profile hints from uploaded files and persist only in self mode."""
	parsed_items: list[dict] = []
	skipped_files: list[str] = []

	for file in files:
		ext = Path(file.filename or "").suffix.lower()
		if ext not in SUPPORTED_TEXT_EXTENSIONS:
			skipped_files.append(file.filename or "unknown")
			continue

		payload = await file.read()
		text = payload.decode("utf-8", errors="ignore")
		if not text.strip():
			skipped_files.append(file.filename or "unknown")
			continue
		parsed_items.append(extract_profile_signals(text))

	aggregated = merge_extracted_signals(parsed_items)
	persisted = False

	if owner_type == "self":
		await apply_profile_patch(current_user.id, aggregated)
		if aggregated.get("psychometric_dimensions"):
			await save_user_psychometric_profile(
				current_user.id,
				PsychometricRequest(dimensions=aggregated["psychometric_dimensions"]),
			)
		persisted = True

	return ProfileIntakeResponse(
		owner_type=owner_type,
		files_processed=len(parsed_items),
		skipped_files=skipped_files,
		extracted_profile=ExtractedProfile(**aggregated),
		persisted_to_user_profile=persisted,
		message=(
			"Profile updated from uploaded files"
			if persisted
			else "Parsed upload for on_behalf mode. No changes were saved to your profile."
		),
	)