import sqlite3
from contextlib import closing
from pathlib import Path

from app.schemas import LeadCreate, LeadReceipt

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


def save_lead_analysis(lead_id: UUID, analysis: LeadAnalysis) -> None:
    with closing(sqlite3.connect(DATABASE_PATH)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
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