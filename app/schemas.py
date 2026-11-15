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
    LARGE = "200+"

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
    