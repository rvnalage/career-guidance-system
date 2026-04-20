"""Chat history persistence helpers backed by MongoDB with an in-memory fallback.

Developer Onboarding Notes:
- Layer: history persistence service
- Role in system: Stores assistant/user turns and exposes resilient read/clear helpers.
- Main callers: chat routes, auth-protected history endpoints, and telemetry aggregation flows.
- Reading tip: Start from `append_message`, then inspect `get_user_history` and `clear_user_history`.
"""


from datetime import datetime, timezone
from typing import Any

from app.database.mongo_db import get_history_collection

_history_fallback: dict[str, list[dict[str, Any]]] = {}


async def append_message(
	user_id: str,
	role: str,
	text: str,
	metadata: dict[str, Any] | None = None,
) -> None:
	"""Append one chat turn to persistent storage and fallback cache.

	Args:
		user_id: History owner.
		role: Message role such as `user` or `assistant`.
		text: Turn content stored for replay and analytics.
		metadata: Optional extra fields such as RAG metrics or citations.

	Significance:
		Primary write path for conversation memory. Always mirrors into in-memory fallback
		so tests and degraded storage conditions still preserve chronology.

	Used by:
		Chat route persistence flow and history seeding in tests.
	"""
	document = {
		"user_id": user_id,
		"role": role,
		"text": text,
		"timestamp": datetime.now(timezone.utc).isoformat(),
	}
	if metadata:
		document.update(metadata)
	# Always mirror to fallback for resilience when async event loops differ across test client requests.
	_history_fallback.setdefault(user_id, []).append(dict(document))
	try:
		collection = get_history_collection()
		await collection.insert_one(document)
	except Exception:
		return


async def get_user_history(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
	"""Return recent chat history in chronological order.

	Significance:
		Canonical history read path for UI replay, planner memory loading, and telemetry.

	Used by:
		History endpoints and RAG telemetry aggregation.
	"""
	try:
		collection = get_history_collection()
		cursor = collection.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
		documents = await cursor.to_list(length=limit)
		for item in documents:
			item.pop("_id", None)
		if documents:
			return list(reversed(documents))
		# If persistent store returns empty, fall back to in-memory cache used in tests/degraded mode.
		return _history_fallback.get(user_id, [])[-limit:]
	except Exception:
		return _history_fallback.get(user_id, [])[-limit:]


async def clear_user_history(user_id: str) -> int:
	"""Delete stored chat history and return removed message count.

	Significance:
		Supports user-facing reset flows while keeping fallback cache consistent with
		persistent storage deletions.

	Used by:
		Authenticated history-clear endpoints.
	"""
	deleted_count = 0
	try:
		collection = get_history_collection()
		result = await collection.delete_many({"user_id": user_id})
		deleted_count = int(result.deleted_count)
	except Exception:
		deleted_count = len(_history_fallback.get(user_id, []))

	_history_fallback[user_id] = []
	return deleted_count

