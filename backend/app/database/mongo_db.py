"""MongoDB client and collection access helpers used across async services.

The module caches a single Motor client per process and exposes small collection
accessors so callers do not duplicate database-selection logic.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import settings

_mongo_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
	"""Return a lazily initialized shared Motor client for the configured MongoDB URL."""
	global _mongo_client
	if _mongo_client is None:
		_mongo_client = AsyncIOMotorClient(settings.mongodb_url)
	return _mongo_client


def get_history_collection() -> AsyncIOMotorCollection:
	"""Return the chat history collection handle."""
	client = get_mongo_client()
	database = client[settings.mongodb_database]
	return database[settings.mongodb_history_collection]


def get_recommendation_collection() -> AsyncIOMotorCollection:
	"""Return the recommendation snapshot collection handle."""
	client = get_mongo_client()
	database = client[settings.mongodb_database]
	return database[settings.mongodb_recommendation_collection]


def get_feedback_collection() -> AsyncIOMotorCollection:
	"""Return the recommendation feedback collection handle."""
	client = get_mongo_client()
	database = client[settings.mongodb_database]
	return database[settings.mongodb_feedback_collection]


def get_psychometric_collection() -> AsyncIOMotorCollection:
	"""Return the psychometric profile collection handle."""
	client = get_mongo_client()
	database = client[settings.mongodb_database]
	return database[settings.mongodb_psychometric_collection]


def get_user_profile_collection() -> AsyncIOMotorCollection:
	"""Return the persistent chat-profile memory collection handle."""
	client = get_mongo_client()
	database = client[settings.mongodb_database]
	return database[settings.mongodb_user_profile_collection]
