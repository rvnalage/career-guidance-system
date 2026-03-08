from fastapi import APIRouter

from app.services.llm_service import get_llm_runtime_status

router = APIRouter()


@router.get("/status")
async def llm_status() -> dict[str, object]:
	return get_llm_runtime_status()
