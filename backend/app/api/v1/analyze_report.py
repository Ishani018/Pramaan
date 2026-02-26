"""
API Route: POST /api/v1/analyze-report
=======================================
Compliance-first Credit Appraisal scanner — zero LLM, fully deterministic.

Pipeline:
  1. SectionBoundaryDetector → locate 'Independent Auditor's Report'
                               and 'Annexure to Auditor's Report'
  2. extract_section_text()  → get raw text for each section
  3. ComplianceScanner.scan() → regex-based detection of:
       • CARO 2020 Clause (vii) statutory defaults     → P-03 trigger
       • Auditor qualifications (Except for / Adverse) → P-03 trigger
       • Emphasis of Matter / Going Concern             → P-04 flag

Returns boolean flags (caro_default_found, adverse_opinion_found) and
full traceability snippets so every finding can be walked back to the PDF.
"""
import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, Request
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool

from app.agents.deep_reader.section_boundary_detector import SectionBoundaryDetector
from app.agents.deep_reader.compliance_scanner import ComplianceScanner
from app.agents.deep_reader.financial_extractor import FinancialExtractor
from app.agents.deep_reader.detect_pdf_type import detect_pdf_type
from app.agents.deep_reader.extract_text import extract_text, get_full_text
from app.agents.restatement_detector import RestatementDetector
from app.agents.orchestrator import orchestrate_decision, BASE_RATE_PCT, BASE_LIMIT_CR
from app.agents.deep_reader.text_cleaner import clean_text

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_PAGES = 200


