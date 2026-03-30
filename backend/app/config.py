"""Central application settings loaded from environment variables and .env files."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
	"""Typed runtime configuration for API, storage, retrieval, and authentication behavior."""
	model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

	app_name: str = "Career Guidance System API"
	app_version: str = "0.1.0"
	environment: str = Field(default="development", alias="ENV")
	api_v1_prefix: str = "/api/v1"
	cors_origins: Annotated[List[str], NoDecode] = [
		"http://localhost:3000",
		"http://127.0.0.1:3000",
		"http://localhost:5173",
		"http://127.0.0.1:5173",
	]

	database_url: str = Field(default="postgresql://postgres:rahulpg@localhost:5432/postgres")
	mongodb_url: str = Field(default="mongodb://localhost:27017")
	redis_url: str = Field(default="redis://localhost:6379/0")
	mongodb_database: str = "career_chat_history"
	mongodb_history_collection: str = "chat_history"
	mongodb_recommendation_collection: str = "recommendation_history"
	mongodb_feedback_collection: str = "recommendation_feedback"
	mongodb_psychometric_collection: str = "psychometric_profiles"
	mongodb_user_profile_collection: str = "user_profiles"

	job_market_api_url: str = "https://remotive.com/api/remote-jobs"
	rag_enabled: bool = Field(default=True, alias="RAG_ENABLED")
	rag_top_k: int = Field(default=4, alias="RAG_TOP_K")
	rag_candidate_pool_size: int = Field(default=20, alias="RAG_CANDIDATE_POOL_SIZE")
	llm_enabled: bool = Field(default=False, alias="LLM_ENABLED")
	llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
	llm_base_url: str = Field(default="http://localhost:11434", alias="LLM_BASE_URL")
	llm_model: str = Field(default="llama3.1:8b", alias="LLM_MODEL")
	llm_finetuned_model: str = Field(default="", alias="LLM_FINETUNED_MODEL")
	llm_request_timeout_seconds: int = Field(default=15, alias="LLM_REQUEST_TIMEOUT_SECONDS")
	llm_require_rag_context: bool = Field(default=True, alias="LLM_REQUIRE_RAG_CONTEXT")
	chat_reply_max_sentences: int = Field(default=8, alias="CHAT_REPLY_MAX_SENTENCES")
	intent_min_confidence: float = Field(default=0.35, alias="INTENT_MIN_CONFIDENCE")

	jwt_secret_key: str = "change-me-in-production"
	jwt_algorithm: str = "HS256"
	access_token_expire_minutes: int = 60

	@field_validator("cors_origins", mode="before")
	@classmethod
	def parse_cors_origins(cls, value: str | List[str]) -> List[str]:
		"""Accept CORS origins from either JSON list syntax or comma-separated text."""
		if isinstance(value, list):
			return value
		if isinstance(value, str):
			text = value.strip()
			if text.startswith("["):
				try:
					parsed = json.loads(text)
					if isinstance(parsed, list):
						return [str(origin).strip() for origin in parsed if str(origin).strip()]
				except json.JSONDecodeError:
					pass
			return [origin.strip() for origin in text.split(",") if origin.strip()]
		return []


@lru_cache
def get_settings() -> Settings:
	"""Return a cached Settings instance so configuration is parsed only once per process."""
	return Settings()


settings = get_settings()
