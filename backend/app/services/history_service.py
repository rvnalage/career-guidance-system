"""Chat history persistence helpers backed by MongoDB with an in-memory fallback."""

from datetime import datetime, timezone
from typing import Any

from app.database.mongo_db import get_history_collection

_history_fallback: dict[str, list[dict[str, Any]]] = {}


async def append_message(user_id: str, role: str, text: str) -> None:
	"""Append a chat turn to persistent history or the fallback cache."""
	document = {
		"user_id": user_id,
		"role": role,
		"text": text,
		"timestamp": datetime.now(timezone.utc).isoformat(),
	}
	try:
		collection = get_history_collection()
		await collection.insert_one(document)
	except Exception:
		_history_fallback.setdefault(user_id, []).append(document)


async def get_user_history(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
	"""Return recent chat history in chronological order for a specific user."""
	try:
		collection = get_history_collection()
		cursor = collection.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
		documents = await cursor.to_list(length=limit)
		for item in documents:
			item.pop("_id", None)
		return list(reversed(documents))
	except Exception:
		return _history_fallback.get(user_id, [])[-limit:]


async def clear_user_history(user_id: str) -> int:
	"""Delete stored chat history for a user and return the number of removed messages."""
	deleted_count = 0
	try:
		collection = get_history_collection()
		result = await collection.delete_many({"user_id": user_id})
		deleted_count = int(result.deleted_count)
	except Exception:
		deleted_count = len(_history_fallback.get(user_id, []))

	_history_fallback[user_id] = []
	return deleted_count
