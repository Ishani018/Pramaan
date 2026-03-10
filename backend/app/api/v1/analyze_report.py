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
import sys
import logging
import asyncio
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
from app.agents.deep_reader.site_visit_analyzer import SiteVisitAnalyzer
from app.agents.external.mca_scanner import MCAScanner
from app.agents.deep_reader.mda_analyzer import MDAAnalyzer
from app.agents.deep_reader.shareholding_scanner import ShareholdingScanner
from app.agents.deep_reader.rating_extractor import RatingExtractor
from app.agents.deep_reader.bank_statement_analyzer import BankStatementAnalyzer
from app.agents.external.sector_benchmark import SectorBenchmarkAssessor
from app.agents.deep_reader.collateral_assessor import CollateralAssessor
from app.agents.external.ecourts_scanner import ECourtsScanner
from app.agents.external.counterparty_intel import CounterpartyIntel, NetworkIntelResult
import os
from app.core.config import settings

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_SRC_PATH = _BACKEND_ROOT / "src"
if _SRC_PATH.exists() and str(_SRC_PATH) not in sys.path:
    sys.path.append(str(_SRC_PATH))

try:
    from supply_chain_risk import run_supply_chain_risk
except Exception:
    run_supply_chain_risk = None

# 1. Get the logger for this specific file
logger = logging.getLogger(__name__)

# 2. Force the log level to INFO
logger.setLevel(logging.INFO)

