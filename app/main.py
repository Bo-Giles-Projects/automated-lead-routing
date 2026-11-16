from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI

from app.enrichment import analyze_lead_mock
from app.schemas import LeadAnalysis, LeadCreate, LeadReceipt

from os import getenv

from app.openai_enrichment import analyze_lead_openai

from app.database import get_lead, get_lead_analysis, save_lead, save_lead_analysis

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
    receipt = LeadReceipt(
        lead_id=uuid4(),
        status="validated",
        received_at=datetime.now(timezone.utc),
        message="Lead validated and saved.",
    )
    save_lead(lead, receipt)
    return receipt

@app.post("/api/leads/analyze", response_model=LeadAnalysis, tags=["Leads"])
def preview_lead_analysis(lead: LeadCreate) -> LeadAnalysis:
    provider = getenv("AI_PROVIDER", "mock").strip().lower()

    if provider == "mock":
        return analyze_lead_mock(lead)

    if provider != "openai":
        raise HTTPException(status_code=503, detail="Unknown analysis provider.")

    if not getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OpenAI API key is missing.")

    try:
        return analyze_lead_openai(lead)
    except (OSError, RuntimeError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="OpenAI could not return a valid lead analysis.",
        ) from None

@app.post("/api/leads/{lead_id}/analyze", response_model=LeadAnalysis, tags=["Leads"])
def analyze_saved_lead(lead_id: UUID) -> LeadAnalysis:
    lead = get_lead(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found.")

    analysis = preview_lead_analysis(lead)
    save_lead_analysis(lead_id, analysis)
    return analysis

@app.get("/api/leads/{lead_id}/analysis", response_model=LeadAnalysis, tags=["Leads"])
def read_saved_analysis(lead_id: UUID) -> LeadAnalysis:
    analysis = get_lead_analysis(lead_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="No saved analysis for this lead.")

    return analysis