import uuid

from tests.conftest import SAMPLE_LEAD


def test_mock_preview_flags_ransomware_as_urgent_security(client):
    response = client.post("/api/leads/analyze", json=SAMPLE_LEAD)

    assert response.status_code == 200
    analysis = response.json()
    assert analysis["urgency"] == "High"
    assert analysis["fit_score"] == 90
    assert analysis["recommended_department"] == "Security"
    assert analysis["follow_up_draft"]["subject"]
    assert "Jordan Taylor" in analysis["follow_up_draft"]["body"]


def test_mock_preview_routes_other_to_sales(client):
    lead = {
        **SAMPLE_LEAD,
        "service_needed": "Other",
        "project_details": "We are curious what services you offer for nonprofits.",
    }
    analysis = client.post("/api/leads/analyze", json=lead).json()

    assert analysis["urgency"] == "Low"
    assert analysis["fit_score"] == 25
    assert analysis["recommended_department"] == "Sales"


def test_unknown_provider_returns_503(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "something-else")
    assert client.post("/api/leads/analyze", json=SAMPLE_LEAD).status_code == 503


def test_openai_without_key_returns_503(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    assert client.post("/api/leads/analyze", json=SAMPLE_LEAD).status_code == 503


def test_analysis_is_saved_and_readable(client, analyzed_lead):
    lead_id, draft = analyzed_lead

    response = client.get(f"/api/leads/{lead_id}/analysis")

    assert response.status_code == 200
    assert response.json()["follow_up_draft"] == draft


def test_analyzing_unknown_lead_returns_404(client, lead_id):
    assert client.post(f"/api/leads/{uuid.uuid4()}/analyze").status_code == 404


def test_reading_missing_analysis_returns_404(client, lead_id):
    assert client.get(f"/api/leads/{lead_id}/analysis").status_code == 404
