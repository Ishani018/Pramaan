"""
API Route: POST /api/v1/decision-narrative
====================================
Accepts aggregated credit state as JSON and returns a step-by-step plain English narrative.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.agents.orchestrator import generate_decision_narrative

router = APIRouter(tags=["Decision Narrative"])


class DecisionNarrativeRequest(BaseModel):
    decision:          Dict[str, Any]
    triggered_rules:   List[str] = []
    pdf_scan:          Optional[Dict[str, Any]] = None
    perfios_data:      Optional[Dict[str, Any]] = None
    restatement_data:  Optional[Dict[str, Any]] = None


@router.post(
    "/decision-narrative",
    summary="Get step-by-step decision narrative",
    description="Returns a plain-English explanation of the credit decision."
)
async def get_decision_narrative(body: DecisionNarrativeRequest):
    return generate_decision_narrative(
        decision=body.decision,
        triggered_rules=body.triggered_rules,
        pdf_scan=body.pdf_scan,
        perfios_data=body.perfios_data,
        restatement_data=body.restatement_data,
    )
