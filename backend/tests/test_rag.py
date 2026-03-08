from pathlib import Path


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
