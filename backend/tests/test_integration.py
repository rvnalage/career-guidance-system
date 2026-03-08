def test_root_endpoint(client):
	response = client.get("/")
	assert response.status_code == 200
	body = response.json()
	assert body["message"] == "Career Guidance System API is running"


def test_health_endpoint(client):
	response = client.get("/health")
	assert response.status_code == 200
	assert response.json() == {"status": "ok"}


def test_chat_route_is_mounted(client):
	payload = {"user_id": "u1", "message": "Suggest AI roles", "context": {}}
	response = client.post("/api/v1/chat/message", json=payload)
	assert response.status_code == 200
	assert "reply" in response.json()


def test_market_jobs_endpoint(client):
	response = client.get("/api/v1/market/jobs?search=data&limit=3")
	assert response.status_code == 200
	body = response.json()
	assert "source" in body
	assert "results" in body
	assert isinstance(body["results"], list)


def test_llm_status_endpoint(client):
	response = client.get("/api/v1/llm/status")
	assert response.status_code == 200
	body = response.json()
	assert "enabled" in body
	assert "provider" in body
	assert "active_model" in body
	assert "is_finetuned_active" in body


def test_psychometric_scoring_endpoint(client):
	payload = {
		"dimensions": {
			"investigative": 5,
			"social": 4,
			"enterprising": 3,
			"artistic": 2,
			"realistic": 3,
			"conventional": 4,
		}
	}
	response = client.post("/api/v1/psychometric/score", json=payload)
	assert response.status_code == 200
	body = response.json()
	assert "normalized_scores" in body
	assert "top_traits" in body
	assert "recommended_domains" in body
