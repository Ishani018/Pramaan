"""
CAM Generator – Credit Appraisal Memo (Word Document)
======================================================
Generates a formatted python-docx Credit Appraisal Memo structured around
the Five Cs of Credit, populated entirely from the aggregated JSON decision data.
"""
import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict

logger = logging.getLogger(f"pramaan.{__name__}")

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import docx
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False
    logger.warning("python-docx not installed — CAM generation disabled")

PRAMAAN_BLUE  = (0x0F, 0x33, 0x6B)
DANGER_RED    = (0xDC, 0x26, 0x26)
SUCCESS_GREEN = (0x16, 0x7A, 0x3E)
WARN_AMBER    = (0xB4, 0x5A, 0x09)
GREY          = (0x64, 0x74, 0x8B)
BLACK         = (0x00, 0x00, 0x00)
WHITE         = (0xFF, 0xFF, 0xFF)

RULE_DISPLAY_NAMES = {
    "P-01": "GST-01: Revenue Mismatch",
    "P-02": "KYC-01: Director Network Risk", 
    "P-03": "AUDIT-01: Statutory Default",
    "P-04": "AUDIT-02: Emphasis of Matter",
    "P-06": "FRAUD-01: Circular Trading",
    "P-07": "PRIMARY-01: Site Visit Risk",
    "P-08": "BANK-01: Suspicious Routing",
    "P-09": "RESTATE-01: Silent Restatement",
    "P-10": "AUDIT-03: Auditor Rotation",
    "P-11": "RATING-01: Sub-Investment Grade",
    "P-12": "RATING-02: Downgrade/Default",
    "P-13": "MEDIA-01: Adverse Media",
    "P-15": "LEGAL-01: Active Court Proceedings",
    "P-16": "MGMT-01: Negative Management Sentiment"
}

def _rgb(doc_color: tuple):
    return RGBColor(*doc_color)

def _set_cell_bg(cell, hex_color: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)

def _add_section_header(doc, text: str):
    h = doc.add_heading(text, level=1)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in h.runs:
        run.font.color.rgb = _rgb(PRAMAAN_BLUE)
        run.font.size = Pt(16)
        run.font.name = "Arial"
        run.bold = True
    return h

def _add_sub_header(doc, text: str):
    h = doc.add_heading(text, level=2)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in h.runs:
        run.font.color.rgb = _rgb(DANGER_RED)
        run.font.size = Pt(12)
        run.font.name = "Arial"
        run.bold = True
    return h

def _add_body_para(doc, text: str, bold=False):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(text)
    r.font.color.rgb = _rgb(BLACK)
    r.font.size = Pt(11)
    r.font.name = "Arial"
    r.bold = bold
    return p

def _create_styled_table(doc, rows: int, cols: int):
    tbl = doc.add_table(rows=rows, cols=cols)
    tbl.style = "Table Grid"
    return tbl

def _kv_row(table, key: str, value: str, flag_color: tuple = None):
    row = table.add_row()
    row.cells[0].text = key
    row.cells[0].paragraphs[0].runs[0].bold = True
    row.cells[0].paragraphs[0].runs[0].font.name = "Arial"
    row.cells[0].paragraphs[0].runs[0].font.size = Pt(11)
    
    row.cells[1].text = str(value)
    row.cells[1].paragraphs[0].runs[0].font.name = "Arial"
    row.cells[1].paragraphs[0].runs[0].font.size = Pt(11)
    if flag_color:
        for run in row.cells[1].paragraphs[0].runs:
            run.font.color.rgb = _rgb(flag_color)

