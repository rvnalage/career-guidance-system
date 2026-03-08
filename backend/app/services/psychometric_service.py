from app.schemas.psychometric import PsychometricRequest
from app.database.mongo_db import get_psychometric_collection


_DOMAIN_MAP = {
	"investigative": ["Data Science", "AI/ML", "Research"],
	"realistic": ["DevOps", "Embedded Systems", "Cloud Operations"],
	"artistic": ["UI/UX", "Content Design", "Creative Technology"],
	"social": ["Counseling", "Teaching", "People Operations"],
	"enterprising": ["Product Management", "Business Analysis", "Consulting"],
	"conventional": ["Finance Analytics", "Operations", "QA Process"],
}


def score_psychometric(payload: PsychometricRequest) -> tuple[dict[str, float], list[str], list[str]]:
	normalized_scores: dict[str, float] = {}
	for key, value in payload.dimensions.items():
		bounded = max(1, min(5, int(value)))
		normalized_scores[key.lower().strip()] = round(((bounded - 1) / 4) * 100, 2)

	if not normalized_scores:
		return {}, [], []

	sorted_traits = sorted(normalized_scores.items(), key=lambda item: item[1], reverse=True)
	top_traits = [trait for trait, _ in sorted_traits[:3]]

	domains: list[str] = []
	for trait in top_traits:
		for domain in _DOMAIN_MAP.get(trait, []):
			if domain not in domains:
				domains.append(domain)

	return normalized_scores, top_traits, domains[:5]


_psychometric_fallback: dict[str, dict] = {}


async def save_user_psychometric_profile(user_id: str, payload: PsychometricRequest) -> dict:
	normalized_scores, top_traits, recommended_domains = score_psychometric(payload)
	document = {
		"user_id": user_id,
		"normalized_scores": normalized_scores,
		"top_traits": top_traits,
		"recommended_domains": recommended_domains,
	}
	try:
		collection = get_psychometric_collection()
		await collection.update_one({"user_id": user_id}, {"$set": document}, upsert=True)
	except Exception:
		_psychometric_fallback[user_id] = document
	return document


async def get_user_psychometric_profile(user_id: str) -> dict | None:
	try:
		collection = get_psychometric_collection()
		document = await collection.find_one({"user_id": user_id})
		if document:
			document.pop("_id", None)
			return document
	except Exception:
		pass

	return _psychometric_fallback.get(user_id)
