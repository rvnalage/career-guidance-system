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
	openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
	openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
	openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
	openai_max_tokens: int = Field(default=260, alias="OPENAI_MAX_TOKENS")
	groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
	groq_model: str = Field(default="llama-3.1-8b-instant", alias="GROQ_MODEL")
	groq_max_tokens: int = Field(default=512, alias="GROQ_MAX_TOKENS")
	llm_auto_fallback_to_openai: bool = Field(default=False, alias="LLM_AUTO_FALLBACK_TO_OPENAI")
	llm_request_timeout_seconds: int = Field(default=15, alias="LLM_REQUEST_TIMEOUT_SECONDS")
	llm_require_rag_context: bool = Field(default=True, alias="LLM_REQUIRE_RAG_CONTEXT")
	llm_ollama_num_predict: int = Field(default=96, alias="LLM_OLLAMA_NUM_PREDICT")
	llm_rag_context_max_chars: int = Field(default=1400, alias="LLM_RAG_CONTEXT_MAX_CHARS")
	chat_reply_max_sentences: int = Field(default=8, alias="CHAT_REPLY_MAX_SENTENCES")
	intent_min_confidence: float = Field(default=0.35, alias="INTENT_MIN_CONFIDENCE")
	intent_model_enabled: bool = Field(default=False, alias="INTENT_MODEL_ENABLED")
	intent_model_artifact_dir: str = Field(
		default="ml-models/pretrained/intent_model",
		alias="INTENT_MODEL_ARTIFACT_DIR",
	)
	intent_model_min_confidence: float = Field(default=0.5, alias="INTENT_MODEL_MIN_CONFIDENCE")
	user_preference_model_enabled: bool = Field(default=False, alias="USER_PREFERENCE_MODEL_ENABLED")
	user_preference_model_artifact_path: str = Field(
		default="ml-models/pretrained/user_modeling/user_preference_model.pkl",
		alias="USER_PREFERENCE_MODEL_ARTIFACT_PATH",
	)
	user_preference_model_alpha: float = Field(default=0.35, alias="USER_PREFERENCE_MODEL_ALPHA")
	psychometric_model_enabled: bool = Field(default=False, alias="PSYCHOMETRIC_MODEL_ENABLED")
	psychometric_model_artifact_path: str = Field(
		default="ml-models/pretrained/psychometric_model/psychometric_model.pkl",
		alias="PSYCHOMETRIC_MODEL_ARTIFACT_PATH",
	)
	cf_model_enabled: bool = Field(default=False, alias="CF_MODEL_ENABLED")
	cf_model_artifact_path: str = Field(
		default="ml-models/pretrained/cf_model",
		alias="CF_MODEL_ARTIFACT_PATH",
	)
	cf_model_alpha: float = Field(default=0.25, alias="CF_MODEL_ALPHA")
	bandit_enabled: bool = Field(default=False, alias="BANDIT_ENABLED")
	bandit_artifact_path: str = Field(
		default="ml-models/pretrained/bandit",
		alias="BANDIT_ARTIFACT_PATH",
	)
	bandit_epsilon: float = Field(default=0.1, alias="BANDIT_EPSILON")
	safety_filter_enabled: bool = Field(default=True, alias="SAFETY_FILTER_ENABLED")

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