def _boundary_summary(boundary) -> dict | None:
    if boundary is None:
        return None
    return {
        "start_page": boundary.start_page,
        "end_page": boundary.end_page,
        "page_count": boundary.end_page - boundary.start_page + 1,
        "confidence": round(boundary.confidence, 3),
        "detected_heading": boundary.start_heading,
    }


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@router.post(
    "/analyze-report",
    summary="Compliance Scanner – Auditor Report Analysis",
    description=(
        "Upload corporate annual report PDFs. "
        "The engine locates the Independent Auditor's Report and its Annexure, "
        "then runs a deterministic compliance scan for CARO 2020 defaults and "
        "auditor qualifications. Returns boolean flags and penalty calculations. "
        "Supports multiple files (e.g., file_fy24, file_fy23)."
    ),
    tags=["Deep Reader"],
)
async def analyze_report(request: Request):
    """
    Deterministic compliance scan pipeline:
      PDF → section detection → text extraction → regex compliance scan → penalty calculation
    """
    import time
    start = time.time()
    def elapsed():
        return f"{time.time() - start:.1f}s"
        
    form = await request.form()
    # Extract all uploaded files (e.g. file_fy24, file_fy23)
    files = {
        k.split("_")[1].upper() if "_" in k else "LATEST": v 
        for k, v in form.items() 
        if k.startswith("file") and getattr(v, "filename", None)
    }
    
    if not files:
        raise HTTPException(status_code=400, detail="No PDF files provided in form data.")
    
    # Sort descending to get the most recent year (e.g., FY24 > FY23)
    sorted_years = sorted(files.keys(), reverse=True)
    latest_year = sorted_years[0]

    per_year_scans = {}
    
    for year in sorted_years:
        file_obj = files[year]
        if not file_obj.filename or not file_obj.filename.lower().endswith(".pdf"):
            logger.warning(f"Skipping non-PDF file for {year}: {file_obj.filename}")
            continue

        tmp_path: Path | None = None
        try:
            # ── Save upload ──────────────────────────────────────────────────────
            suffix = f"_{uuid.uuid4().hex}.pdf"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp_path = Path(tmp.name)
                contents = await file_obj.read()
                tmp.write(contents)

            logger.info(f"PDF received for {year}: {file_obj.filename} ({len(contents):,} bytes)")
            logger.info(f"[{elapsed()}] PDF opened")

            # ── Step 0: Detect PDF type & Limit ──────────────────────────────────
            pdf_type = detect_pdf_type(tmp_path)
            logger.info(f"PDF {file_obj.filename} detected as type: {pdf_type}. Respecting MAX_PAGES={MAX_PAGES}")

            # ── Step 1: Detect sections ──────────────────────────────────────────
            detector = SectionBoundaryDetector(tmp_path)
            from app.agents.deep_reader.section_boundary_detector import SECTION_CONFIGS
            auditor_cfg  = next(c for c in SECTION_CONFIGS if c["id"] == "auditors_report")
            annexure_cfg = next(c for c in SECTION_CONFIGS if c["id"] == "auditors_annexure")

            # Try to detect early termination in section detector
            auditor_boundary  = await run_in_threadpool(detector.detect_section, auditor_cfg, max_pages=MAX_PAGES)
            annexure_boundary = await run_in_threadpool(detector.detect_section, annexure_cfg, max_pages=MAX_PAGES)
            logger.info(f"[{elapsed()}] SectionBoundaryDetector done")

            if auditor_boundary is None and annexure_boundary is None:
                per_year_scans[year] = {
                    "status": "section_not_found",
                    "file_name": file_obj.filename,
                    "pdf_type": pdf_type,
                    "caro_default_found": False,
                    "adverse_opinion_found": False,
                    "emphasis_of_matter_found": False,
                    "triggered_rules": [],
                }
                continue

            # ── Step 2: Extract text ─────────────────────────────────────────────
            # Use the new robust text extraction pipeline, restricted to target pages
            target_pages = set()
            if auditor_boundary:
                target_pages.update(range(auditor_boundary.start_page, auditor_boundary.end_page + 1))
            if annexure_boundary:
                target_pages.update(range(annexure_boundary.start_page, annexure_boundary.end_page + 1))
                
            pages_data, extraction_stats = await run_in_threadpool(extract_text, tmp_path, pdf_type, pages_to_extract=list(target_pages))
            
            auditor_pages = [p for p in pages_data if auditor_boundary and auditor_boundary.start_page <= p.page_number <= auditor_boundary.end_page]
            annexure_pages = [p for p in pages_data if annexure_boundary and annexure_boundary.start_page <= p.page_number <= annexure_boundary.end_page]

            auditor_text = get_full_text(auditor_pages) if auditor_pages else ""
            annexure_text = get_full_text(annexure_pages) if annexure_pages else ""
            
            logger.info(f"[{elapsed()}] Text extraction done")

            total_chars = len(auditor_text) + len(annexure_text)
            
            if total_chars < 50:
                per_year_scans[year] = {
                    "status": "error",
                    "file_name": file_obj.filename,
                    "pdf_type": pdf_type,
                    "message": f"Sections detected but no text extracted (pdf_type={pdf_type}, coverage={extraction_stats.get('extraction_coverage', 0):.1f}%)."
                }
                continue

            # === NEW: APPLY BRSR TEXT CLEANING HERE ===
            auditor_text = await run_in_threadpool(clean_text, auditor_text)
            annexure_text = await run_in_threadpool(clean_text, annexure_text)
            # ==========================================

            # ── Step 3: Compliance scan ──────────────────────────────────────────
            try:
                scanner = ComplianceScanner()
                scan_result = await run_in_threadpool(
                    scanner.scan,
                    auditor_text=auditor_text,
                    annexure_text=annexure_text,
                )
                scan_dict = scan_result.to_dict()
            except Exception as e:
                logger.exception(f"ComplianceScanner failed for {year}: {e}")
                scan_dict = {
                    "caro_default_found": False,
                    "adverse_opinion_found": False,
                    "emphasis_of_matter_found": False,
                    "triggered_rules": [],
                    "caro_findings": [],
                    "auditor_qualification_findings": [],
                    "emphasis_findings": [],
                }
            logger.info(f"[{elapsed()}] ComplianceScanner done")

            # ── Step 4: Extract Financials ───────────────────────────────────────
            try:
                # User optimization 2: Only run extraction on the first 150 pages maximum.
                # Since the financials may be located earlier in the document than the auditor report,
                # we extract the first 150 pages explicitly for the extractor.
                fin_pages_data, _ = await run_in_threadpool(extract_text, tmp_path, pdf_type, pages_to_extract=list(range(1, 151)))
                fin_text = get_full_text(fin_pages_data)
                
                extractor = FinancialExtractor()
                extracted_figures = await run_in_threadpool(extractor.extract, text=fin_text, year=year)
            except Exception as e:
                logger.exception(f"FinancialExtractor failed for {year}: {e}")
                extracted_figures = {}
            logger.info(f"[{elapsed()}] FinancialExtractor done")

            # ── Store per-year result ────────────────────────────────────────────
            per_year_scans[year] = {
                "status": "success",
                "file_name": file_obj.filename,
                "pdf_type": pdf_type,
                "extraction_coverage": extraction_stats.get("extraction_coverage", 0),
                "sections_detected": {
                    "auditors_report": _boundary_summary(auditor_boundary),
                    "auditors_annexure": _boundary_summary(annexure_boundary),
                },
                "caro_default_found":        scan_dict.get("caro_default_found", False),
                "adverse_opinion_found":     scan_dict.get("adverse_opinion_found", False),
                "emphasis_of_matter_found":  scan_dict.get("emphasis_of_matter_found", False),
                "triggered_rules":           scan_dict.get("triggered_rules", []),
                "caro_findings":             scan_dict.get("caro_findings", []),
                "auditor_qualification_findings":  scan_dict.get("auditor_qualification_findings", []),
                "emphasis_findings":         scan_dict.get("emphasis_findings", []),
                "extracted_figures":         extracted_figures,
            }
        
        except Exception as exc:
            logger.exception(f"Error scanning {year}: {exc}")
            per_year_scans[year] = {"status": "error", "message": str(exc)}
        
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)


    # ── Step 5: Restatement Detection ────────────────────────────────────────
    try:
        scans_for_restatement = { y: data.get("extracted_figures", {}) for y, data in per_year_scans.items() if data.get("status", "") == "success" }
        restatement_detector = RestatementDetector()
        restatement_data = await run_in_threadpool(restatement_detector.compare, scans=scans_for_restatement)
    except Exception as e:
        logger.exception(f"RestatementDetector failed: {e}")
        restatement_data = {
            "restatements_detected": False,
            "restatements": [],
            "auditor_changed": False,
            "auditor_history": {}
        }
    logger.info(f"[{elapsed()}] RestatementDetector done")

    if latest_year not in per_year_scans or per_year_scans[latest_year].get("status") == "error":
        raise HTTPException(status_code=422, detail="Failed to parse the most recent primary report.")

    # Top-level response uses the most recent year's data to avoid breaking existing frontend logic
    latest_scan = per_year_scans[latest_year]
    
    if latest_scan.get("status") == "section_not_found":
        return JSONResponse(
            status_code=200,
            content={
                **latest_scan,
                "message": "Neither the Independent Auditor's Report nor its Annexure could be located.",
                "decision": orchestrate_decision(None, None, None, restatement_data=restatement_data),
                "per_year_scans": per_year_scans,
                "restatement_data": restatement_data,
            }
        )

    decision = orchestrate_decision(
        pdf_scan_result=latest_scan,
        perfios_data=None,      
        karza_data=None,        
        restatement_data=restatement_data,
    )
    logger.info(f"[{elapsed()}] Orchestrator done")

    return {
        **latest_scan,
        "pdf_type": latest_scan.get("pdf_type", "unknown"),
        "extraction_coverage": latest_scan.get("extraction_coverage", 0),
        "total_caro_matches": len(latest_scan.get("caro_findings", [])),
        "total_qualification_matches": len(latest_scan.get("auditor_qualification_findings", [])),
        "decision": decision,
        "per_year_scans": per_year_scans,
        "restatement_data": restatement_data,
        "methodology": (
            "All findings are extracted by deterministic regex — zero LLM calls. "
            "Every snippet is traceable to the original PDF text. "
            "Rate and limit penalties are computed by a transparent accumulator model."
        )
    }
