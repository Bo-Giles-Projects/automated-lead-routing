# Automated Lead Routing & Follow-Up

A Python automation project exploring how small-to-medium businesses
can organize customer inquiries, prioritize leads, and prepare
personalized follow-ups with human oversight.

## Project Status

**Current milestone: Lead capture, validation, and mock analysis.**

Implemented:
- FastAPI endpoint for customer inquiries
- Required-field and email-format validation
- Supported company-size and service categories
- Unique receipt IDs and UTC timestamps
- Interactive API documentation
- `POST /api/leads/analyze` previews urgency,
fit score, department,
a short summary, and an email draft using local Python rules.

Planned:
- Database storage
- AI-powered summaries, urgency classification, and lead-fit scoring
- CRM integration and internal sales alerts
- AI-generated personalized follow-up email drafts
- Human approval before email delivery

## Business Value

The completed system aims to reduce manual lead sorting, improve
response consistency, and help staff identify urgent inquiries.

Performance improvements and time savings have not yet been measured.

## Technology

- Python 3.11+
- FastAPI
- Pydantic
- Uvicorn
- Git and GitHub

## Local Setup — Windows PowerShell

Clone the repository and enter its folder:

```powershell
git clone https://github.com/Bo-Giles-Projects/automated-lead-routing.git
cd automated-lead-routing
```

Create a virtual environment and install dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1
```

Open http://127.0.0.1:8000/docs for interactive API documentation.

## Try a Lead

Expand `POST /api/leads`, select **Try it out**, and submit:

```json
{
  "name": "Jordan Taylor",
  "email": "jordan@example.com",
  "company_size": "11-50",
  "service_needed": "Cybersecurity",
  "project_details": "Several employees cannot access shared files, and a ransom note appeared on one workstation this morning. We need urgent help assessing the incident and restoring business operations."
}
```
Submit the same JSON to POST /api/leads/analyze to preview the analysis. This sample returns High urgency, a fit score of 90, and Security as the recommended department.

A valid request returns HTTP 200 with a validation receipt.
An invalid email or missing required field returns HTTP 422.

## Run the Tests

Install the development dependencies and run the suite:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

Each test uses its own temporary SQLite database and the mock analysis
provider, so it needs no API key and never touches `data/leads.db`.
`tests/test_approval.py` covers the human-approval rules: an email is
queued only for the exact saved draft a reviewer approved, a changed
draft needs fresh approval, and repeated sends queue just one email.

GitHub Actions runs the suite on Python 3.11 and 3.13 for every pull
request and every push to `main` (`.github/workflows/tests.yml`).

## Responsible Automation

Current safeguards:
- Validate required fields, allowed values, and text lengths.
- Reject unexpected request fields.
- Use fictional information in sample submissions.
- Exclude environment secrets and local databases through `.gitignore`.

Planned AI safeguards:
- Treat customer text as untrusted input.
- Validate structured AI responses.
- Minimize personal information sent to external providers.
- Require human approval before sending emails.
- Track approval and delivery status.

## Current Limitations

Lead analysis currently uses local rules and runs without an API key.
The preview returns an email draft for review. Lead storage, alerts,
and email delivery are planned.

This is a local development project. Authentication and production
abuse controls are not implemented.