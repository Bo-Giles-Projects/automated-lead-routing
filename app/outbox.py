import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import DATABASE_PATH
from app.schemas import FollowUpDraft, LeadAnalysis

router = APIRouter(tags=["Leads"])


class SimulatedEmail(BaseModel):
    message_id: UUID
    lead_id: UUID
    recipient: str
    draft: FollowUpDraft
    queued_at: datetime
    status: Literal["simulated"] = "simulated"


@router.post("/api/leads/{lead_id}/send")
def simulate_email_send(lead_id: UUID) -> SimulatedEmail:
    if not DATABASE_PATH.is_file():
        raise HTTPException(status_code=404, detail="No saved draft for this lead.")

    with closing(sqlite3.connect(DATABASE_PATH)) as db, db:
        # Lock writes so the draft and its approval cannot change during the insert.
        db.execute("BEGIN IMMEDIATE")
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name IN ('lead_analyses', 'draft_reviews')"
            )
        }
        if "lead_analyses" not in tables:
            raise HTTPException(status_code=404, detail="No saved draft for this lead.")

        lead = db.execute(
            """
            SELECT leads.email, lead_analyses.analysis_json
            FROM leads
            JOIN lead_analyses ON lead_analyses.lead_id = leads.id
            WHERE leads.id = ?
            """,
            (str(lead_id),),
        ).fetchone()
        if lead is None:
            raise HTTPException(status_code=404, detail="No saved draft for this lead.")

        recipient, analysis_json = lead
        draft = LeadAnalysis.model_validate_json(analysis_json).follow_up_draft
        draft_json = draft.model_dump_json()
        review = None
        if "draft_reviews" in tables:
            review = db.execute(
                "SELECT decision FROM draft_reviews WHERE lead_id = ? AND draft_json = ?",
                (str(lead_id), draft_json),
            ).fetchone()
        if review is None or review[0] != "approved":
            raise HTTPException(status_code=409, detail="The current draft needs approval.")

        db.execute("""
            CREATE TABLE IF NOT EXISTS email_outbox (
                message_id TEXT PRIMARY KEY,
                lead_id TEXT NOT NULL,
                recipient TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                queued_at TEXT NOT NULL,
                UNIQUE (lead_id, draft_json)
            )
        """)
        db.execute(
            """
            INSERT INTO email_outbox (message_id, lead_id, recipient, draft_json, queued_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (lead_id, draft_json) DO NOTHING
            """,
            (
                str(uuid4()), str(lead_id), recipient, draft_json,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        message_id, saved_recipient, queued_at = db.execute(
            """
            SELECT message_id, recipient, queued_at
            FROM email_outbox
            WHERE lead_id = ? AND draft_json = ?
            """,
            (str(lead_id), draft_json),
        ).fetchone()

    return SimulatedEmail(
        message_id=message_id,
        lead_id=lead_id,
        recipient=saved_recipient,
        draft=draft,
        queued_at=queued_at,
    )
