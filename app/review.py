import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.database import DATABASE_PATH, get_lead_analysis
from app.schemas import FollowUpDraft

router = APIRouter(tags=["Leads"])


class DraftReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    draft: FollowUpDraft


@router.post("/api/leads/{lead_id}/review")
def review_saved_draft(lead_id: UUID, review: DraftReview) -> dict[str, str]:
    if get_lead_analysis(lead_id) is None:
        raise HTTPException(status_code=404, detail="No saved analysis for this lead.")

    reviewed_at = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(DATABASE_PATH)) as db, db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS draft_reviews (
                lead_id TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                decision TEXT NOT NULL,
                reviewed_at TEXT NOT NULL,
                PRIMARY KEY (lead_id, draft_json)
            )
        """)
        saved = db.execute(
            """
            INSERT INTO draft_reviews (lead_id, draft_json, decision, reviewed_at)
            SELECT lead_id, ?, ?, ?
            FROM lead_analyses
            WHERE lead_id = ?
              AND json_extract(analysis_json, '$.follow_up_draft.subject') = ?
              AND json_extract(analysis_json, '$.follow_up_draft.body') = ?
            ON CONFLICT (lead_id, draft_json) DO UPDATE SET
                decision = excluded.decision,
                reviewed_at = excluded.reviewed_at
            """,
            (
                review.draft.model_dump_json(),
                review.decision,
                reviewed_at,
                str(lead_id),
                review.draft.subject,
                review.draft.body,
            ),
        )
        if saved.rowcount == 0:
            raise HTTPException(
                status_code=409, detail="Reload and review the current draft."
            )

    return {
        "lead_id": str(lead_id),
        "decision": review.decision,
        "reviewed_at": reviewed_at,
    }

class DraftReviewStatus(BaseModel):
    lead_id: UUID
    draft: FollowUpDraft
    decision: Literal["pending", "approved", "rejected"]
    reviewed_at: datetime | None = None


@router.get("/api/leads/{lead_id}/review")
def read_draft_review(lead_id: UUID) -> DraftReviewStatus:
    analysis = get_lead_analysis(lead_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="No saved analysis for this lead.")

    draft = analysis.follow_up_draft
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        table = db.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'draft_reviews'"
        ).fetchone()
        row = None
        if table is not None:
            row = db.execute(
                "SELECT decision, reviewed_at FROM draft_reviews "
                "WHERE lead_id = ? AND draft_json = ?",
                (str(lead_id), draft.model_dump_json()),
            ).fetchone()

    return DraftReviewStatus(
        lead_id=lead_id,
        draft=draft,
        decision=row[0] if row else "pending",
        reviewed_at=row[1] if row else None,
    )