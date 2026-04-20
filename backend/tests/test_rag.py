from pathlib import Path

from app.services.rag_service import infer_metadata_filters


def test_rag_status_endpoint(client):
	response = client.get("/api/v1/rag/status")
	assert response.status_code == 200
	body = response.json()
	assert "enabled" in body
	assert "total_chunks" in body


def test_rag_ingest_and_search_endpoint(client, tmp_path: Path):
	doc_path = tmp_path / "sample_notes.txt"
	doc_path.write_text(
		"Career planning for data science includes SQL, Python, statistics, and interview preparation.",
		encoding="utf-8",
	)

	ingest_response = client.post("/api/v1/rag/ingest", json={"directory_path": str(tmp_path)})
	assert ingest_response.status_code == 200
	ingest_body = ingest_response.json()
	assert ingest_body["ingested_chunks"] >= 1
	assert len(ingest_body["ingested_files"]) >= 1

	search_response = client.get("/api/v1/rag/search?query=data science interview")
	assert search_response.status_code == 200
	search_body = search_response.json()
	assert search_body["query"] == "data science interview"
	assert isinstance(search_body["results"], list)
	assert len(search_body["results"]) >= 1


def test_rag_search_with_intent_and_role_params(client, tmp_path: Path):
	doc_path = tmp_path / "ml_engineer_interview_notes.txt"
	doc_path.write_text(
		"ML engineer interview preparation includes model evaluation, feature engineering, and system design.",
		encoding="utf-8",
	)

	ingest_response = client.post("/api/v1/rag/ingest", json={"directory_path": str(tmp_path)})
	assert ingest_response.status_code == 200

	search_response = client.get(
		"/api/v1/rag/search",
		params={
			"query": "how to crack ml interview",
			"intent": "interview_prep",
			"target_role": "ml engineer",
		},
	)
	assert search_response.status_code == 200
	body = search_response.json()
	assert body["query"] == "how to crack ml interview"
	assert len(body["results"]) >= 1


def test_rag_evaluate_endpoint(client, tmp_path: Path):
	doc_path = tmp_path / "learning_roadmap_data_science.txt"
	doc_path.write_text(
		"A learning roadmap for data science should include python, statistics, and portfolio projects.",
		encoding="utf-8",
	)

	ingest_response = client.post("/api/v1/rag/ingest", json={"directory_path": str(tmp_path)})
	assert ingest_response.status_code == 200

	evaluate_response = client.post(
		"/api/v1/rag/evaluate",
		json={
			"query": "data science learning roadmap",
			"expected_terms": ["python", "statistics", "roadmap"],
			"expected_source_contains": ["learning_roadmap_data_science"],
			"intent": "learning_path",
			"target_role": "data scientist",
			"top_k": 4,
		},
	)
	assert evaluate_response.status_code == 200
	body = evaluate_response.json()
	assert body["query"] == "data science learning roadmap"
	assert isinstance(body["retrieved_count"], int)
	assert body["retrieved_count"] >= 1
	assert isinstance(body["results"], list)
	assert len(body["results"]) >= 1
	assert body["term_coverage"] is None or 0 <= body["term_coverage"] <= 1
	assert body["source_recall_at_k"] is None or 0 <= body["source_recall_at_k"] <= 1


def test_rag_telemetry_endpoint(client):
	user_id = "rag-telemetry-user"
	message_response = client.post(
		"/api/v1/chat/message",
		json={
			"user_id": user_id,
			"message": "Give me a learning roadmap for data science interview prep",
			"context": {},
		},
	)
	assert message_response.status_code == 200

	telemetry_response = client.get(
		"/api/v1/rag/telemetry",
		params={"user_id": user_id, "limit": 50},
	)
	assert telemetry_response.status_code == 200
	body = telemetry_response.json()
	assert body["user_id"] == user_id
	assert body["samples"] >= 1
	assert body["retrieval_ms_avg"] >= 0
	assert body["retrieval_ms_p50"] >= 0
	assert body["retrieval_ms_p95"] >= 0
	assert body["retrieved_count_avg"] >= 0
	assert body["retrieved_count_p50"] >= 0
	assert body["retrieved_count_p95"] >= 0
	assert 0 <= body["auto_filters_rate"] <= 1
	assert 0 <= body["fallback_without_filters_rate"] <= 1
	assert 0 <= body["non_empty_retrieval_rate"] <= 1


