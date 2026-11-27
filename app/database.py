import sqlite3
from contextlib import closing
from pathlib import Path
from app.schemas import LeadCreate, LeadReceipt
from uuid import UUID
from app.schemas import LeadAnalysis, LeadCreate, LeadReceipt, LeadAnalysis, LeadCreate, LeadReceipt

DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "leads.db"

def get_lead(lead_id: UUID) -> LeadCreate | None:
    if not DATABASE_PATH.is_file():
        return None

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT name, email, company_size, service_needed, project_details
            FROM leads
            WHERE id = ?
            """,
            (str(lead_id),),
        ).fetchone()

    return LeadCreate.model_validate(dict(row)) if row is not None else None


def _draft_is_locked(connection: sqlite3.Connection, lead_id: UUID) -> bool:
    """True once a person has acted on the lead's draft: approved it, edited it,
    or had an email queued from it. Rejections alone do not lock the draft."""
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('draft_reviews', 'draft_edits', 'email_outbox')"
        )
    }
    checks = {
        "draft_reviews": "SELECT 1 FROM draft_reviews WHERE lead_id = ? AND decision = 'approved'",
        "draft_edits": "SELECT 1 FROM draft_edits WHERE lead_id = ?",
        "email_outbox": "SELECT 1 FROM email_outbox WHERE lead_id = ?",
    }
    return any(
        connection.execute(query, (str(lead_id),)).fetchone() is not None
        for table, query in checks.items()
        if table in tables
    )


def draft_is_locked(lead_id: UUID) -> bool:
    if not DATABASE_PATH.is_file():
        return False
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        return _draft_is_locked(connection, lead_id)


def save_lead_analysis(
    lead_id: UUID, analysis: LeadAnalysis, *, unless_locked: bool = False
) -> bool:
    """Save or replace a lead's analysis. With unless_locked=True, refuse
    (return False) when a person has already acted on the current draft."""
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        # Lock writes so a review, edit or send cannot land between the check and the save.
        connection.execute("BEGIN IMMEDIATE")
        if unless_locked and _draft_is_locked(connection, lead_id):
            return False
        connection.execute("""
            CREATE TABLE IF NOT EXISTS lead_analyses (
                lead_id TEXT PRIMARY KEY REFERENCES leads(id),
                analysis_json TEXT NOT NULL
            )
        """)
        connection.execute(
            """
            INSERT INTO lead_analyses (lead_id, analysis_json)
            VALUES (?, ?)
            ON CONFLICT (lead_id) DO UPDATE
            SET analysis_json = excluded.analysis_json
            """,
            (str(lead_id), analysis.model_dump_json()),
        )
    return True

def save_lead(lead: LeadCreate, receipt: LeadReceipt) -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                received_at TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company_size TEXT NOT NULL,
                service_needed TEXT NOT NULL,
                project_details TEXT NOT NULL
            )
        """)
        connection.execute(
            """
            INSERT INTO leads (
                id, received_at, name, email, company_size,
                service_needed, project_details
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(receipt.lead_id),
                receipt.received_at.isoformat(),
                lead.name,
                lead.email,
                lead.company_size.value,
                lead.service_needed.value,
                lead.project_details,
            ),
        )

def get_lead_analysis(lead_id: UUID) -> LeadAnalysis | None:
    if not DATABASE_PATH.is_file():
        return None

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'lead_analyses'"
        ).fetchone()

        if table_exists is None:
            return None

        row = connection.execute(
            "SELECT analysis_json FROM lead_analyses WHERE lead_id = ?",
            (str(lead_id),),
        ).fetchone()

    return LeadAnalysis.model_validate_json(row[0]) if row is not None else None