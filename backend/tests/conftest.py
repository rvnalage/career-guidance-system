import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def _stabilize_test_runtime():
	"""Keep tests deterministic by disabling optional local LLM calls."""
	original_llm_enabled = settings.llm_enabled
	original_require_rag = settings.llm_require_rag_context
	original_rag_enabled = settings.rag_enabled
	settings.llm_enabled = False
	settings.llm_require_rag_context = True
	settings.rag_enabled = True
	try:
		yield
	finally:
		settings.llm_enabled = original_llm_enabled
		settings.llm_require_rag_context = original_require_rag
		settings.rag_enabled = original_rag_enabled


@pytest.fixture
def client() -> TestClient:
	return TestClient(app)
