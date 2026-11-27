"""Approval rules for follow-up emails.

The invariant these tests protect: an email is only queued for a draft
that a human approved, and only for the exact draft that was approved.
"""
import sqlite3
import uuid
from uuid import UUID

from app.database import get_lead_analysis, save_lead_analysis


def review(client, lead_id, decision, draft):
    return client.post(
        f"/api/leads/{lead_id}/review",
        json={"decision": decision, "draft": draft},
    )


def send(client, lead_id):
    return client.post(f"/api/leads/{lead_id}/send")


def replace_saved_draft(lead_id, **changes):
    """Simulate the saved draft changing (re-analysis or future draft editing)."""
    analysis = get_lead_analysis(UUID(lead_id))
    new_draft = analysis.follow_up_draft.model_copy(update=changes)
    save_lead_analysis(UUID(lead_id), analysis.model_copy(update={"follow_up_draft": new_draft}))
    return new_draft.model_dump()


def outbox_rows(db_path):
    with sqlite3.connect(db_path) as db:
        return db.execute("SELECT lead_id, recipient, draft_json FROM email_outbox").fetchall()


# --- Review status -----------------------------------------------------------

def test_new_draft_starts_pending(client, analyzed_lead):
    lead_id, draft = analyzed_lead

    status = client.get(f"/api/leads/{lead_id}/review").json()

    assert status["decision"] == "pending"
    assert status["reviewed_at"] is None
    assert status["draft"] == draft


def test_approval_is_reported_in_status(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    assert review(client, lead_id, "approved", draft).status_code == 200

    status = client.get(f"/api/leads/{lead_id}/review").json()

    assert status["decision"] == "approved"
    assert status["reviewed_at"] is not None


def test_review_status_for_unanalyzed_lead_returns_404(client, lead_id):
    assert client.get(f"/api/leads/{lead_id}/review").status_code == 404


# --- Reviewing ---------------------------------------------------------------

def test_review_without_saved_analysis_returns_404(client, lead_id):
    draft = {"subject": "Hi", "body": "Hello"}
    assert review(client, lead_id, "approved", draft).status_code == 404


def test_review_of_unknown_lead_returns_404(client, analyzed_lead):
    _, draft = analyzed_lead
    assert review(client, str(uuid.uuid4()), "approved", draft).status_code == 404


def test_review_of_a_different_draft_is_refused(client, analyzed_lead):
    """The reviewer must approve the draft that is actually saved."""
    lead_id, draft = analyzed_lead
    edited = {**draft, "body": draft["body"] + "\n\nP.S. 50% off!"}

    response = review(client, lead_id, "approved", edited)

    assert response.status_code == 409
    assert client.get(f"/api/leads/{lead_id}/review").json()["decision"] == "pending"
    assert send(client, lead_id).status_code == 409


def test_review_rejects_invalid_decision(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    assert review(client, lead_id, "maybe", draft).status_code == 422


def test_review_rejects_unexpected_fields(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    response = client.post(
        f"/api/leads/{lead_id}/review",
        json={"decision": "approved", "draft": draft, "force": True},
    )
    assert response.status_code == 422


# --- Sending -----------------------------------------------------------------

def test_send_without_any_database_returns_404(client, db_path):
    assert not db_path.exists()
    assert send(client, str(uuid.uuid4())).status_code == 404


def test_send_without_analysis_returns_404(client, lead_id):
    assert send(client, lead_id).status_code == 404


def test_send_of_unknown_lead_returns_404(client, analyzed_lead):
    assert send(client, str(uuid.uuid4())).status_code == 404


def test_send_before_review_is_refused(client, analyzed_lead, db_path):
    lead_id, _ = analyzed_lead

    response = send(client, lead_id)

    assert response.status_code == 409
    with sqlite3.connect(db_path) as db:
        table = db.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'email_outbox'"
        ).fetchone()
    assert table is None


def test_send_after_rejection_is_refused(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "rejected", draft)

    assert send(client, lead_id).status_code == 409


def test_rejecting_after_approval_blocks_send(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)
    review(client, lead_id, "rejected", draft)

    assert send(client, lead_id).status_code == 409


def test_approved_draft_is_queued_to_lead_email(client, analyzed_lead, db_path):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)

    response = send(client, lead_id)

    assert response.status_code == 200
    email = response.json()
    assert email["status"] == "simulated"
    assert email["recipient"] == "jordan@example.com"
    assert email["lead_id"] == lead_id
    assert email["draft"] == draft
    assert len(outbox_rows(db_path)) == 1


def test_sending_twice_queues_only_one_email(client, analyzed_lead, db_path):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)

    first = send(client, lead_id).json()
    second = send(client, lead_id).json()

    assert first["message_id"] == second["message_id"]
    assert first["queued_at"] == second["queued_at"]
    assert len(outbox_rows(db_path)) == 1


def test_changed_draft_needs_new_approval(client, analyzed_lead, db_path):
    """Approval belongs to one exact draft, not to the lead."""
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)

    new_draft = replace_saved_draft(lead_id, body="Hi Jordan,\n\nNew wording.\n\nBest,\nThe team")

    assert client.get(f"/api/leads/{lead_id}/review").json()["decision"] == "pending"
    assert send(client, lead_id).status_code == 409
    assert review(client, lead_id, "approved", draft).status_code == 409

    assert review(client, lead_id, "approved", new_draft).status_code == 200
    email = send(client, lead_id).json()
    assert email["draft"] == new_draft
    assert len(outbox_rows(db_path)) == 1


def test_reverting_to_an_approved_draft_restores_approval(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)

    replace_saved_draft(lead_id, subject="Something else")
    assert send(client, lead_id).status_code == 409

    replace_saved_draft(lead_id, subject=draft["subject"])
    assert send(client, lead_id).status_code == 200


def test_approval_for_one_lead_does_not_cover_another(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)

    from tests.conftest import SAMPLE_LEAD
    other_id = client.post("/api/leads", json=SAMPLE_LEAD).json()["lead_id"]
    other_draft = client.post(f"/api/leads/{other_id}/analyze").json()["follow_up_draft"]
    assert other_draft == draft  # identical text, different lead

    assert send(client, other_id).status_code == 409
