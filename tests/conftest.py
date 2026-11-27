import pytest
from fastapi.testclient import TestClient

import app.database
import app.drafts
import app.outbox
import app.review
from app.main import app as fastapi_app

SAMPLE_LEAD = {
    "name": "Jordan Taylor",
    "email": "jordan@example.com",
    "company_size": "11-50",
    "service_needed": "Cybersecurity",
    "project_details": (
        "Several employees cannot access shared files, and a ransom note "
        "appeared on one workstation this morning. We need urgent help "
        "assessing the incident and restoring business operations."
    ),
}


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point every module at a throwaway SQLite file.

    review.py, outbox.py and drafts.py import DATABASE_PATH by name, so each module's
    copy has to be patched, not only app.database's.
    """
    path = tmp_path / "data" / "leads.db"
    for module in (app.database, app.review, app.outbox, app.drafts):
        monkeypatch.setattr(module, "DATABASE_PATH", path)
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return TestClient(fastapi_app)


@pytest.fixture
def lead_id(client):
    response = client.post("/api/leads", json=SAMPLE_LEAD)
    assert response.status_code == 200
    return response.json()["lead_id"]


@pytest.fixture
def analyzed_lead(client, lead_id):
    """A saved lead with a saved analysis. Returns (lead_id, draft)."""
    response = client.post(f"/api/leads/{lead_id}/analyze")
    assert response.status_code == 200
    return lead_id, response.json()["follow_up_draft"]
