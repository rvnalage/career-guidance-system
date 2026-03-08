INTENT_KEYWORDS = {
	"interview_prep": ["interview", "hr round", "technical round", "mock"],
	"learning_path": ["learn", "roadmap", "course", "upskill", "study plan"],
	"job_matching": ["job", "role", "match", "fit", "eligibility"],
	"networking": ["network", "linkedin", "referral", "mentor", "outreach"],
}


def detect_intent(message: str) -> str:
	normalized = message.lower().strip()
	if not normalized:
		return "career_assessment"

	for intent, keywords in INTENT_KEYWORDS.items():
		if any(keyword in normalized for keyword in keywords):
			return intent

	return "career_assessment"
