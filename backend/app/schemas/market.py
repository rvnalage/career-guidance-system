from pydantic import BaseModel


class JobMarketItem(BaseModel):
	job_title: str
	company: str
	location: str
	category: str
	url: str
	published_at: str


class JobMarketResponse(BaseModel):
	source: str
	query: str
	results: list[JobMarketItem]
