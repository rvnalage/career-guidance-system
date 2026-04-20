"""Static typed constants used by recommendation and knowledge-base modules."""

# Developer Onboarding Notes:
# - Layer: core module
# - Role in system: Supports application behavior and shared logic.
# - Main callers: Imported by neighboring modules.
# - Reading tip: Start from exported functions/classes, then follow dependencies upward to route handlers.


from typing import TypedDict


class CareerPath(TypedDict):
	"""Shape of a supported career definition used by the recommendation engine."""
	role: str
	required_skills: list[str]
	related_interests: list[str]
	min_education: str
	description: str


EDUCATION_ORDER = {
	"high_school": 1,
	"diploma": 2,
	"bachelor": 3,
	"master": 4,
	"phd": 5,
}

# Maps a skill keyword to a concise free/low-cost learning resource suggestion.
SKILL_RESOURCES: dict[str, str] = {
	"sql": "SQLZoo (sqlzoo.net) or Mode Analytics SQL Tutorial",
	"python": "Python.org official tutorial or 'Automate the Boring Stuff' (free online)",
	"excel": "Microsoft Excel training on support.microsoft.com or Chandoo.org",
	"statistics": "Khan Academy Statistics or StatQuest with Josh Starmer (YouTube)",
	"power bi": "Microsoft Learn Power BI learning path (free, learn.microsoft.com)",
	"machine learning": "Andrew Ng's Machine Learning Specialization (Coursera) or fast.ai",
	"deep learning": "fast.ai Practical Deep Learning or deeplearning.ai specialization",
	"pandas": "Pandas official 10-minute tutorial or Kaggle Pandas micro-course (free)",
	"numpy": "NumPy quickstart guide (numpy.org) or CS231n Python/NumPy tutorial",
	"fastapi": "FastAPI official docs tutorial (fastapi.tiangolo.com)",
	"api": "REST API Design best practices â€” restfulapi.net or Postman Learning Center",
	"docker": "Docker official Get Started guide (docs.docker.com) or TechWorld with Nana (YouTube)",
	"kubernetes": "Kubernetes.io interactive tutorials or KodeKloud free Kubernetes course",
	"linux": "Linux Journey (linuxjourney.com) or The Odin Project Linux section",
	"ci/cd": "GitHub Actions quickstart or GitLab CI/CD tutorial (docs.gitlab.com)",
	"cloud": "AWS Cloud Practitioner Essentials (free on AWS Skill Builder) or Google Cloud Skills Boost",
	"figma": "Figma official tutorials (help.figma.com) or Figma YouTube channel",
	"wireframing": "Balsamiq wireframing guide or NNGroup articles on wireframing",
	"prototyping": "Figma interactive prototype tutorial or Adobe XD free course on YouTube",
	"design thinking": "IDEO Design Thinking free course (IDEO U) or Stanford d.school resources",
	"usability": "NNGroup usability heuristics articles or Interaction Design Foundation free courses",
}


CAREER_PATHS: list[CareerPath] = [
	{
		"role": "Data Analyst",
		"required_skills": ["sql", "python", "excel", "statistics", "power bi"],
		"related_interests": ["data", "analytics", "business", "research"],
		"min_education": "bachelor",
		"description": "Analyze datasets and generate business insights.",
	},
	{
		"role": "Machine Learning Engineer",
		"required_skills": ["python", "machine learning", "deep learning", "pandas", "numpy"],
		"related_interests": ["ai", "data science", "automation", "research"],
		"min_education": "bachelor",
		"description": "Build and deploy ML models for intelligent systems.",
	},
	{
		"role": "Backend Developer",
		"required_skills": ["python", "fastapi", "sql", "api", "docker"],
		"related_interests": ["software", "web development", "systems", "cloud"],
		"min_education": "bachelor",
		"description": "Design robust server-side services and APIs.",
	},
	{
		"role": "Cloud DevOps Engineer",
		"required_skills": ["docker", "kubernetes", "linux", "ci/cd", "cloud"],
		"related_interests": ["cloud", "automation", "infrastructure", "systems"],
		"min_education": "bachelor",
		"description": "Automate deployment and manage cloud infrastructure.",
	},
	{
		"role": "UI/UX Designer",
		"required_skills": ["figma", "wireframing", "prototyping", "design thinking", "usability"],
		"related_interests": ["design", "creativity", "user experience", "product"],
		"min_education": "diploma",
		"description": "Create intuitive interfaces and user journeys.",
	},
]