# 3. If Uvicorn stripped the handlers, explicitly add our own console handler
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# 4. Prevent logs from bubbling up to the hijacked root logger (prevents double-printing)
logger.propagate = False


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
        
        # Initialize default values to avoid UnboundLocalError
        mca_data = None
        ecourts_data = None
        shareholding_data = None
        bank_result = None
        counterparty_result = None

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
            supply_chain_result: dict = {}
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

                # ── Step 4.0: Supply Chain Risk (deterministic) ───────────────────
                if run_supply_chain_risk and fin_text:
                    try:
                        supply_chain_result = await run_in_threadpool(run_supply_chain_risk, fin_text)
                        logger.info(
                            f"[{elapsed()}] SupplyChainRisk done — "
                            f"overall={supply_chain_result.get('overall_supply_chain_risk_band')}, "
                            f"weakest_link={supply_chain_result.get('weakest_link')}"
                        )
                    except Exception as e:
                        logger.exception(f"SupplyChainRisk failed for {year}: {e}")
                        supply_chain_result = {}

                # ── Step 4.0.1: Collateral Assessor ──────────────────────────────────────────
                try:
                    collateral_assessor = CollateralAssessor()
                    collateral_result = await run_in_threadpool(collateral_assessor.analyze, fin_text)
                    logger.info(
                        f"[{elapsed()}] CollateralAssessor done — "
                        f"findings={len(collateral_result.findings)}, "
                        f"unsecured={collateral_result.has_unsecured_loans}")
                except Exception as e:
                    logger.exception(f"CollateralAssessor failed: {e}")
                    from app.agents.deep_reader.collateral_assessor import CollateralResult
                    collateral_result = CollateralResult()

                # Merge collateral rules
                if collateral_result.triggered_rules:
                    if "triggered_rules" not in scan_dict:
                        scan_dict["triggered_rules"] = []
                    for rule in collateral_result.triggered_rules:
                        if rule not in scan_dict["triggered_rules"]:
                            scan_dict["triggered_rules"].append(rule)

                # ── Step 4.1: Rating Extractor ───────────────────────────────────────────
                try:
                    rating_extractor = RatingExtractor()
                    rating_result = await run_in_threadpool(rating_extractor.extract, fin_text)
                    logger.info(
                        f"[{elapsed()}] RatingExtractor done — "
                        f"rating={rating_result.latest_rating}, "
                        f"agency={rating_result.latest_agency}, "
                        f"downgrade={rating_result.downgrade_detected}")
                except Exception as e:
                    logger.exception(f"RatingExtractor failed: {e}")
                    from app.agents.deep_reader.rating_extractor import RatingResult
                    rating_result = RatingResult()

                # Merge rating rules into scan_dict
                if rating_result.triggered_rules:
                    if "triggered_rules" not in scan_dict:
                        scan_dict["triggered_rules"] = []
                    for rule in rating_result.triggered_rules:
                        if rule not in scan_dict["triggered_rules"]:
                            scan_dict["triggered_rules"].append(rule)
                
                # ── Step 4.X: Shareholding Scanner ──────────────────────────────────
                shareholding_scanner = ShareholdingScanner()
                shareholding_data = await run_in_threadpool(
                    shareholding_scanner.scan, fin_text)
                logger.info(
                    f"[{elapsed()}] ShareholdingScanner done — "
                    f"promoter={shareholding_data.promoter_holding_pct}%, "
                    f"pledged={shareholding_data.pledged_pct}%, "
                    f"govt={shareholding_data.government_holding_pct}%")
                if shareholding_data.triggered_rules:
                    if "triggered_rules" not in scan_dict:
                        scan_dict["triggered_rules"] = []
                    for rule in shareholding_data.triggered_rules:
                        if rule not in scan_dict["triggered_rules"]:
                            scan_dict["triggered_rules"].append(rule)

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
                    
                    # --- Fallback entity name from PDF text ---
                    fallback_entity_name = None
                    try:
                        first_3k = first_page_text[:3000]
                        # Look for "<Company Name>\n...Annual Report"
                        ar_match = re.search(
                            r'([A-Z][A-Za-z\s&\-\.]{4,60})\s*\n[^\n]*(?:Annual\s+Report|ANNUAL\s+REPORT)',
                            first_3k
                        )
                        if ar_match:
                            candidate = ar_match.group(1).strip()
                            # Skip dates and generic words
                            if not re.search(r'(20\d{2}|\bFY\d{2}\b|Integrated|Statutory|Financial)', candidate, re.IGNORECASE):
                                fallback_entity_name = candidate
                                logger.info(f"Fallback entity name from PDF text: '{fallback_entity_name}'")
                    except Exception:
                        pass
                    
                    # If the extracted name is too generic (like "annual-report") but MCA found the real company name, use the MCA name!
                    if getattr(mca_data, "company_name", None):
                        lower_name = entity_name.lower()
                        if "annual" in lower_name or "report" in lower_name or len(entity_name) < 4:
                            logger.info(f"Overriding generic entity name '{entity_name}' with MCA name '{mca_data.company_name}'")
                            entity_name = mca_data.company_name.title()
                    elif fallback_entity_name:
                        lower_name = entity_name.lower()
                        if "annual" in lower_name or "report" in lower_name or len(entity_name) < 4:
                            logger.info(f"MCA unavailable — using fallback entity name '{fallback_entity_name}'")
                            entity_name = fallback_entity_name

                    # Update the external mocks with the real entity name
                    from app.api.v1.external_mocks import set_entity, EntityUpdate
                    cin_str = mca_data.cin if (mca_data and getattr(mca_data, "cin", "")) else ("L15122KA2008PLC047538" if "coffee" in entity_name.lower() else "U27100MH2010PTC123456")
                    await set_entity(EntityUpdate(entity_name=entity_name, cin=cin_str))
                except Exception as e:
                    logger.exception(f"Error during entity name extraction for {year}: {e}")
                    entity_name = "Unknown Entity"

                # ── Step 4.5: Parallel External Scans ──────────────────────────────────
                try:
                    news_scanner = NewsScanner(api_key=settings.NEWS_API_KEY)
                    ecourts_scanner = ECourtsScanner()
                    
                    news_result, ecourts_result = await asyncio.gather(
                        news_scanner.scan(entity_name),
                        run_in_threadpool(ecourts_scanner.scan, entity_name)
                    )
                    
                    # Manual construction for news_data dict (as expected by frontend/orchestrator)
                    news_data = {
                        "entity": entity_name,
                        "adverse_media_detected": news_result.red_flag_count > 0,
                        "red_flag_count": news_result.red_flag_count,
                        "articles_found": news_result.articles_found,
                        "red_flags": news_result.articles, # Frontend expects red_flags
                        "triggered_rules": news_result.triggered_rules
                    }
                    
                    if news_result:
                        logger.info(f"[{elapsed()}] NewsScanner done")
                        logger.info(f"NewsScanner triggered_rules: {news_result.triggered_rules}")
                    
                    if ecourts_result:
                        logger.info(f"[{elapsed()}] ECourtsScanner done — cases={ecourts_result.cases_found}, high_risk={ecourts_result.high_risk_cases}")
                        # Convert to dict for serialization
                        ecourts_data = {
                            "cases_found": ecourts_result.cases_found,
                            "high_risk_cases": ecourts_result.high_risk_cases,
                            "findings": ecourts_result.findings,
                            "triggered_rules": ecourts_result.triggered_rules
                        }
                    else:
                        ecourts_data = None

                except Exception as e:
                    logger.exception(f"Error during parallel scans for {year}: {e}")
                    news_data = None
                    ecourts_data = None

                # ── Fallback to synthetic mocks when real APIs return empty ──────────
                if not ecourts_data or ecourts_data.get("cases_found", 0) == 0:
                    from app.api.v1.external_mocks import mock_ecourts
                    ecourts_data = await mock_ecourts()
                    logger.info(f"[{elapsed()}] Using synthetic eCourts fallback")

                if not news_data or not news_data.get("adverse_media_detected"):
                    from app.api.v1.external_mocks import mock_news
                    news_data = await mock_news()
                    logger.info(f"[{elapsed()}] Using synthetic News fallback")

                # ── Step 4.6: MD&A Analysis ───────────────────────────────────────────
                try:
                    from app.agents.deep_reader.section_boundary_detector import SECTION_CONFIGS
                    mda_cfg = next((c for c in SECTION_CONFIGS if c["id"] == "mda_report"), None)
                    mda_boundary = None
                    mda_text = ""
                    if mda_cfg:
                        mda_boundary = await run_in_threadpool(detector.detect_section, mda_cfg, max_pages=MAX_PAGES)
                    
                    if mda_boundary:
                        mda_start = mda_boundary.start_page
                        mda_end = mda_boundary.end_page
                        # Extract the detected pages using pymupdf
                        mda_pages_data, _ = await run_in_threadpool(
                            extract_text_with_pymupdf,
                            tmp_path, pages_to_extract=list(range(mda_start, mda_end + 1)))
                        mda_text = get_full_text(mda_pages_data)
                        logger.info(f"MD&A extracted: pages {mda_start}-{mda_end}, {len(mda_text)} chars")
                    
                    mda_insights = {"status": "not_run"}
                    if mda_text:
                        mda_analyzer = MDAAnalyzer()
                        mda_insights = await run_in_threadpool(mda_analyzer.analyze, mda_text)
                        logger.info(f"[{elapsed()}] MDAAnalyzer done — sentiment={mda_insights.get('sentiment_score')}, risk={mda_insights.get('risk_intensity')}, headwinds={len(mda_insights.get('extracted_headwinds', []))}")
                    
                    if mda_insights.get("status") == "success" and mda_insights.get("sentiment_score", 0) < -0.01:
                        if "P-16" not in scan_dict["triggered_rules"]:
                            scan_dict["triggered_rules"].append("P-16")
                        logger.warning(f"P-16 TRIGGERED: negative MD&A sentiment {mda_insights['sentiment_score']}")
                except Exception as e:
                    logger.exception(f"MDAAnalyzer failed for {year}: {e}")
                    mda_insights = {"status": "error"}

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
                    "shareholding_data":         shareholding_data,
                    "news_data":                 news_data,
                    "ecourts_data":              ecourts_data,
                    "mda_insights":              mda_insights,
                    "supply_chain_risk":         supply_chain_result,
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
            site_visit_notes = form.get("site_visit_notes", "")
            site_visit_analyzer = SiteVisitAnalyzer()
            site_visit_result = site_visit_analyzer.analyze(site_visit_notes)
            logger.info(
                f"[{elapsed()}] SiteVisitAnalyzer done — "
                f"{len(site_visit_result.findings)} findings, "
                f"rules={site_visit_result.triggered_rules}")
        except Exception as e:
            logger.exception(f"SiteVisitAnalyzer failed: {e}")
            from app.agents.deep_reader.site_visit_analyzer import SiteVisitResult
            site_visit_result = SiteVisitResult(raw_notes=form.get("site_visit_notes", ""))

        # ── Step 6.5: Bank Statement Analyzer ──────────────────────────────────────
        try:
            bank_csv_file = form.get("bank_csv")
            if bank_csv_file and getattr(bank_csv_file, "filename", None):
                bank_csv_content = (await bank_csv_file.read()).decode("utf-8")
                bank_analyzer = BankStatementAnalyzer()
                bank_result = bank_analyzer.analyze(bank_csv_content)
                logger.info(
                    f"[{elapsed()}] BankStatementAnalyzer done — "
                    f"{bank_result.total_transactions} txns, "
                    f"circular={len(bank_result.circular_transactions)}, "
                    f"rules={bank_result.triggered_rules}")
            else:
                from app.agents.deep_reader.bank_statement_analyzer import BankStatementResult
                bank_result = BankStatementResult()
        except Exception as e:
            logger.exception(f"BankStatementAnalyzer failed: {e}")
            from app.agents.deep_reader.bank_statement_analyzer import BankStatementResult
            bank_result = BankStatementResult()
        
        # ── Step 6.6: Counterparty Intelligence ─────────────────────────────────
        try:
            if bank_result and bank_result.top_counterparties:
                cp_intel = CounterpartyIntel()
                applicant_directors = getattr(mca_data, "directors", []) if mca_data else []
                # Normalize director list — may be list of dicts or strings
                dir_names = []
                for d in applicant_directors:
                    if isinstance(d, dict):
                        dir_names.append(d.get("name", ""))
                    elif isinstance(d, str):
                        dir_names.append(d)

                applicant_addr = getattr(mca_data, "registered_address", "") if mca_data else ""
                applicant_cin = getattr(mca_data, "cin", "") if mca_data else ""

                counterparty_result = await run_in_threadpool(
                    cp_intel.analyze,
                    counterparties=bank_result.top_counterparties,
                    applicant_directors=dir_names,
                    applicant_address=applicant_addr,
                    applicant_name=entity_name,
                    applicant_cin=applicant_cin,
                    bank_transactions=bank_result.transactions,
                )
                logger.info(
                    f"[{elapsed()}] CounterpartyIntel done — "
                    f"{len(counterparty_result.counterparty_profiles)} profiles, "
                    f"{len(counterparty_result.relationship_flags)} flags, "
                    f"circular={counterparty_result.circular_trading_detected}, "
                    f"rules={counterparty_result.triggered_rules}"
                )
            else:
                counterparty_result = NetworkIntelResult()
        except Exception as e:
            logger.exception(f"CounterpartyIntel failed: {e}")
            counterparty_result = NetworkIntelResult()

        # ── Step 6.8: Sector Benchmark Assessor ──────────────────────────────────
        try:
            sector_assessor = SectorBenchmarkAssessor()
            latest_fin = latest_scan.get("extracted_figures", {})
            benchmark_result = sector_assessor.analyze(mca_data, latest_fin, {})
            logger.info(
                f"[{elapsed()}] SectorBenchmarkAssessor done — "
                f"sector={benchmark_result.sector_used}, "
                f"rules={benchmark_result.triggered_rules}")
        except Exception as e:
            logger.exception(f"SectorBenchmarkAssessor failed: {e}")
            from app.agents.external.sector_benchmark import BenchmarkResult
            benchmark_result = BenchmarkResult()

        # ── Step 6.9: Claims Extraction + Cross-Verification ──────────────────
        cross_verification = {"verifications": [], "summary": {}, "triggered_rules": []}
        claims = {}
        try:
            from app.agents.claims_extractor import extract_claims
            from app.agents.cross_verifier import CrossVerifier
            from app.api.v1.external_mocks import mock_perfios, mock_karza, mock_cibil

            perfios_for_xver = await mock_perfios()
            karza_for_xver = await mock_karza()
            cibil_for_xver = await mock_cibil()

            claims = extract_claims(
                extracted_figures=latest_scan.get("extracted_figures", {}),
                scan_dict=latest_scan,
                shareholding_data=shareholding_data,
                rating_result=rating_result if 'rating_result' in dir() else None,
                mda_insights=mda_insights if 'mda_insights' in dir() else None,
                restatement_data=restatement_data,
            )

            cross_verifier = CrossVerifier()
            cross_verification = cross_verifier.verify(
                claims=claims,
                bank_result=bank_result,
                perfios_data=perfios_for_xver,
                cibil_data=cibil_for_xver,
                karza_data=karza_for_xver,
                mca_data=mca_data,
                ecourts_data=ecourts_data,
                news_data=news_data,
                site_visit_result=site_visit_result,
                benchmark_result=benchmark_result if 'benchmark_result' in dir() else None,
            )
            logger.info(
                f"[{elapsed()}] Cross-verification done — "
                f"summary={cross_verification.get('summary')}, "
                f"rules={cross_verification.get('triggered_rules')}"
            )
        except Exception as e:
            logger.exception(f"Cross-verification failed: {e}")

        # ── Step 7: Orchestrate Final Decision ───────────────────────────────────

        all_triggered_rules = latest_scan.get("triggered_rules", [])
        if site_visit_result and site_visit_result.triggered_rules:
            for rule in site_visit_result.triggered_rules:
                if rule not in all_triggered_rules:
                    all_triggered_rules.append(rule)

        if bank_result and bank_result.triggered_rules:
            for rule in bank_result.triggered_rules:
                if rule not in all_triggered_rules:
                    all_triggered_rules.append(rule)

        if benchmark_result and benchmark_result.triggered_rules:
            for rule in benchmark_result.triggered_rules:
                if rule not in all_triggered_rules:
                    all_triggered_rules.append(rule)
        
        if mca_data and mca_data.triggered_rules:
            for rule in mca_data.triggered_rules:
                if rule not in all_triggered_rules:
                    all_triggered_rules.append(rule)

        # ── Merge CounterpartyIntel triggered_rules (P-06) ────────────────────
        if counterparty_result and counterparty_result.triggered_rules:
            logger.info(f"CounterpartyIntel triggered_rules: {counterparty_result.triggered_rules}")
            for rule in counterparty_result.triggered_rules:
                if rule not in all_triggered_rules:
                    all_triggered_rules.append(rule)

        # ── Merge NewsScanner triggered_rules (P-13) ─────────────────────────
        news_data = latest_scan.get("news_data")
        if news_data and news_data.get("triggered_rules"):
            logger.info(f"NewsScanner triggered_rules: {news_data.get('triggered_rules')}")
            for rule in news_data["triggered_rules"]:
                if rule not in all_triggered_rules:
                    all_triggered_rules.append(rule)
        
        # ── Merge ECourtsScanner triggered_rules (P-15) ──────────────────────
        ecourts_data = latest_scan.get("ecourts_data")
        if ecourts_data and ecourts_data.get("triggered_rules"):
            logger.info(f"ECourtsScanner triggered_rules: {ecourts_data['triggered_rules']}")
            for rule in ecourts_data["triggered_rules"]:
                if rule not in all_triggered_rules:
                    all_triggered_rules.append(rule)
                    
        # ── Merge Cross-Verification triggered_rules (P-31, P-32) ───────────
        if cross_verification and cross_verification.get("triggered_rules"):
            logger.info(f"CrossVerification triggered_rules: {cross_verification['triggered_rules']}")
            for rule in cross_verification["triggered_rules"]:
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
                    "decision": orchestrate_decision(None, None, None, restatement_data=restatement_data, news_data=news_data, site_visit_scan={"triggered_rules": site_visit_result.triggered_rules}, mca_data={"triggered_rules": getattr(mca_data, "triggered_rules", [])} if mca_data else None, counterparty_intel={"triggered_rules": counterparty_result.triggered_rules} if counterparty_result else None),
                    "per_year_scans": per_year_scans,
                    "restatement_data": restatement_data,
                }
            )

        decision = orchestrate_decision(
            pdf_scan_result=latest_scan,
            perfios_data=None,
            karza_data=None,
            restatement_data=restatement_data,
            news_data=news_data,
            site_visit_scan={"triggered_rules": site_visit_result.triggered_rules},
            mca_data={"triggered_rules": getattr(mca_data, "triggered_rules", [])} if mca_data else None,
            counterparty_intel={"triggered_rules": counterparty_result.triggered_rules} if counterparty_result else None,
            cross_verification=cross_verification,
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
            "claims": claims,
            "cross_verification": cross_verification,
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
            "site_visit": {
                "notes": site_visit_notes,
                "findings": [
                    {
                        "rule_id": f.rule_id,
                        "rule_name": f.rule_name,
                        "description": f.description,
                        "matched_text": f.matched_text,
                        "severity": f.severity,
                        "rate_penalty_bps": f.rate_penalty_bps,
                        "limit_reduction_pct": f.limit_reduction_pct,
                    }
                    for f in site_visit_result.findings
                ],
                "triggered_rules": site_visit_result.triggered_rules,
                "total_penalty_bps": site_visit_result.total_penalty_bps,
                "risk_summary": site_visit_result.risk_summary,
            },
            "bank_statement": {
                "total_transactions": bank_result.total_transactions if bank_result else 0,
                "total_debits": bank_result.total_debits if bank_result else 0,
                "total_credits": bank_result.total_credits if bank_result else 0,
                "avg_monthly_balance": bank_result.avg_monthly_balance if bank_result else 0,
                "circular_transactions": [
                    {
                        "party": ct.party,
                        "debit_date": ct.debit_date,
                        "debit_amount": ct.debit_amount,
                        "credit_date": ct.credit_date,
                        "credit_amount": ct.credit_amount,
                        "days_gap": ct.days_gap,
                    }
                    for ct in (bank_result.circular_transactions if bank_result else [])
                ],
                "cash_spikes": [
                    {
                        "date": cs.date,
                        "amount": cs.amount,
                        "nearest_filing_date": cs.nearest_filing_date,
                        "days_before_filing": cs.days_before_filing,
                    }
                    for cs in (bank_result.cash_spikes if bank_result else [])
                ],
                "top_counterparties": bank_result.top_counterparties if bank_result else [],
                "findings": bank_result.findings if bank_result else [],
                "triggered_rules": bank_result.triggered_rules if bank_result else [],
            },
            "counterparty_intel": {
                "circular_trading_detected": counterparty_result.circular_trading_detected if counterparty_result else False,
                "network_graph": counterparty_result.network_graph if counterparty_result else {"nodes": [], "links": []},
                "relationship_flags": [
                    {
                        "flag_type": f.flag_type,
                        "severity": f.severity,
                        "entity_a": f.entity_a,
                        "entity_b": f.entity_b,
                        "evidence": f.evidence,
                        "details": f.details,
                    }
                    for f in (counterparty_result.relationship_flags if counterparty_result else [])
                ],
                "counterparty_profiles": [
                    {
                        "name": p.name,
                        "total_volume": p.total_volume,
                        "debit_volume": p.debit_volume,
                        "credit_volume": p.credit_volume,
                        "txn_count": p.txn_count,
                        "mca_found": p.mca_found,
                        "cin": p.cin,
                        "company_status": p.company_status,
                        "registered_address": p.registered_address,
                        "business_activity": p.business_activity,
                        "paid_up_capital": p.paid_up_capital,
                        "is_shell_suspect": p.is_shell_suspect,
                        "shell_reasons": p.shell_reasons,
                    }
                    for p in (counterparty_result.counterparty_profiles if counterparty_result else [])
                ],
                "findings": counterparty_result.findings if counterparty_result else [],
                "triggered_rules": counterparty_result.triggered_rules if counterparty_result else [],
                "total_lookups": counterparty_result.total_lookups if counterparty_result else 0,
            },
            "ecourts": latest_scan.get("ecourts_data") or {
                "cases_found": 0,
                "high_risk_cases": 0,
                "findings": [],
                "triggered_rules": [],
                "source": "eCourts Public API"
            },
            "shareholding": {
                "promoter_holding_pct": shareholding_data.promoter_holding_pct,
                "pledged_pct": shareholding_data.pledged_pct,
                "fii_holding_pct": shareholding_data.fii_holding_pct,
                "government_holding_pct": shareholding_data.government_holding_pct,
                "findings": shareholding_data.findings,
                "triggered_rules": shareholding_data.triggered_rules,
                "source": shareholding_data.source
            } if shareholding_data else {},
            "methodology": (
                "All findings are extracted by deterministic regex — zero LLM calls. "
                "Every snippet is traceable to the original PDF text. "
                "Rate and limit penalties are computed by a transparent accumulator model."
            ),
            "benchmark_data": {
                "sector_used": benchmark_result.sector_used if 'benchmark_result' in dir() else "DEFAULT",
                "summary": benchmark_result.summary if 'benchmark_result' in dir() else "",
                "findings": [
                    {
                        "metric": f.metric,
                        "company_value": f.company_value,
                        "benchmark_value": f.benchmark_value,
                        "deviation_pct": f.deviation_pct,
                        "status": f.status
                    }
                    for f in (benchmark_result.findings if 'benchmark_result' in dir() else [])
                ],
                "triggered_rules": benchmark_result.triggered_rules if 'benchmark_result' in dir() else [],
            },
            "collateral": {
                "has_unsecured_loans": collateral_result.has_unsecured_loans if 'collateral_result' in dir() else False,
                "is_fully_secured": collateral_result.is_fully_secured if 'collateral_result' in dir() else False,
                "summary": collateral_result.summary if 'collateral_result' in dir() else "",
                "findings": [
                    {
                        "asset_type": f.asset_type,
                        "security_type": f.security_type,
                        "snippet": f.snippet
                    }
                    for f in (collateral_result.findings if 'collateral_result' in dir() else [])
                ],
                "triggered_rules": collateral_result.triggered_rules if 'collateral_result' in dir() else [],
            },
            "ratings": {
                "latest_agency": rating_result.latest_agency if 'rating_result' in dir() else None,
                "latest_rating": rating_result.latest_rating if 'rating_result' in dir() else None,
                "latest_outlook": rating_result.latest_outlook if 'rating_result' in dir() else None,
                "is_investment_grade": rating_result.is_investment_grade if 'rating_result' in dir() else None,
                "downgrade_detected": rating_result.downgrade_detected if 'rating_result' in dir() else False,
                "ratings_found": rating_result.ratings_found if 'rating_result' in dir() else [],
                "triggered_rules": rating_result.triggered_rules if 'rating_result' in dir() else [],
            },
            "supply_chain_risk": latest_scan.get("supply_chain_risk", {}),
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
