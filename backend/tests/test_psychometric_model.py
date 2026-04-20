from app.schemas.psychometric import PsychometricRequest
from app.services import psychometric_service


def test_score_psychometric_uses_model_primary_domain_when_enabled(monkeypatch):
	class _Model:
		def predict_proba(self, rows):
			_ = rows
			return [[0.1, 0.9]]

	monkeypatch.setattr(psychometric_service.settings, "psychometric_model_enabled", True)
	monkeypatch.setattr(
		psychometric_service,
		"_load_psychometric_model",
		lambda: {"model": _Model(), "domains": ["DevOps", "Data Science"]},
	)

	payload = PsychometricRequest(
		dimensions={
			"investigative": 5,
			"realistic": 2,
			"artistic": 2,
			"social": 2,
			"enterprising": 3,
			"conventional": 3,
		}
	)
	normalized_scores, top_traits, domains = psychometric_service.score_psychometric(payload)

	assert normalized_scores
	assert top_traits
	assert domains[0] == "Data Science"


def test_score_psychometric_fallback_without_model(monkeypatch):
	monkeypatch.setattr(psychometric_service.settings, "psychometric_model_enabled", False)
	payload = PsychometricRequest(
		dimensions={
			"social": 5,
			"investigative": 4,
			"conventional": 3,
		}
	)
	_, _, domains = psychometric_service.score_psychometric(payload)
	assert len(domains) > 0


def test_score_psychometric_returns_top_three_traits(monkeypatch):
	monkeypatch.setattr(psychometric_service.settings, "psychometric_model_enabled", False)
	payload = PsychometricRequest(
		dimensions={
			"investigative": 5,
			"realistic": 4,
			"artistic": 3,
			"social": 2,
			"enterprising": 1,
			"conventional": 4,
		}
	)
	_, top_traits, _ = psychometric_service.score_psychometric(payload)

	# API contract keeps top-traits summary concise for UI display.
	assert len(top_traits) == 3
	assert top_traits[0] == "investigative"


def test_score_psychometric_fallback_uses_non_top_three_traits(monkeypatch):
	monkeypatch.setattr(psychometric_service.settings, "psychometric_model_enabled", False)
	payload = PsychometricRequest(
		dimensions={
			"investigative": 5,
			"realistic": 5,
			"artistic": 5,
			"social": 5,
			"enterprising": 5,
			"conventional": 5,
		}
	)
	_, _, domains = psychometric_service.score_psychometric(payload)

	# Domain candidates from lower-ranked traits should still be eligible in fallback mapping.
	assert "Product Management" in domains
