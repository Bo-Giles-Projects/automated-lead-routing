from app.schemas import (
    Department,
    FollowUpDraft,
    LeadAnalysis,
    LeadCreate,
    LeadUrgency,
    ServiceNeeded,
)

DEPARTMENTS = {
    ServiceNeeded.MANAGED_IT: Department.IT_SUPPORT,
    ServiceNeeded.CYBERSECURITY: Department.SECURITY,
    ServiceNeeded.AI_AUTOMATION: Department.AUTOMATION,
    ServiceNeeded.WEB_DEVELOPMENT: Department.WEB,
    ServiceNeeded.OTHER: Department.SALES,
}

URGENT_SIGNALS = ("ransom note", "ransomware", "active breach", "systems are down")


def analyze_lead_mock(lead: LeadCreate) -> LeadAnalysis:
    department = DEPARTMENTS[lead.service_needed]
    details = lead.project_details.casefold()

    if any(signal in details for signal in URGENT_SIGNALS):
        urgency = LeadUrgency.HIGH
        next_step = "What is the best number for our team to reach you?"
    elif department == Department.SALES:
        urgency = LeadUrgency.LOW
        next_step = "Could you share what outcome you are looking for?"
    else:
        urgency = LeadUrgency.MEDIUM
        next_step = "Could you share your preferred timeline and availability for a call?"

    return LeadAnalysis(
        urgency=urgency,
        fit_score=25 if department == Department.SALES else 90,
        pain_point_summary=lead.project_details[:500],
        recommended_department=department,
        follow_up_draft=FollowUpDraft(
            subject=f"Following up on your {lead.service_needed.value} inquiry",
            body=(
                f"Hi {lead.name},\n\n"
                f"Thanks for reaching out about {lead.service_needed.value}. "
                f"{next_step}\n\n"
                "Best,\nThe team"
            ),
        ),
    )