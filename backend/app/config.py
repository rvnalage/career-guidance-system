from functools import lru_cache
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

	app_name: str = "Career Guidance System API"
	app_version: str = "0.1.0"
	environment: str = Field(default="development", alias="ENV")
	api_v1_prefix: str = "/api/v1"
	cors_origins: Annotated[List[str], NoDecode] = ["http://localhost:3000", "http://127.0.0.1:3000"]

	database_url: str = Field(default="postgresql://postgres:rahulpg@localhost:5432/postgres")
	mongodb_url: str = Field(default="mongodb://localhost:27017")
	redis_url: str = Field(default="redis://localhost:6379/0")
	mongodb_database: str = "career_chat_history"
	mongodb_history_collection: str = "chat_history"
	mongodb_recommendation_collection: str = "recommendation_history"
	mongodb_feedback_collection: str = "recommendation_feedback"
	mongodb_psychometric_collection: str = "psychometric_profiles"

	job_market_api_url: str = "https://remotive.com/api/remote-jobs"
	rag_enabled: bool = Field(default=True, alias="RAG_ENABLED")
	rag_top_k: int = Field(default=2, alias="RAG_TOP_K")
	llm_enabled: bool = Field(default=False, alias="LLM_ENABLED")
	llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
	llm_base_url: str = Field(default="http://localhost:11434", alias="LLM_BASE_URL")
	llm_model: str = Field(default="llama3.1:8b", alias="LLM_MODEL")
	llm_finetuned_model: str = Field(default="", alias="LLM_FINETUNED_MODEL")
	llm_request_timeout_seconds: int = Field(default=15, alias="LLM_REQUEST_TIMEOUT_SECONDS")

	jwt_secret_key: str = "change-me-in-production"
	jwt_algorithm: str = "HS256"
	access_token_expire_minutes: int = 60

	@field_validator("cors_origins", mode="before")
	@classmethod
	def parse_cors_origins(cls, value: str | List[str]) -> List[str]:
		if isinstance(value, list):
			return value
		if isinstance(value, str):
			return [origin.strip() for origin in value.split(",") if origin.strip()]
		return []


@lru_cache
def get_settings() -> Settings:
	return Settings()


settings = get_settings()
