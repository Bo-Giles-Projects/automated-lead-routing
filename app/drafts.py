import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.database import DATABASE_PATH, get_lead_analysis
from app.review import DraftReviewStatus, read_draft_review
from app.schemas import FollowUpDraft, LeadAnalysis

router = APIRouter(tags=["Leads"])


class DraftEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The draft the reviewer started editing from. If it no longer matches the
    # saved draft, someone else changed it and the edit is refused.
    current_draft: FollowUpDraft
    new_draft: FollowUpDraft


class DraftEditRecord(BaseModel):
    previous_draft: FollowUpDraft
    new_draft: FollowUpDraft
    edited_at: datetime


def _tables(db: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('lead_analyses', 'draft_reviews', 'email_outbox', 'draft_edits')"
        )
    }


@router.put("/api/leads/{lead_id}/draft")
def edit_saved_draft(lead_id: UUID, edit: DraftEdit) -> DraftReviewStatus:
    """Replace the saved follow-up draft. The new text always starts as pending."""
    if not DATABASE_PATH.is_file():
        raise HTTPException(status_code=404, detail="No saved draft for this lead.")

    with closing(sqlite3.connect(DATABASE_PATH)) as db, db:
        # Lock writes so a review or send cannot slip in between the checks and the update.
        db.execute("BEGIN IMMEDIATE")
        tables = _tables(db)
        row = None
        if "lead_analyses" in tables:
            row = db.execute(
                "SELECT analysis_json FROM lead_analyses WHERE lead_id = ?",
                (str(lead_id),),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="No saved draft for this lead.")

        analysis = LeadAnalysis.model_validate_json(row[0])
        if analysis.follow_up_draft != edit.current_draft:
            raise HTTPException(status_code=409, detail="Reload and edit the current draft.")

        if "email_outbox" in tables and db.execute(
            "SELECT 1 FROM email_outbox WHERE lead_id = ?", (str(lead_id),)
        ).fetchone():
            raise HTTPException(
                status_code=409, detail="A follow-up email was already sent for this lead."
            )

        if edit.new_draft != edit.current_draft:
            updated = analysis.model_copy(update={"follow_up_draft": edit.new_draft})
            new_draft_json = edit.new_draft.model_dump_json()
            db.execute(
                "UPDATE lead_analyses SET analysis_json = ? WHERE lead_id = ?",
                (updated.model_dump_json(), str(lead_id)),
            )
            db.execute("""
                CREATE TABLE IF NOT EXISTS draft_edits (
                    lead_id TEXT NOT NULL,
                    previous_draft_json TEXT NOT NULL,
                    new_draft_json TEXT NOT NULL,
                    edited_at TEXT NOT NULL
                )
            """)
            db.execute(
                """
                INSERT INTO draft_edits (lead_id, previous_draft_json, new_draft_json, edited_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(lead_id),
                    edit.current_draft.model_dump_json(),
                    new_draft_json,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            # Approvals belong to exact text. Clear any earlier decision on this
            # text so an edit always needs a fresh approval, even when it restores
            # wording that was approved before.
            if "draft_reviews" in tables:
                db.execute(
                    "DELETE FROM draft_reviews WHERE lead_id = ? AND draft_json = ?",
                    (str(lead_id), new_draft_json),
                )

    return read_draft_review(lead_id)


@router.get("/api/leads/{lead_id}/draft/edits")
def list_draft_edits(lead_id: UUID) -> list[DraftEditRecord]:
    """Edit history for a lead's draft, oldest first."""
    if get_lead_analysis(lead_id) is None:
        raise HTTPException(status_code=404, detail="No saved analysis for this lead.")

    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        if "draft_edits" not in _tables(db):
            return []
        rows = db.execute(
            """
            SELECT previous_draft_json, new_draft_json, edited_at
            FROM draft_edits
            WHERE lead_id = ?
            ORDER BY edited_at, rowid
            """,
            (str(lead_id),),
        ).fetchall()

    return [
        DraftEditRecord(
            previous_draft=FollowUpDraft.model_validate_json(previous),
            new_draft=FollowUpDraft.model_validate_json(new),
            edited_at=edited_at,
        )
        for previous, new, edited_at in rows
    ]
