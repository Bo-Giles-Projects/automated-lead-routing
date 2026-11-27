from tests.conftest import SAMPLE_LEAD


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_valid_lead_returns_receipt(client):
    response = client.post("/api/leads", json=SAMPLE_LEAD)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated"
    assert body["lead_id"]
    assert body["received_at"]


def test_each_lead_gets_a_unique_id(client):
    first = client.post("/api/leads", json=SAMPLE_LEAD).json()["lead_id"]
    second = client.post("/api/leads", json=SAMPLE_LEAD).json()["lead_id"]
    assert first != second


def test_invalid_email_is_rejected(client):
    response = client.post("/api/leads", json={**SAMPLE_LEAD, "email": "not-an-email"})
    assert response.status_code == 422


def test_missing_field_is_rejected(client):
    lead = {k: v for k, v in SAMPLE_LEAD.items() if k != "project_details"}
    assert client.post("/api/leads", json=lead).status_code == 422


def test_unexpected_field_is_rejected(client):
    response = client.post("/api/leads", json={**SAMPLE_LEAD, "is_admin": True})
    assert response.status_code == 422


def test_unsupported_category_is_rejected(client):
    response = client.post("/api/leads", json={**SAMPLE_LEAD, "service_needed": "Plumbing"})
    assert response.status_code == 422


def test_short_project_details_are_rejected(client):
    response = client.post("/api/leads", json={**SAMPLE_LEAD, "project_details": "help"})
    assert response.status_code == 422
