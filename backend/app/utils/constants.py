from typing import TypedDict


class CareerPath(TypedDict):
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
