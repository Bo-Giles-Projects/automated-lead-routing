from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI

from app.schemas import LeadCreate, LeadReceipt


app = FastAPI(
    title="Automated Lead Routing & Follow-Up",
    description=(
        "A proposal for an automated lead routing"
        " and follow-up system that leverages AI to "
        "enhance lead management and customer "
        "engagement."
    ),
    version="0.1.0",
)

@app.get("/health", tags=["System" ])
def health_check():
    return {"status": "ok"}


@app.post(
    "/api/leads",
    response_model=LeadReceipt,
    tags=["Leads"],
)
def create_lead(lead: LeadCreate) -> LeadReceipt:
    # FastAPI validates the body before this function runs.
    # Persistance and AI processing will be added in later steps.
    return LeadReceipt(
        lead_id = uuid4(),
        status = "validated",
        received_at = datetime.now(timezone.utc),
        message =(
        "Lead has been received and validated. "
        "This milestone does not store or process the lead."    
        ),
    ) 