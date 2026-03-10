"""
API Route: POST /api/v1/export-cam
====================================
Accepts the full aggregated credit state as JSON and returns a
formatted Credit Appraisal Memo (.docx) as a downloadable file.

Input body mirrors the shape of the frontend credit state:
  {
    "entity_name":       "Acme Steels Pvt Ltd",
    "primary_insights":  "Plant visit notes from credit officer…",
    "pdf_scan":          { ... from POST /analyze-report response ... },
    "perfios":           { ... from GET /mock/perfios ... },
    "karza":             { ... from GET /mock/karza ... },
    "decision":          { ... accumulated penalty decision ... },
    "triggered_rules":   ["P-01", "P-03"],
    # Optional financial fields for C3/C4
    "net_worth":         "₹45 Cr",
    "debt_equity":       "0.82x",
    "ebitda_margin":     "22.4%",
    "current_ratio":     "1.4x",
    "proposed_security": "First charge on fixed assets",
    "security_coverage": "1.5x"
  }
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.utils.cam_generator import generate_cam

logger = logging.getLogger(f"pramaan.{__name__}")

router = APIRouter(tags=["CAM Export"])


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------
class CamRequest(BaseModel):
    entity_name:       str = "Unnamed Entity"
    primary_insights:  str = ""

    pdf_scan:   Optional[Dict[str, Any]] = None
    perfios:    Optional[Dict[str, Any]] = None
    karza:      Optional[Dict[str, Any]] = None
    decision:   Optional[Dict[str, Any]] = None
    restatement_data: Optional[Dict[str, Any]] = None
    news_data:  Optional[Dict[str, Any]] = None
    site_visit_scan: Optional[Dict[str, Any]] = None
    mca_data:   Optional[Dict[str, Any]] = None
    triggered_rules: list[str]           = []
    cross_verification: Optional[Dict[str, Any]] = None
    bank_statement: Optional[Dict[str, Any]] = None
    counterparty_intel: Optional[Dict[str, Any]] = None
    benchmark_data: Optional[Dict[str, Any]] = None
    network_data: Optional[Dict[str, Any]] = None

    # Capital / Collateral (optional free-text from officer)
    net_worth:          Optional[str] = None
    debt_equity:        Optional[str] = None
    ebitda_margin:      Optional[str] = None
    current_ratio:      Optional[str] = None
    proposed_security:  Optional[str] = None
    security_coverage:  Optional[str] = None


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.post(
    "/export-cam",
    summary="Export Credit Appraisal Memo (Word Document)",
    description=(
        "Accepts the aggregated credit state JSON and returns a "
        "formatted .docx Credit Appraisal Memo structured around the Five Cs of Credit. "
        "Fully deterministic — no LLM text generation."
    ),
    response_class=Response,
)
async def export_cam(body: CamRequest):
    """Generate and return the CAM .docx as a binary file download."""
    try:
        docx_bytes = generate_cam(body.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception(f"CAM generation error: {exc}")
        raise HTTPException(status_code=500, detail=f"CAM generation failed: {str(exc)}")

    filename = (
        f"CAM_{body.entity_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
    )

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