def test_rag_telemetry_trends_endpoint(client):
	user_id = "rag-telemetry-trends-user"
	for message in [
		"Give me roadmap for data science",
		"How to prepare for interview rounds",
		"Show role fit for ml engineer",
	]:
		response = client.post(
			"/api/v1/chat/message",
			json={"user_id": user_id, "message": message, "context": {}},
		)
		assert response.status_code == 200

	trends_response = client.get(
		"/api/v1/rag/telemetry/trends",
		params={"user_id": user_id, "windows": "2,5", "limit": 20},
	)
	assert trends_response.status_code == 200
	body = trends_response.json()
	assert body["user_id"] == user_id
	assert body["total_samples"] >= 1
	assert isinstance(body["windows"], list)
	assert len(body["windows"]) == 2
	assert body["windows"][0]["window"] == 2
	assert body["windows"][1]["window"] == 5
	for bucket in body["windows"]:
		assert bucket["samples"] >= 0
		assert bucket["retrieval_ms_avg"] >= 0
		assert bucket["retrieval_ms_p50"] >= 0
		assert bucket["retrieval_ms_p95"] >= 0
		assert 0 <= bucket["non_empty_retrieval_rate"] <= 1


def test_rag_telemetry_trend_series_endpoint(client):
	user_id = "rag-telemetry-series-user"
	for message in [
		"Give me roadmap for data science",
		"How to prepare for interview rounds",
		"Show role fit for ml engineer",
	]:
		response = client.post(
			"/api/v1/chat/message",
			json={"user_id": user_id, "message": message, "context": {}},
		)
		assert response.status_code == 200

	series_response = client.get(
		"/api/v1/rag/telemetry/trends/series",
		params={"user_id": user_id, "windows": "2,5", "limit": 20},
	)
	assert series_response.status_code == 200
	body = series_response.json()
	assert body["user_id"] == user_id
	assert body["total_samples"] >= 1
	assert body["windows"] == [2, 5]
	assert body["labels"] == ["last_2", "last_5"]
	length = len(body["windows"])
	assert len(body["samples"]) == length
	assert len(body["retrieval_ms_avg"]) == length
	assert len(body["retrieved_count_avg"]) == length
	assert len(body["non_empty_retrieval_rate"]) == length
	assert len(body["auto_filters_rate"]) == length
	assert len(body["fallback_without_filters_rate"]) == length
	for value in body["non_empty_retrieval_rate"]:
		assert 0 <= value <= 1


def test_rag_telemetry_trends_combined_endpoint(client):
	user_id = "rag-telemetry-combined-user"
	for message in [
		"Give me roadmap for data science",
		"How to prepare for interview rounds",
		"Show role fit for ml engineer",
	]:
		response = client.post(
			"/api/v1/chat/message",
			json={"user_id": user_id, "message": message, "context": {}},
		)
		assert response.status_code == 200

	combined_response = client.get(
		"/api/v1/rag/telemetry/trends/combined",
		params={"user_id": user_id, "windows": "2,5", "limit": 20},
	)
	assert combined_response.status_code == 200
	body = combined_response.json()
	assert body["user_id"] == user_id
	assert body["total_samples"] >= 1
	assert len(body["windows"]) == 2
	assert body["windows"][0]["window"] == 2
	assert body["windows"][1]["window"] == 5
	series = body["series"]
	assert series["user_id"] == user_id
	assert series["windows"] == [2, 5]
	assert series["labels"] == ["last_2", "last_5"]
	assert len(series["retrieval_ms_avg"]) == 2


def test_rag_infer_metadata_filters_detects_data_science_interview_role():
	filters = infer_metadata_filters("how i can prepare for data science interview")
	assert filters.get("topic") == "interview"
	assert filters.get("role") == "data scientist"
