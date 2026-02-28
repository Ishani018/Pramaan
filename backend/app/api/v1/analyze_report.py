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
import traceback
from fastapi.concurrency import run_in_threadpool

from app.agents.deep_reader.section_boundary_detector import SectionBoundaryDetector
from app.agents.deep_reader.compliance_scanner import ComplianceScanner
from app.agents.deep_reader.financial_extractor import FinancialExtractor
from app.agents.deep_reader.detect_pdf_type import detect_pdf_type
from app.agents.deep_reader.extract_text import extract_text, get_full_text, extract_text_with_pymupdf
from app.agents.restatement_detector import RestatementDetector
from app.agents.orchestrator import orchestrate_decision, BASE_RATE_PCT, BASE_LIMIT_CR
from app.agents.deep_reader.text_cleaner import clean_text
from app.api.v1.external_mocks import _last_entity
from app.agents.external.news_scanner import NewsScanner
from app.agents.primary.site_visit_scanner import SiteVisitScanner
from app.agents.external.mca_scanner import MCAScanner
import os
from app.core.config import settings
logger = logging.getLogger(__name__)

router = APIRouter()

import fitz

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
        
    try:
        print("=== NEW CODE RUNNING ===")
        logger.info("=== PIPELINE START ===")
        logger.info(f"Files in request: attempting to read form data")
        form = await request.form()
        logger.info(f"Form data keys: {list(form.keys())}")
        
        site_visit_notes = form.get("site_visit_notes", "")

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
                    # 🚀 FIX: Use PyMuPDF directly for the bulk 150-page extraction!
                    # It is magnitudes faster than pdfplumber and prevents timeouts.
                    fin_pages_data, _ = await run_in_threadpool(
                        extract_text_with_pymupdf, 
                        tmp_path, 
                        pages_to_extract=list(range(1, 151))
                    )
                    fin_text = get_full_text(fin_pages_data)
                    
                    extractor = FinancialExtractor()
                    extracted_figures = await run_in_threadpool(extractor.extract, text=fin_text, year=year)
                    logger.info(f"Financial figures: {extracted_figures}")
                    logger.info(f"FINANCIAL KEYS: {list(extracted_figures.keys()) if extracted_figures else 'None'}")
                    logger.info(f"FINANCIAL VALUES: {extracted_figures}")
                except Exception as e:
                    logger.exception(f"FinancialExtractor failed for {year}: {e}")
                    extracted_figures = {}
                logger.info(f"[{elapsed()}] FinancialExtractor done")
                
                # ── Step 4.2: MCA Scan ───────────────────────────────────────────────
                try:
                    mca_scanner = MCAScanner()
                    mca_data = await run_in_threadpool(mca_scanner.scan, text=fin_text, entity_name=_last_entity["name"])
                    logger.info(f"[{elapsed()}] MCAScanner done — status={mca_data.company_status}, cin={mca_data.cin}")
                except Exception as e:
                    logger.exception(f"MCAScanner failed for {year}: {e}")
                    mca_data = None

                # ── Step 4.5: News Scan ──────────────────────────────────────────────
                try:
                    import fitz
                    import re
                    
                    doc = fitz.open(str(tmp_path))
                    first_page_text = doc[0].get_text("text")
                    doc.close()
                    
                    # === INCORPORATED BRSR EXTRACTION LOGIC ===
                    def extract_entity_name(fname: str, page_text: str) -> str:
                        base = fname.replace('.pdf', '')
                        name = None
                        
                        # 1. Regex parsing from BRSR file_naming.py 
                        match = re.search(r'^(.+?)[_-](?:Annual(?:_|\s)?Report|BRSR)', base, re.IGNORECASE)
                        if match:
                            name = match.group(1).replace('_', ' ').strip()
                        else:
                            # Reverse extraction for "AnnualReport_2019CDEL"
                            cln = re.sub(r'(?i)(annual_?report|brsr|financial_?statements)', '', base)
                            cln = re.sub(r'20\d{2}[_-]?(\d{2})?', '', cln) # Strip years
                            cln = re.sub(r'[\d_]', ' ', cln).strip()
                            if cln and len(cln) > 2:
                                name = cln
                        
                        # 2. PDF Text Fallback (Improved to skip dates & generic words)
                        if not name or len(name) <= 4:
                            lines = [l.strip() for l in page_text.split('\n') if l.strip()]
                            for i, line in enumerate(lines):
                                if "annual report" in line.lower() and i > 0:
                                    # Look at up to 2 lines above to find a valid company name
                                    for offset in (1, 2):
                                        if i - offset >= 0:
                                            potential = lines[i-offset]
                                            # Skip dates ("2023-24", "FY24") and generic report words
                                            is_date_or_generic = re.search(r'(20\d{2}|\bFY\d{2}\b|Integrated|Statutory|Financial)', potential, re.IGNORECASE)
                                            if len(potential) > 4 and not potential.isnumeric() and not is_date_or_generic:
                                                if not name or len(potential) > len(name):
                                                    name = potential
                                                break 
                                    if name and len(name) > 4:
                                        break
                                        
                        if not name:
                            name = base

                        # 3. Dirty Character Sanitization (from BRSR file_naming.py)
                        name = re.sub(r'[\\/*?:"<>|()\[\]]', '', name)
                            
                        # 4. Suffix Cleaning (Sorted by length!)
                        name = re.sub(r'\s+', ' ', name).strip()
                        suffixes = [
                            " Private Limited", " Pvt. Ltd.", " Pvt Ltd", 
                            " Corporation", " Limited", " Ltd.", " Ltd", 
                            " Inc.", " Inc", " Corp.", " Corp"
                        ]
                        
                        # Keep stripping until clean (handles trailing periods and stacked suffixes)
                        cleaning = True
                        while cleaning:
                            cleaning = False
                            name = name.strip(',.- ') 
                            for suf in suffixes:
                                if name.lower().endswith(suf.lower()):
                                    name = name[:-len(suf)].strip()
                                    cleaning = True
                                    break 
                                
                        # 5. Symbol Lookup Mapper
                        symbol_map = {
                            "CDEL": "Coffee Day Enterprises",
                            "TCS": "Tata Consultancy Services"
                        }
                        return symbol_map.get(name.upper(), name)

                    entity_name = extract_entity_name(file_obj.filename, first_page_text)
                    # ==========================================
                    
                    
                    # Update the external mocks with the real entity name
                    from app.api.v1.external_mocks import set_entity, EntityUpdate
                    cin_str = mca_data.cin if (mca_data and getattr(mca_data, "cin", "")) else ("L15122KA2008PLC047538" if "coffee" in entity_name.lower() else "U27100MH2010PTC123456")
                    await set_entity(EntityUpdate(entity_name=entity_name, cin=cin_str))

                    # Use Pydantic settings instead of os.getenv
                    api_key = settings.NEWS_API_KEY
                    if api_key:
                        news_scanner = NewsScanner(api_key=api_key)
                        news_data = await news_scanner.scan(entity_name)
                    else:
                        logger.warning("NEWS_API_KEY is missing or empty. Skipping News Scan.")
                        news_data = None
                except Exception as e:
                    logger.exception(f"NewsScanner failed for {year}: {e}")
                    news_data = None
                logger.info(f"[{elapsed()}] NewsScanner done")

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
                    "emphasis_findings":         scan_dict.get("emphasis_findings", []),
                    "extracted_figures":         extracted_figures,
                    "news_data":                 news_data,
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
            real_error_msg = per_year_scans.get(latest_year, {}).get("message", "Unknown error")
            logger.error(f"PIPELINE ABORTED. Reason: {real_error_msg}")
            raise HTTPException(
                status_code=422, 
                detail=f"Failed to parse report. Reason: {real_error_msg}"
            )

        # Top-level response uses the most recent year's data to avoid breaking existing frontend logic
        latest_scan = per_year_scans[latest_year]
        
        # ── Step 6: Site Visit Scanner ───────────────────────────────────────────
        try:
            site_visit_scanner = SiteVisitScanner()
            site_visit_scan_obj = site_visit_scanner.scan(site_visit_notes)
            site_visit_scan = {
                "triggered_rules": site_visit_scan_obj.triggered_rules,
                "findings": site_visit_scan_obj.findings,
                "notes_provided": site_visit_scan_obj.notes_provided,
                "capacity_utilisation_pct": site_visit_scan_obj.capacity_utilisation_pct
            }
        except Exception as e:
            logger.exception(f"SiteVisitScanner failed: {e}")
            site_visit_scan = {"triggered_rules": [], "findings": [], "notes_provided": False, "capacity_utilisation_pct": None}
        
        # ── Step 7: Orchestrate Final Decision ───────────────────────────────────
        
        all_triggered_rules = latest_scan.get("triggered_rules", [])
        if site_visit_scan and site_visit_scan.get("triggered_rules"):
            for rule in site_visit_scan["triggered_rules"]:
                if rule not in all_triggered_rules:
                    all_triggered_rules.append(rule)
        
        if mca_data and mca_data.triggered_rules:
            for rule in mca_data.triggered_rules:
                if rule not in all_triggered_rules:
                    all_triggered_rules.append(rule)
                    
        latest_scan["triggered_rules"] = all_triggered_rules
        logger.info(f"ALL RULES GOING TO ORCHESTRATOR: {all_triggered_rules}")
        
        if latest_scan.get("status") == "section_not_found":
            return JSONResponse(
                status_code=200,
                content={
                    **latest_scan,
                    "message": "Neither the Independent Auditor's Report nor its Annexure could be located.",
                    "decision": orchestrate_decision(None, None, None, restatement_data=restatement_data, news_data=latest_scan.get("news_data"), site_visit_scan=site_visit_scan, mca_data={"triggered_rules": getattr(mca_data, "triggered_rules", [])} if mca_data else None),
                    "per_year_scans": per_year_scans,
                    "restatement_data": restatement_data,
                }
            )

        decision = orchestrate_decision(
            pdf_scan_result=latest_scan,
            perfios_data=None,      
            karza_data=None,        
            restatement_data=restatement_data,
            news_data=latest_scan.get("news_data"),
            site_visit_scan=site_visit_scan,
            mca_data={"triggered_rules": getattr(mca_data, "triggered_rules", [])} if mca_data else None
        )
        logger.info(f"[{elapsed()}] Orchestrator done")

        logger.info(f"FINAL RESPONSE entity_name = '{entity_name}'")
        
        mca_dict = {
            "company_name": getattr(mca_data, "company_name", ""),
            "cin": getattr(mca_data, "cin", ""),
            "company_status": getattr(mca_data, "company_status", "Unknown"),
            "date_of_incorporation": getattr(mca_data, "date_of_incorporation", ""),
            "registered_state": getattr(mca_data, "registered_state", ""),
            "registered_address": getattr(mca_data, "registered_address", ""),
            "business_activity": getattr(mca_data, "business_activity", ""),
            "paid_up_capital": getattr(mca_data, "paid_up_capital", 0.0),
            "is_struck_off": getattr(mca_data, "is_struck_off", False),
            "directors": getattr(mca_data, "directors", []),
            "total_charges_cr": getattr(mca_data, "total_charges_cr", 0.0),
            "charge_holders": getattr(mca_data, "charge_holders", []),
            "findings": getattr(mca_data, "findings", []),
            "source": getattr(mca_data, "source", "MCA21")
        } if mca_data else None
        
        logger.info(f"MCA in response: {mca_dict or 'MISSING'}")

        return {
            **latest_scan,
            "pdf_type": latest_scan.get("pdf_type", "unknown"),
            "extraction_coverage": latest_scan.get("extraction_coverage", 0),
            "entity_name": entity_name,
            "total_caro_matches": len(latest_scan.get("caro_findings", [])),
            "total_qualification_matches": len(latest_scan.get("auditor_qualification_findings", [])),
            "decision": decision,
            "all_triggered_rules": decision.get("triggered_rules", []),
            "per_year_scans": per_year_scans,
            "restatement_data": restatement_data,
            "news": latest_scan.get("news_data") or {
                "entity": _last_entity["name"],
                "articles_found": 0,
                "red_flags": [],
                "adverse_media_detected": False
            },
            "mca": mca_dict,
            "site_visit_scan": site_visit_scan,
            "methodology": (
                "All findings are extracted by deterministic regex — zero LLM calls. "
                "Every snippet is traceable to the original PDF text. "
                "Rate and limit penalties are computed by a transparent accumulator model."
            )
        }
    except Exception as inner_e:
        error_detail = traceback.format_exc()
        logger.error(f"=== PIPELINE CRASH ===\n{error_detail}")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(inner_e),
                "traceback": error_detail,
                "status": "crashed"
            }
        )
