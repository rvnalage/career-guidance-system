from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config import settings

_mongo_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
	global _mongo_client
	if _mongo_client is None:
		_mongo_client = AsyncIOMotorClient(settings.mongodb_url)
	return _mongo_client


def get_history_collection() -> AsyncIOMotorCollection:
	client = get_mongo_client()
	database = client[settings.mongodb_database]
	return database[settings.mongodb_history_collection]


def get_recommendation_collection() -> AsyncIOMotorCollection:
	client = get_mongo_client()
	database = client[settings.mongodb_database]
	return database[settings.mongodb_recommendation_collection]


def get_feedback_collection() -> AsyncIOMotorCollection:
	client = get_mongo_client()
	database = client[settings.mongodb_database]
	return database[settings.mongodb_feedback_collection]


def get_psychometric_collection() -> AsyncIOMotorCollection:
	client = get_mongo_client()
	database = client[settings.mongodb_database]
	return database[settings.mongodb_psychometric_collection]
