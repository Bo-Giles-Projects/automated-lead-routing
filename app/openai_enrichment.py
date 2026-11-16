import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from app.schemas import LeadAnalysis, LeadCreate

PROMPT_PATH = Path(__file__).parent / "prompts" / "lead_enrichment.txt"


def analyze_lead_openai(lead: LeadCreate) -> LeadAnalysis:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in this PowerShell session first.")

    payload = {
        "model": "gpt-5-mini",
        "instructions": PROMPT_PATH.read_text(encoding="utf-8-sig"),
        "input": lead.model_dump_json(
            include={"company_size", "service_needed", "project_details"}
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "lead_analysis",
                "schema": LeadAnalysis.model_json_schema(),
                "strict": True,
            }
        },
        "max_output_tokens": 1500,
        "store": False,
    }

    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("status") == "completed":
        for item in result.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        return LeadAnalysis.model_validate_json(part["text"])

    raise RuntimeError("OpenAI did not return a complete lead analysis.")