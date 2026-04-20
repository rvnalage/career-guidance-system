"""Keyword-based intent detection for routing chat messages to specialized agents.

The recognizer deliberately uses deterministic scoring so behavior is predictable,
easy to test, and simple to tune without retraining a separate classifier.
"""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


INTENT_KEYWORDS = {
	# Order matters here: more specific intents should appear before broader keyword buckets such as job matching.
	"interview_prep": ["interview", "hr round", "technical round", "mock"],
	"learning_path": ["learn", "roadmap", "course", "upskill", "study plan"],
	"recommendation": ["recommend", "recommendation", "suggest", "best role", "career option"],
	"job_matching": ["job", "role", "match", "fit", "eligibility"],
	"networking": ["network", "linkedin", "referral", "mentor", "outreach"],
	"feedback": ["feedback", "rate", "rating", "helpful", "not helpful"],
}


def detect_intent_with_confidence(message: str) -> tuple[str, float, list[str]]:
	"""Return the best-matching intent, its confidence score, and matched keywords."""
	normalized = message.lower().strip()
	if not normalized:
		return "career_assessment", 0.0, []

	best_intent = "career_assessment"
	best_score = 0.0
	best_matches: list[str] = []
	for intent, keywords in INTENT_KEYWORDS.items():
		matches = [keyword for keyword in keywords if keyword in normalized]
		if not matches:
			continue

		# Confidence is intentionally simple and deterministic so routing stays testable and easy to tune.
		keyword_hit_ratio = len(matches) / max(1, len(keywords))
		coverage_bonus = min(0.35, 0.12 * len(matches))
		score = min(1.0, 0.45 + keyword_hit_ratio + coverage_bonus)
		if score > best_score:
			best_intent = intent
			best_score = score
			best_matches = matches

	if best_score == 0.0:
		# Low-signal text still gets a non-zero score so callers can distinguish "no match" from an empty message.
		return "career_assessment", 0.15, []
	return best_intent, round(best_score, 4), best_matches


def detect_intent(message: str) -> str:
	"""Return only the winning intent name for callers that do not need score details."""
	intent, _, _ = detect_intent_with_confidence(message)
	return intent

