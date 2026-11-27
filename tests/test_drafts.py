"""Draft editing: a reviewer can change the AI's draft, and any edit needs a
fresh approval before it can be sent."""
import uuid

from tests.test_approval import outbox_rows, review, send

EDITED = {"subject": "Next steps on your incident", "body": "Hi Jordan,\n\nCan we call at 2pm?\n\nBest,\nThe team"}


def edit(client, lead_id, current, new):
    return client.put(
        f"/api/leads/{lead_id}/draft",
        json={"current_draft": current, "new_draft": new},
    )


def status(client, lead_id):
    return client.get(f"/api/leads/{lead_id}/review").json()


# --- Editing -----------------------------------------------------------------

def test_edit_replaces_saved_draft_and_is_pending(client, analyzed_lead):
    lead_id, draft = analyzed_lead

    response = edit(client, lead_id, draft, EDITED)

    assert response.status_code == 200
    assert response.json()["decision"] == "pending"
    assert response.json()["draft"] == EDITED
    assert client.get(f"/api/leads/{lead_id}/analysis").json()["follow_up_draft"] == EDITED


def test_edit_keeps_the_rest_of_the_analysis(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    before = client.get(f"/api/leads/{lead_id}/analysis").json()

    edit(client, lead_id, draft, EDITED)

    after = client.get(f"/api/leads/{lead_id}/analysis").json()
    assert {k: v for k, v in after.items() if k != "follow_up_draft"} == {
        k: v for k, v in before.items() if k != "follow_up_draft"
    }


def test_edit_from_a_stale_draft_is_refused(client, analyzed_lead):
    """Two reviewers editing at once: the second must reload first."""
    lead_id, draft = analyzed_lead
    edit(client, lead_id, draft, EDITED)

    response = edit(client, lead_id, draft, {**draft, "subject": "Other reviewer's subject"})

    assert response.status_code == 409
    assert status(client, lead_id)["draft"] == EDITED


def test_edit_without_saved_analysis_returns_404(client, lead_id):
    assert edit(client, lead_id, EDITED, EDITED).status_code == 404


def test_edit_of_unknown_lead_returns_404(client, analyzed_lead):
    _, draft = analyzed_lead
    assert edit(client, str(uuid.uuid4()), draft, EDITED).status_code == 404


def test_edit_without_any_database_returns_404(client, db_path):
    assert not db_path.exists()
    assert edit(client, str(uuid.uuid4()), EDITED, EDITED).status_code == 404


def test_edit_rejects_empty_or_oversized_text(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    assert edit(client, lead_id, draft, {**draft, "body": "   "}).status_code == 422
    assert edit(client, lead_id, draft, {**draft, "subject": "x" * 151}).status_code == 422


def test_edit_rejects_unexpected_fields(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    response = client.put(
        f"/api/leads/{lead_id}/draft",
        json={"current_draft": draft, "new_draft": EDITED, "decision": "approved"},
    )
    assert response.status_code == 422
    assert status(client, lead_id)["decision"] == "pending"


# --- Edits and approval ------------------------------------------------------

def test_editing_an_approved_draft_revokes_approval(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)

    edit(client, lead_id, draft, EDITED)

    assert status(client, lead_id)["decision"] == "pending"
    assert send(client, lead_id).status_code == 409


def test_edited_draft_is_sent_once_approved(client, analyzed_lead, db_path):
    lead_id, draft = analyzed_lead
    edit(client, lead_id, draft, EDITED)
    assert review(client, lead_id, "approved", EDITED).status_code == 200

    response = send(client, lead_id)

    assert response.status_code == 200
    assert response.json()["draft"] == EDITED
    assert len(outbox_rows(db_path)) == 1


def test_original_draft_cannot_be_approved_after_edit(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    edit(client, lead_id, draft, EDITED)

    assert review(client, lead_id, "approved", draft).status_code == 409
    assert send(client, lead_id).status_code == 409


def test_editing_back_to_approved_text_still_needs_approval(client, analyzed_lead):
    """Every edit needs a fresh approval, even one that restores old wording."""
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)
    edit(client, lead_id, draft, EDITED)

    edit(client, lead_id, EDITED, draft)

    assert status(client, lead_id)["decision"] == "pending"
    assert send(client, lead_id).status_code == 409


def test_saving_unchanged_text_keeps_approval(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)

    response = edit(client, lead_id, draft, draft)

    assert response.json()["decision"] == "approved"
    assert client.get(f"/api/leads/{lead_id}/draft/edits").json() == []
    assert send(client, lead_id).status_code == 200


def test_edit_after_sending_is_refused(client, analyzed_lead, db_path):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)
    send(client, lead_id)

    response = edit(client, lead_id, draft, EDITED)

    assert response.status_code == 409
    assert status(client, lead_id)["draft"] == draft
    assert len(outbox_rows(db_path)) == 1


# --- Edit history ------------------------------------------------------------

def test_edit_history_records_each_change(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    second = {**EDITED, "subject": "Second try"}
    edit(client, lead_id, draft, EDITED)
    edit(client, lead_id, EDITED, second)

    history = client.get(f"/api/leads/{lead_id}/draft/edits").json()

    assert [(h["previous_draft"], h["new_draft"]) for h in history] == [
        (draft, EDITED),
        (EDITED, second),
    ]
    assert all(h["edited_at"] for h in history)


def test_refused_edits_are_not_recorded(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    edit(client, lead_id, EDITED, {**EDITED, "subject": "stale"})

    assert client.get(f"/api/leads/{lead_id}/draft/edits").json() == []


def test_edit_history_for_unanalyzed_lead_returns_404(client, lead_id):
    assert client.get(f"/api/leads/{lead_id}/draft/edits").status_code == 404


# --- Re-analysis -------------------------------------------------------------

def reanalyze(client, lead_id):
    return client.post(f"/api/leads/{lead_id}/analyze")


def test_reanalysis_is_allowed_before_any_review(client, analyzed_lead):
    lead_id, _ = analyzed_lead
    assert reanalyze(client, lead_id).status_code == 200


def test_reanalysis_is_allowed_after_rejection(client, analyzed_lead):
    """A rejected draft can be replaced with a fresh one."""
    lead_id, draft = analyzed_lead
    review(client, lead_id, "rejected", draft)

    assert reanalyze(client, lead_id).status_code == 200


def test_reanalysis_after_approval_is_refused(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)

    assert reanalyze(client, lead_id).status_code == 409
    assert status(client, lead_id)["decision"] == "approved"


def test_reanalysis_after_edit_keeps_the_edit(client, analyzed_lead):
    lead_id, draft = analyzed_lead
    edit(client, lead_id, draft, EDITED)

    assert reanalyze(client, lead_id).status_code == 409
    assert status(client, lead_id)["draft"] == EDITED


def test_reanalysis_cannot_restore_an_approval_the_reviewer_edited_away(client, analyzed_lead):
    """Approve the AI draft, edit it, re-analyze: the AI's wording (still
    approved from before) must not come back and become sendable."""
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)
    edit(client, lead_id, draft, EDITED)

    assert reanalyze(client, lead_id).status_code == 409
    assert status(client, lead_id) | {"reviewed_at": None} == {
        "lead_id": lead_id, "draft": EDITED, "decision": "pending", "reviewed_at": None,
    }
    assert send(client, lead_id).status_code == 409


def test_reanalysis_after_send_is_refused(client, analyzed_lead, db_path):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)
    send(client, lead_id)

    assert reanalyze(client, lead_id).status_code == 409
    assert len(outbox_rows(db_path)) == 1


def test_locked_lead_is_refused_before_calling_the_ai(client, analyzed_lead, monkeypatch):
    lead_id, draft = analyzed_lead
    review(client, lead_id, "approved", draft)

    def fail(_lead):
        raise AssertionError("analysis should not run for a locked lead")

    monkeypatch.setattr("app.main.analyze_lead_mock", fail)
    assert reanalyze(client, lead_id).status_code == 409


def test_review_during_slow_analysis_is_not_overwritten(client, analyzed_lead, monkeypatch):
    """If a reviewer approves while the AI is still working, the new
    analysis must not replace the draft they approved."""
    lead_id, draft = analyzed_lead
    import app.main
    real = app.main.analyze_lead_mock

    def approve_mid_analysis(lead):
        review(client, lead_id, "approved", draft)
        result = real(lead)
        return result.model_copy(
            update={"follow_up_draft": result.follow_up_draft.model_copy(update={"subject": "AI v2"})}
        )

    monkeypatch.setattr("app.main.analyze_lead_mock", approve_mid_analysis)

    assert reanalyze(client, lead_id).status_code == 409
    assert status(client, lead_id)["draft"] == draft
    assert status(client, lead_id)["decision"] == "approved"
