from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

class CompanySize(str, Enum):
    SOLO = "1"
    SMALL = "2-10"
    GROWING = "11-50"
    MEDIUM = "51-200"
    LARGE = "201+"

class ServiceNeeded(str, Enum):
    MANAGED_IT = "Managed IT"
    CYBERSECURITY = "Cybersecurity"
    AI_AUTOMATION = "AI Automation"
    WEB_DEVELOPMENT = "Web Development"
    OTHER = "Other"

class LeadCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    company_size: CompanySize
    service_needed: ServiceNeeded
    project_details: str = Field(min_length=20, max_length=5000)

class LeadReceipt(BaseModel):
    lead_id: UUID
    status: Literal["validated"]
    received_at: datetime
    message: str

class LeadUrgency(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class Department(str, Enum):
    IT_SUPPORT = "IT Support"
    SECURITY = "Security"
    AUTOMATION = "Automation"
    WEB = "Web Development"
    SALES = "Sales"

class FollowUpDraft(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )
    subject: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=3000)

class LeadAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    urgency: LeadUrgency
    fit_score: int = Field(strict=True, ge=0, le=100)
    pain_point_summary: str = Field(min_length=1, max_length=500)
    recommended_department: Department
    follow_up_draft: FollowUpDraft
    