def generate_cam(data: Dict[str, Any]) -> bytes:
    if not _DOCX_AVAILABLE:
        raise RuntimeError("python-docx is not installed.")

    doc = Document()
    
    # Page setup
    for section in doc.sections:
        section.top_margin    = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)
        
        # Header Watermark
        header = section.header
        header_para = header.paragraphs[0]
        header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = header_para.add_run("PRAMAAN CONFIDENTIAL")
        hrun.font.color.rgb = _rgb(GREY)
        hrun.font.size = Pt(10)
        hrun.bold = True
        
        # Footer
        footer = section.footer
        footer_para = footer.paragraphs[0]
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        frun = footer_para.add_run("Page | Project Pramaan Auto-CAM")
        frun.font.size = Pt(9)
        frun.font.color.rgb = _rgb(GREY)

    # ── VARIABLES ─────────────────────────────────────────────────────────────
    entity_name = data.get("entity_name") or "Acme Steels Pvt Ltd"
    decision_d  = data.get("decision") or {}
    triggered   = data.get("triggered_rules") or []
    karza       = data.get("karza") or {}
    perfios     = data.get("perfios") or {}
    pdf_scan    = data.get("pdf_scan") or {}
    news_data   = data.get("news_data") or {}
    restate     = data.get("restatement_data") or {}
    site_visit  = data.get("site_visit_scan") or {}
    
    # Reconstruct extracted figures
    figs = pdf_scan.get("extracted_figures", {}) if pdf_scan else {}

    # ── TITLE ─────────────────────────────────────────────────────────────────
    title = doc.add_heading("CREDIT APPRAISAL MEMORANDUM", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.color.rgb = _rgb(PRAMAAN_BLUE)
        run.font.size = Pt(20)
        run.bold = True
    doc.add_paragraph()

    # ── SECTION 1: EXECUTIVE SUMMARY ──────────────────────────────────────────
    _add_section_header(doc, "SECTION 1: EXECUTIVE SUMMARY")
    
    mca_data_dict = data.get("mca_data", {}) or {}
    cin_display = mca_data_dict.get("cin", "") if mca_data_dict else ""
    
    _add_body_para(doc, f"Entity Name: {entity_name}")
    _add_body_para(doc, f"CIN: {cin_display or 'Not found in document'}")
    _add_body_para(doc, f"Assessment Date: {datetime.now().strftime('%d %B %Y')}")
    
    # Final Decision Paragraph
    rec = decision_d.get("recommendation", "PENDING").replace("_", " ")
    rec_color = DANGER_RED if "MANUAL" in rec else (SUCCESS_GREEN if rec == "APPROVE" else WARN_AMBER)
    p_dec = _add_body_para(doc, f"FINAL DECISION: {rec}", bold=True)
    p_dec.runs[0].font.color.rgb = _rgb(rec_color)
    p_dec.runs[0].font.size = Pt(14)
    
    _add_body_para(doc, f"Recommended Limit: ₹{decision_d.get('final_limit_cr', 0.0):.2f} Cr")
    _add_body_para(doc, f"Recommended Rate: {decision_d.get('final_rate_pct', 0.0):.2f}% p.a.")
    
    pen_count = len(triggered)
    _add_body_para(doc, f"Total Penalties Applied: {pen_count} rules triggered.")
    doc.add_paragraph()

    # ── SECTION 2: CHARACTER ──────────────────────────────────────────────────
    _add_section_header(doc, "SECTION 2: CHARACTER")
    _add_sub_header(doc, "Assessment of promoter integrity and governance quality")
    
    # MCA Data
    c2_tbl = _create_styled_table(doc, 0, 2)
    c2_tbl.columns[0].width = Inches(2.5)
    
    mca = data.get("mca_data", {}) or {}
    
    if mca.get("company_name") or mca.get("cin"):
        status = mca.get("company_status", "Pending")
        address = mca.get("registered_address", "")
        activity = mca.get("business_activity", "")
        paidup_raw = mca.get("paid_up_capital", 0)
        cin = mca.get("cin", "Not found")
        date_raw = mca.get("date_of_incorporation", "")
        
        try:
            dt = datetime.strptime(date_raw[:10], "%Y-%m-%d")
            date_display = dt.strftime("%d %B %Y")
        except:
            date_display = date_raw[:10]
        
        _kv_row(c2_tbl, "Company Status", status)
        _kv_row(c2_tbl, "Date of Incorporation", date_display)
        _kv_row(c2_tbl, "Registered State", mca.get("registered_state", ""))
        _kv_row(c2_tbl, "Registered Address", address)
        _kv_row(c2_tbl, "Principal Business Activity", activity)
        
        if paidup_raw:
            paidup_cr = paidup_raw / 10000000
            _kv_row(c2_tbl, "Paid-up Capital", f"₹{paidup_cr:,.2f} Cr")
        else:
            _kv_row(c2_tbl, "Paid-up Capital", "N/A")
            
        _kv_row(c2_tbl, "CIN", cin)
        
        holders = mca.get("charge_holders", [])
        _kv_row(c2_tbl, "Charge Holders", ", ".join(holders) if holders else "None registered")
        _kv_row(c2_tbl, "Data Source", mca.get("source", "data.gov.in MCA"))
    else:
        _kv_row(c2_tbl, "MCA Verification", "Pending MCA verification")
    
    # Litigation
    lits = karza.get("active_litigations", [])
    _kv_row(c2_tbl, "Litigation History", "; ".join(lits) if lits else "No severe litigations detected", WARN_AMBER if lits else SUCCESS_GREEN)
    
    # eCourts
    ecourts = data.get("ecourts", {})
    ec_cases = ecourts.get("cases_found", 0)
    ec_high = ecourts.get("high_risk_cases", 0)
    _kv_row(c2_tbl, "eCourts Cases Found", str(ec_cases))
    _kv_row(c2_tbl, "High-Risk Cases", f"{ec_high} [LEGAL-01]" if ec_high > 0 else "0", DANGER_RED if ec_high > 0 else SUCCESS_GREEN)
    _kv_row(c2_tbl, "Source", ecourts.get("source", "eCourts Public API [LIVE]"))
    ec_findings = ecourts.get("findings", [])
    if ec_findings:
        for f in ec_findings:
            _kv_row(c2_tbl, "Finding", f"{f.get('signal', '')} | {f.get('court', '')}", DANGER_RED)
    
    # NewsScanner
    adverse = news_data.get("adverse_media_detected", False)
    _kv_row(c2_tbl, "Adverse Media (NewsScanner)", "⚠ YES [MEDIA-01]" if adverse else "✓ Clear", DANGER_RED if adverse else SUCCESS_GREEN)
    
    # Auditor Continuity
    aud_change = restate.get("auditor_changed", False)
    _kv_row(c2_tbl, "Auditor Continuity", "⚠ Changed [AUDIT-03]" if aud_change else "✓ Continuous", WARN_AMBER if aud_change else SUCCESS_GREEN)
    doc.add_paragraph()

    # ── SECTION 3: CAPACITY ───────────────────────────────────────────────────
    _add_section_header(doc, "SECTION 3: CAPACITY")
    _add_sub_header(doc, "Assessment of repayment capacity from operations")
    c3_tbl = _create_styled_table(doc, 0, 2)
    c3_tbl.columns[0].width = Inches(2.5)
    
    # Financial extraction logic
    rev_obj = figs.get("Revenue", {})
    rev_val = rev_obj.get("value") if rev_obj else None
    rev_prev = rev_obj.get("previous_value") if rev_obj else None
    if rev_val is not None:
        if rev_val < 100 and rev_prev is not None:
            revenue_str = f"₹{rev_prev:.2f} Cr"
        else:
            revenue_str = f"₹{rev_val:.2f} Cr"
    else:
        revenue_str = "—"
        
    ebitda_obj = figs.get("EBITDA", {})
    ebitda_str = f"₹{ebitda_obj.get('value'):.2f} Cr" if ebitda_obj and ebitda_obj.get("value") is not None else "— (Not extracted)"
    
    pat_obj = figs.get("PAT", {})
    pat_str = f"₹{pat_obj.get('value'):.2f} Cr" if pat_obj and pat_obj.get("value") is not None else "— (Not extracted)"
    
    _kv_row(c3_tbl, "Total Revenue (Reported)", revenue_str)
    _kv_row(c3_tbl, "EBITDA", ebitda_str)
    _kv_row(c3_tbl, "PAT", pat_str)
    
    # perfios
    mismatch = perfios.get("gstr_2a_3b_mismatch_pct", 0)
    _kv_row(c3_tbl, "GST 2A/3B Reconciliation", f"{mismatch:.1f}% Mismatch {'[GST-01]' if mismatch > 15 else ''}", DANGER_RED if mismatch > 15 else SUCCESS_GREEN)
    
    disc_score = perfios.get("gst_filing_discipline_score")
    if disc_score is not None:
        _kv_row(c3_tbl, "GST Filing Discipline Score", f"{disc_score:.1f}/100", WARN_AMBER if disc_score < 90 else SUCCESS_GREEN)
    
    cap = site_visit.get("capacity_utilisation_pct")
    _kv_row(c3_tbl, "Site Visit Capacity", f"{cap}% — BELOW THRESHOLD [PRIMARY-01]" if cap and cap < 60 else f"{cap}%" if cap else "No quantitative data", DANGER_RED if cap and cap < 60 else None)
    
    if "P-07" in triggered:
        _kv_row(c3_tbl, "Flagged Risks", "⚠ adverse observations [PRIMARY-01]", DANGER_RED)
    doc.add_paragraph()

    # ── SECTION 4: CAPITAL ────────────────────────────────────────────────────
    _add_section_header(doc, "SECTION 4: CAPITAL")
    _add_sub_header(doc, "Assessment of net worth and financial leverage")
    c4_tbl = _create_styled_table(doc, 0, 2)
    c4_tbl.columns[0].width = Inches(2.5)
    
    nw_obj = figs.get("Net Worth", {})
    nw_val = nw_obj.get("value") if nw_obj else None
    td_obj = figs.get("Total Debt", {})
    td_val = td_obj.get("value") if td_obj else None
    
    nw_str = f"₹{nw_val:.2f} Cr" if nw_val is not None else data.get("net_worth", "— Pending Extraction")
    td_str = f"₹{td_val:.2f} Cr" if td_val is not None else f"₹{karza.get('charge_amount_cr', 0):.2f} Cr (MCA Charges)" if karza.get("mca_charge_registered") else "None registered"
    
    if nw_val is not None and td_val is not None and nw_val != 0:
        de_ratio = td_val / nw_val
        de_str = f"{de_ratio:.2f}x"
    else:
        de_str = data.get("debt_equity", "—")
    
    _kv_row(c4_tbl, "Net Worth", nw_str)
    _kv_row(c4_tbl, "Total Debt", td_str)
    _kv_row(c4_tbl, "Debt / Equity Ratio", de_str)
    
    restate_det = restate.get("restatements_detected", False)
    _kv_row(c4_tbl, "Financial Restatements", "⚠ Detected [RESTATE-01]" if restate_det else "✓ None", DANGER_RED if restate_det else SUCCESS_GREEN)
    doc.add_paragraph()

    # ── SECTION 5: COLLATERAL ─────────────────────────────────────────────────
    _add_section_header(doc, "SECTION 5: COLLATERAL")
    _add_sub_header(doc, "Assessment of security coverage")
    c5_tbl = _create_styled_table(doc, 0, 2)
    c5_tbl.columns[0].width = Inches(2.5)
    
    holders = karza.get("charge_holders", [])
    _kv_row(c5_tbl, "Registered Charges (MCA)", ", ".join(holders) if holders else "None")
    
    col_data = pdf_scan.get("collateral", {})
    if col_data:
        has_unsec = col_data.get("has_unsecured_loans", False)
        _kv_row(c5_tbl, "Unsecured Borrowings", "⚠ Detected [P-31]" if has_unsec else "✓ None", DANGER_RED if has_unsec else SUCCESS_GREEN)
        
        findings = col_data.get("findings", [])
        if findings:
            for i, f in enumerate(findings):
                _kv_row(c5_tbl, f"Collateral Finding {i+1}", f"{f.get('security_type')} on {f.get('asset_type')}")
    else:
        _kv_row(c5_tbl, "Security Coverage Ratio", data.get("security_coverage", "— Pending Legal Eval"))
    
    _add_body_para(doc, "Note: Primary security to be verified by legal team.", bold=True).runs[0].font.color.rgb = _rgb(GREY)
    doc.add_paragraph()

    # ── SECTION 6: CONDITIONS ─────────────────────────────────────────────────
    _add_section_header(doc, "SECTION 6: CONDITIONS")
    _add_sub_header(doc, "Macro and sector conditions affecting creditworthiness")
    c6_tbl = _create_styled_table(doc, 0, 2)
    c6_tbl.columns[0].width = Inches(2.5)
    
    rf = news_data.get("red_flags", [])
    has_reg = any("RBI" in r.get("headline", "") for r in rf)
    _kv_row(c6_tbl, "Sector Context", "News headlines processed" if news_data else "Unknown")
    _kv_row(c6_tbl, "Regulatory Flags (News)", "⚠ RBI/SEBI alerts found" if has_reg else "✓ Clear")
    
    caro = pdf_scan.get("caro_default_found", False)
    eom = pdf_scan.get("emphasis_of_matter_found", False)
    _kv_row(c6_tbl, "CARO Findings", "⚠ Default True [AUDIT-01]" if caro else "✓ Clear", DANGER_RED if caro else SUCCESS_GREEN)
    _kv_row(c6_tbl, "Emphasis of Matter", "⚠ Flaged [AUDIT-02]" if eom else "✓ Clear", WARN_AMBER if eom else SUCCESS_GREEN)
    doc.add_paragraph()

    mda = data.get("mda_insights", {})
    if mda.get("status") == "success":
        _add_sub_header(doc, "MD&A SENTIMENT ANALYSIS (Loughran-McDonald Financial NLP)")
        mda_tbl = _create_styled_table(doc, 0, 2)
        mda_tbl.columns[0].width = Inches(2.5)
        
        score = mda.get("sentiment_score", 0)
        risk = mda.get("risk_intensity", 0)
        metrics = mda.get("metrics", {})
        
        _kv_row(mda_tbl, "Sentiment Score", f"{score} (positive = confident, negative = distressed)")
        _kv_row(mda_tbl, "Risk Intensity", f"{risk}")
        _kv_row(mda_tbl, "Negative Words", str(metrics.get("negative_words", 0)))
        _kv_row(mda_tbl, "Positive Words", str(metrics.get("positive_words", 0)))
        _kv_row(mda_tbl, "Uncertainty Words", str(metrics.get("uncertainty_words", 0)))
        _kv_row(mda_tbl, "Methodology", mda.get("methodology", "Loughran-McDonald Dictionary"))
        doc.add_paragraph()
        
        hw = mda.get("extracted_headwinds", [])
        if hw:
            _add_body_para(doc, "KEY RISK SENTENCES FROM MD&A:", bold=True).runs[0].font.color.rgb = _rgb(WARN_AMBER)
            for h in hw:
                doc.add_paragraph(h, style="List Bullet")
            doc.add_paragraph()

    # ── SECTION 7: RISK RULE MATRIX ───────────────────────────────────────────
    _add_section_header(doc, "SECTION 7: RISK RULE MATRIX")
    penalties = decision_d.get("applied_penalties", [])
    if penalties:
        p_tbl = _create_styled_table(doc, rows=1, cols=4)
        # Header row
        hdr = p_tbl.rows[0]
        for i, h in enumerate(["Rule Name", "Penalty (bps)", "Limit Impact", "Severity"]):
            hdr.cells[i].text = h
            hdr.cells[i].paragraphs[0].runs[0].bold = True
            hdr.cells[i].paragraphs[0].runs[0].font.color.rgb = _rgb(WHITE)
            _set_cell_bg(hdr.cells[i], "0F336B")  # Dark navy blue bg
            
        for p in penalties:
            row = p_tbl.add_row()
            raw_rule = p.get("rule_id", "")
            mapped = RULE_DISPLAY_NAMES.get(raw_rule, raw_rule)
            
            row.cells[0].text = f"{mapped}\n({p.get('trigger', '')})"
            row.cells[1].text = f"+{p.get('rate_penalty_bps', 0)} bps"
            row.cells[2].text = f"-{p.get('limit_reduction_pct', 0)}%"
            # Grab severity mapped or fallback
            sev = "HIGH" if p.get('limit_reduction_pct', 0) > 10 else "MEDIUM"
            if raw_rule == "P-09": sev = "CRITICAL"
            row.cells[3].text = sev
            row.cells[3].paragraphs[0].runs[0].bold = True
            if sev == "CRITICAL" or sev == "HIGH":
                row.cells[3].paragraphs[0].runs[0].font.color.rgb = _rgb(DANGER_RED)
    else:
        _add_body_para(doc, "No risk rules triggered.", bold=True).runs[0].font.color.rgb = _rgb(SUCCESS_GREEN)
    doc.add_paragraph()

    # ── SECTION 8: DECISION & CONDITIONS ──────────────────────────────────────
    _add_section_header(doc, "SECTION 8: DECISION & CONDITIONS")
    
    rate_steps = [f"Base Rate: {decision_d.get('base_rate_pct', 0.0):.2f}%"]
    lim_steps  = [f"Base Limit: ₹{decision_d.get('base_limit_cr', 0.0):.2f} Cr"]
    
    for p in penalties:
        bps = p.get("rate_penalty_bps", 0)
        lim = p.get("limit_reduction_pct", 0)
        mapped = RULE_DISPLAY_NAMES.get(p.get('rule_id'), p.get('rule_id'))
        if bps > 0: rate_steps.append(f"+ {bps} bps ({mapped})")
        if lim > 0: lim_steps.append(f"- {lim}% ({mapped})")
        
    rate_steps.append(f"FINAL RATE: {decision_d.get('final_rate_pct', 0.0):.2f}%")
    lim_steps.append(f"FINAL LIMIT: ₹{decision_d.get('final_limit_cr', 0.0):.2f} Cr")
    
    _add_body_para(doc, "Rate Calculation:")
    for s in rate_steps:
        doc.add_paragraph(s, style="List Bullet")
        
    _add_body_para(doc, "Limit Calculation:")
    for s in lim_steps:
        doc.add_paragraph(s, style="List Bullet")
        
    doc.add_paragraph()
    _add_body_para(doc, "Conditions precedent (items to verify before disbursement):", bold=True)
    
    conds = []
    if "P-03" in triggered: conds.append("Obtain auditor clarification on CARO Clause (vii) default")
    if "P-13" in triggered: conds.append("Obtain management response to adverse media findings")
    if "P-07" in triggered: conds.append("Re-verify plant capacity with independent chartered engineer")
    conds.append("Obtain board resolution, latest bank statements, ITR for 3 years")
    
    for c in conds:
        doc.add_paragraph(c, style="List Bullet")
    doc.add_paragraph()

    # ── SECTION 9: DISCLAIMER ─────────────────────────────────────────────────
    _add_section_header(doc, "SECTION 9: DISCLAIMER")
    disc = (
        "This memo was generated by Project Pramaan Intelli-Credit Engine v1.0. "
        "All findings are extracted by deterministic regex from source documents. "
        "No AI inference or hallucination. Every finding is traceable to the "
        "original document and page number."
    )
    pdisc = _add_body_para(doc, disc)
    pdisc.runs[0].italic = True
    pdisc.runs[0].font.size = Pt(9)
    pdisc.runs[0].font.color.rgb = _rgb(GREY)

    # ── SERIALIZE ─────────────────────────────────────────────────────────────
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    logger.info(f"CAM generated successfully ({buffer.getbuffer().nbytes:,} bytes)")
    return buffer.read()
