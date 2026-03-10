"""
CAM Generator – Credit Appraisal Memo (Word Document)
======================================================
Generates a formatted python-docx Credit Appraisal Memo structured around
the Five Cs of Credit, populated entirely from the aggregated JSON decision data.
"""
import logging
import os
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
LIGHT_GREY_BG = "F1F5F9"
BLUE_BG       = "0F336B"
RED_BG        = "FEF2F2"
GREEN_BG      = "F0FDF4"
AMBER_BG      = "FFFBEB"

LOGO_PATH = os.path.join(os.path.dirname(__file__), "pramaan_logo.png")

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
    "P-16": "MGMT-01: Negative Management Sentiment",
    "P-28": "BANK-02: Circular Transactions",
    "P-29": "BANK-03: Cash Spike near GST Filing",
    "P-33": "RECON-01: GST-Bank Turnover Mismatch",
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

def _add_sub_header(doc, text: str, color=DANGER_RED):
    h = doc.add_heading(text, level=2)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in h.runs:
        run.font.color.rgb = _rgb(color)
        run.font.size = Pt(12)
        run.font.name = "Arial"
        run.bold = True
    return h

def _add_body_para(doc, text: str, bold=False, color=BLACK):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(text)
    r.font.color.rgb = _rgb(color)
    r.font.size = Pt(11)
    r.font.name = "Arial"
    r.bold = bold
    return p

def _add_bullet(doc, text: str, bold=False, color=BLACK):
    p = doc.add_paragraph(style="List Bullet")
    p.clear()
    r = p.add_run(text)
    r.font.size = Pt(10)
    r.font.name = "Arial"
    r.font.color.rgb = _rgb(color)
    r.bold = bold
    return p

def _create_styled_table(doc, rows: int, cols: int):
    tbl = doc.add_table(rows=rows, cols=cols)
    tbl.style = "Table Grid"
    return tbl

def _kv_row(table, key: str, value: str, flag_color: tuple = None):
    row = table.add_row()
    row.cells[0].text = key
    for run in row.cells[0].paragraphs[0].runs:
        run.bold = True
        run.font.name = "Arial"
        run.font.size = Pt(10)

    row.cells[1].text = str(value)
    for run in row.cells[1].paragraphs[0].runs:
        run.font.name = "Arial"
        run.font.size = Pt(10)
        if flag_color:
            run.font.color.rgb = _rgb(flag_color)

def _add_table_header_row(table, headers):
    hdr = table.rows[0]
    for i, h in enumerate(headers):
        hdr.cells[i].text = h
        for run in hdr.cells[i].paragraphs[0].runs:
            run.bold = True
            run.font.color.rgb = _rgb(WHITE)
            run.font.name = "Arial"
            run.font.size = Pt(10)
        _set_cell_bg(hdr.cells[i], BLUE_BG)


# ══════════════════════════════════════════════════════════════════════════
# MAIN GENERATOR
# ══════════════════════════════════════════════════════════════════════════
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

        # Header with logo
        header = section.header
        header_para = header.paragraphs[0]
        header_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        if os.path.exists(LOGO_PATH):
            hrun = header_para.add_run()
            hrun.add_picture(LOGO_PATH, width=Inches(1.0))
        # Add confidential watermark on the right
        tab_run = header_para.add_run("\t\t\t\t   PRAMAAN CONFIDENTIAL")
        tab_run.font.color.rgb = _rgb(GREY)
        tab_run.font.size = Pt(9)
        tab_run.bold = True

        # Footer
        footer = section.footer
        footer_para = footer.paragraphs[0]
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        frun = footer_para.add_run("Project Pramaan | Intelli-Credit Engine v1.0 | Auto-Generated CAM")
        frun.font.size = Pt(8)
        frun.font.color.rgb = _rgb(GREY)

    # ── VARIABLES ─────────────────────────────────────────────────────────────
    entity_name      = data.get("entity_name") or "Unnamed Entity"
    decision_d       = data.get("decision") or {}
    triggered        = data.get("triggered_rules") or []
    karza            = data.get("karza") or {}
    perfios          = data.get("perfios") or {}
    pdf_scan         = data.get("pdf_scan") or {}
    news_data        = data.get("news_data") or {}
    restate          = data.get("restatement_data") or {}
    site_visit       = data.get("site_visit_scan") or {}
    supply_chain     = (pdf_scan.get("supply_chain_risk") if pdf_scan else {}) or {}
    cross_ver        = data.get("cross_verification") or (pdf_scan.get("cross_verification") or {})
    bank_stmt        = data.get("bank_statement") or (pdf_scan.get("bank_statement") or {})
    cp_intel         = data.get("counterparty_intel") or (pdf_scan.get("counterparty_intel") or {})
    benchmark        = data.get("benchmark_data") or (pdf_scan.get("benchmark_data") or {})
    network_data     = data.get("network_data") or {}
    mda              = pdf_scan.get("mda_insights", {}) if pdf_scan else {}
    figs             = pdf_scan.get("extracted_figures", {}) if pdf_scan else {}

    # ══════════════════════════════════════════════════════════════════════════
    # TITLE PAGE
    # ══════════════════════════════════════════════════════════════════════════
    doc.add_paragraph()
    title = doc.add_heading("CREDIT APPRAISAL MEMORANDUM", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.color.rgb = _rgb(PRAMAAN_BLUE)
        run.font.size = Pt(22)
        run.bold = True

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub.add_run(entity_name.upper())
    sr.font.color.rgb = _rgb(BLACK)
    sr.font.size = Pt(14)
    sr.font.name = "Arial"
    sr.bold = True

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    dr = date_p.add_run(f"Assessment Date: {datetime.now().strftime('%d %B %Y')}")
    dr.font.color.rgb = _rgb(GREY)
    dr.font.size = Pt(11)
    dr.font.name = "Arial"
    doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1: EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "1. EXECUTIVE SUMMARY")

    mca = data.get("mca_data", {}) or {}
    cin_display = mca.get("cin", "Not found in document")

    exec_tbl = _create_styled_table(doc, 0, 2)
    exec_tbl.columns[0].width = Inches(2.5)
    _kv_row(exec_tbl, "Entity Name", entity_name)
    _kv_row(exec_tbl, "CIN", cin_display)
    _kv_row(exec_tbl, "Assessment Date", datetime.now().strftime('%d %B %Y'))

    rec = decision_d.get("recommendation", "PENDING").replace("_", " ")
    rec_color = DANGER_RED if "MANUAL" in rec else (SUCCESS_GREEN if rec == "APPROVE" else WARN_AMBER)
    _kv_row(exec_tbl, "FINAL DECISION", rec, rec_color)
    _kv_row(exec_tbl, "Recommended Limit", f"\u20b9{decision_d.get('final_limit_cr', 0.0):.2f} Cr")
    _kv_row(exec_tbl, "Recommended Rate", f"{decision_d.get('final_rate_pct', 0.0):.2f}% p.a.")
    _kv_row(exec_tbl, "Rules Triggered", f"{len(triggered)} penalty rules applied")
    doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2: GST-BANK RECONCILIATION
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "2. GST-BANK RECONCILIATION")
    _add_sub_header(doc, "Reconciliation of declared GST turnover with bank statement credits", PRAMAAN_BLUE)

    # Try to get GST recon from cross-verification data
    gst_tbl = _create_styled_table(doc, 0, 2)
    gst_tbl.columns[0].width = Inches(2.5)

    gst_turnover = perfios.get("gst_turnover_cr", 0) if perfios else 0
    bank_credits = bank_stmt.get("total_credits", 0) if bank_stmt else 0
    bank_credits_cr = bank_credits / 1_00_00_000 if bank_credits > 100 else bank_credits

    if gst_turnover > 0 and bank_credits_cr > 0:
        variance = ((bank_credits_cr - gst_turnover) / gst_turnover) * 100
        abs_var = abs(variance)

        if abs_var > 20:
            status_text = "MISMATCH — HIGH VARIANCE"
            status_color = DANGER_RED
        elif abs_var > 10:
            status_text = "PARTIAL MATCH — MODERATE VARIANCE"
            status_color = WARN_AMBER
        else:
            status_text = "MATCH — RECONCILED"
            status_color = SUCCESS_GREEN

        _kv_row(gst_tbl, "GST Turnover (Perfios)", f"\u20b9{gst_turnover:.2f} Cr")
        _kv_row(gst_tbl, "Bank Statement Credits", f"\u20b9{bank_credits_cr:.2f} Cr")
        _kv_row(gst_tbl, "Variance", f"{variance:+.1f}%", status_color)
        _kv_row(gst_tbl, "Reconciliation Status", status_text, status_color)

        mismatch_pct = perfios.get("gstr_2a_3b_mismatch_pct", 0) if perfios else 0
        _kv_row(gst_tbl, "GSTR 2A vs 3B Mismatch", f"{mismatch_pct:.1f}%", DANGER_RED if mismatch_pct > 15 else SUCCESS_GREEN)

        disc_score = perfios.get("gst_filing_discipline_score") if perfios else None
        if disc_score is not None:
            _kv_row(gst_tbl, "Filing Discipline Score", f"{disc_score:.1f}/100", WARN_AMBER if disc_score < 90 else SUCCESS_GREEN)

        # Narrative
        if abs_var > 20:
            _add_body_para(doc, f"FINDING: A {abs_var:.0f}% variance between GST-reported turnover and bank credits indicates potential revenue overstatement or off-books transactions. Credit exposure should be conservatively assessed.", bold=True, color=DANGER_RED)
            if "P-33" in triggered:
                _add_body_para(doc, "Rule P-33 (RECON-01) triggered: +125 bps rate penalty, -20% limit reduction.", color=DANGER_RED)
        elif abs_var > 10:
            _add_body_para(doc, f"OBSERVATION: A {abs_var:.0f}% variance exists between GST turnover and bank credits. While within tolerance for working capital timing differences, this warrants monitoring.", color=WARN_AMBER)
        else:
            _add_body_para(doc, f"GST turnover and bank credits are reconciled within {abs_var:.0f}% tolerance. Standard credit assessment recommended.", color=SUCCESS_GREEN)
    elif gst_turnover > 0:
        _kv_row(gst_tbl, "GST Turnover (Perfios)", f"\u20b9{gst_turnover:.2f} Cr")
        _kv_row(gst_tbl, "Bank Statement Credits", "Not available — bank CSV not uploaded")
        _kv_row(gst_tbl, "Reconciliation Status", "UNVERIFIABLE", GREY)
    else:
        _kv_row(gst_tbl, "Status", "GST data not available for reconciliation", GREY)
    doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3: COUNTERPARTY INTELLIGENCE & CIRCULAR TRADING
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "3. COUNTERPARTY INTELLIGENCE & CIRCULAR TRADING")

    profiles = cp_intel.get("counterparty_profiles", [])
    flags = cp_intel.get("relationship_flags", [])
    circular_detected = cp_intel.get("circular_trading_detected", False)
    circular_txns = bank_stmt.get("circular_transactions", [])

    # Network data from counterparty intel module
    net_profiles = network_data.get("profiles", []) if network_data else []
    net_flags = network_data.get("flags", []) if network_data else []

    # Use whichever has data
    all_profiles = net_profiles or profiles
    all_flags = net_flags or flags

    ci_tbl = _create_styled_table(doc, 0, 2)
    ci_tbl.columns[0].width = Inches(2.5)
    _kv_row(ci_tbl, "Counterparties Analyzed", str(len(all_profiles)))

    shell_count = sum(1 for p in all_profiles if p.get("is_shell_suspect"))
    _kv_row(ci_tbl, "Shell Company Suspects", str(shell_count), DANGER_RED if shell_count > 0 else SUCCESS_GREEN)

    circular_flags = [f for f in all_flags if f.get("flag_type") == "circular_loop"]
    _kv_row(ci_tbl, "Circular Trading Detected", "YES" if (circular_detected or len(circular_flags) > 0) else "NO", DANGER_RED if (circular_detected or len(circular_flags) > 0) else SUCCESS_GREEN)
    _kv_row(ci_tbl, "Round-trip Flow Chains", str(len(circular_flags)))
    _kv_row(ci_tbl, "Total Risk Flags", str(len(all_flags)))
    doc.add_paragraph()

    # Circular Trading Detail
    if circular_flags:
        _add_sub_header(doc, "CIRCULAR TRADING FLOWS DETECTED [P-06: FRAUD-01]")
        _add_body_para(doc, "The following round-trip money flows were detected between the applicant and counterparties, indicating potential circular trading or fund layering:", bold=True, color=DANGER_RED)

        for cf in circular_flags:
            entity_a = cf.get("entity_a", "Unknown")
            entity_b = cf.get("entity_b", "Unknown")
            evidence = cf.get("evidence", "")
            _add_bullet(doc, f"{entity_a} \u2194 {entity_b}: {evidence}", color=DANGER_RED)

        if "P-06" in triggered:
            _add_body_para(doc, "Rule P-06 (FRAUD-01) triggered: +200 bps rate penalty, -30% limit reduction.", color=DANGER_RED)
        doc.add_paragraph()

    # Bank Statement Circular Transactions (P-28)
    if circular_txns:
        _add_sub_header(doc, "BANK STATEMENT CIRCULAR TRANSACTIONS [P-28]")
        _add_body_para(doc, f"{len(circular_txns)} round-trip flows detected within 7-day windows in the bank statement:")

        ct_tbl = _create_styled_table(doc, rows=1, cols=5)
        _add_table_header_row(ct_tbl, ["Counterparty", "Debit Amount", "Credit Amount", "Gap (Days)", "Dates"])

        for ct in circular_txns[:10]:
            row = ct_tbl.add_row()
            row.cells[0].text = ct.get("party", "Unknown")
            row.cells[1].text = f"\u20b9{ct.get('debit_amount', 0):,.0f}"
            row.cells[2].text = f"\u20b9{ct.get('credit_amount', 0):,.0f}"
            row.cells[3].text = str(ct.get("days_gap", ""))
            row.cells[4].text = f"{ct.get('debit_date', '')} / {ct.get('credit_date', '')}"
        doc.add_paragraph()

    # Shell Company Suspects
    shells = [p for p in all_profiles if p.get("is_shell_suspect")]
    if shells:
        _add_sub_header(doc, "SHELL COMPANY SUSPECTS")
        for s in shells:
            reasons = s.get("shell_reasons", [])
            reason_text = "; ".join(reasons) if reasons else "Flagged by heuristics"
            _add_bullet(doc, f"{s.get('name', 'Unknown')} — {reason_text}", color=DANGER_RED)
        doc.add_paragraph()

    # Counterparty Summary Table
    if all_profiles:
        _add_sub_header(doc, "TOP COUNTERPARTIES BY TRANSACTION VOLUME", PRAMAAN_BLUE)
        cp_tbl = _create_styled_table(doc, rows=1, cols=5)
        _add_table_header_row(cp_tbl, ["Counterparty", "Volume", "MCA Verified", "Shell?", "Status"])

        for p in all_profiles[:10]:
            row = cp_tbl.add_row()
            row.cells[0].text = p.get("name", "Unknown")
            vol = p.get("total_volume", 0)
            row.cells[1].text = f"\u20b9{vol:,.0f}" if vol else "N/A"
            row.cells[2].text = "Yes" if p.get("mca_found") else "No"
            is_shell = p.get("is_shell_suspect", False)
            row.cells[3].text = "YES" if is_shell else "No"
            if is_shell:
                for run in row.cells[3].paragraphs[0].runs:
                    run.font.color.rgb = _rgb(DANGER_RED)
                    run.bold = True
            row.cells[4].text = p.get("company_status", "Unknown")
        doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4: SUPPLY CHAIN & COMPETITOR ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "4. SUPPLY CHAIN & COMPETITOR ANALYSIS")

    if supply_chain:
        _add_sub_header(doc, "SUPPLY CHAIN RISK ASSESSMENT", PRAMAAN_BLUE)
        sc_tbl = _create_styled_table(doc, 0, 2)
        sc_tbl.columns[0].width = Inches(2.5)

        overall_band = supply_chain.get('overall_supply_chain_risk_band', 'Unknown')
        overall_score = supply_chain.get('overall_supply_chain_risk_score', 0)
        sc_color = DANGER_RED if overall_band == "High" else WARN_AMBER if overall_band == "Moderate" else SUCCESS_GREEN

        _kv_row(sc_tbl, "Overall Supply Chain Risk", f"{overall_band} (Score: {overall_score})", sc_color)
        _kv_row(sc_tbl, "Upstream Supplier Risk", f"{supply_chain.get('supplier_risk_band', 'Unknown')} ({supply_chain.get('supplier_risk_score', 0)})")
        _kv_row(sc_tbl, "Downstream Buyer Risk", f"{supply_chain.get('buyer_risk_band', 'Unknown')} ({supply_chain.get('buyer_risk_score', 0)})")
        _kv_row(sc_tbl, "Weakest Link", supply_chain.get("weakest_link", "Not determined"))
        _kv_row(sc_tbl, "Major Supplier", supply_chain.get("major_supplier", "Not explicitly identified"))
        _kv_row(sc_tbl, "Major Buyer", supply_chain.get("major_buyer", "Not explicitly identified"))
        doc.add_paragraph()

        reasons = supply_chain.get("reasons", [])
        if reasons:
            _add_body_para(doc, "Key Supply Chain Risk Factors:", bold=True)
            for reason in reasons[:5]:
                _add_bullet(doc, reason)

        cam_text = supply_chain.get("cam_paragraph")
        if cam_text:
            doc.add_paragraph()
            _add_body_para(doc, cam_text)
        doc.add_paragraph()
    else:
        _add_body_para(doc, "Supply chain data not extracted from the annual report.", color=GREY)
        doc.add_paragraph()

    # Competitor / Sector Benchmark Analysis
    if benchmark:
        _add_sub_header(doc, "COMPETITOR & SECTOR BENCHMARK ANALYSIS", PRAMAAN_BLUE)
        _add_body_para(doc, f"Sector Used: {benchmark.get('sector_used', 'Unknown')}", bold=True)

        summary_text = benchmark.get("summary", "")
        if summary_text:
            _add_body_para(doc, summary_text)

        findings = benchmark.get("findings", [])
        if findings:
            bm_tbl = _create_styled_table(doc, rows=1, cols=5)
            _add_table_header_row(bm_tbl, ["Metric", "Company", "Benchmark", "Deviation", "Status"])

            for f in findings:
                row = bm_tbl.add_row()
                row.cells[0].text = f.get("metric", "")

                cv = f.get("company_value")
                row.cells[1].text = f"{cv:.1f}%" if cv is not None else "N/A"

                bv = f.get("benchmark_value")
                row.cells[2].text = f"{bv:.1f}%" if bv is not None else "N/A"

                dev = f.get("deviation_pct")
                row.cells[3].text = f"{dev:+.1f}%" if dev is not None else "N/A"

                status = f.get("status", "OK")
                row.cells[4].text = status
                if status == "CRITICAL":
                    for run in row.cells[4].paragraphs[0].runs:
                        run.font.color.rgb = _rgb(DANGER_RED)
                        run.bold = True
                elif status == "BELOW":
                    for run in row.cells[4].paragraphs[0].runs:
                        run.font.color.rgb = _rgb(WARN_AMBER)
            doc.add_paragraph()

            # Narrative about competitive positioning
            critical_metrics = [f for f in findings if f.get("status") == "CRITICAL"]
            below_metrics = [f for f in findings if f.get("status") == "BELOW"]

            if critical_metrics:
                _add_body_para(doc, "COMPETITIVE RISK: The borrower significantly underperforms sector benchmarks on the following metrics:", bold=True, color=DANGER_RED)
                for cm in critical_metrics:
                    _add_bullet(doc, f"{cm['metric']}: Company at {cm.get('company_value', 0):.1f}% vs sector benchmark {cm.get('benchmark_value', 0):.1f}% (deviation: {cm.get('deviation_pct', 0):+.1f}%)", color=DANGER_RED)
                _add_body_para(doc, "Competitors with stronger fundamentals in these areas have structural cost and risk advantages, potentially impacting the borrower's market position and repayment capacity.")
            elif below_metrics:
                _add_body_para(doc, "The borrower shows moderate underperformance on some sector benchmarks. While not critical, this indicates limited competitive headroom.", color=WARN_AMBER)
            else:
                _add_body_para(doc, "The borrower is broadly aligned with sector benchmarks, indicating competitive parity.", color=SUCCESS_GREEN)
        doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5: CHARACTER
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "5. CHARACTER")
    _add_sub_header(doc, "Promoter integrity, governance quality, and legal standing", PRAMAAN_BLUE)

    c2_tbl = _create_styled_table(doc, 0, 2)
    c2_tbl.columns[0].width = Inches(2.5)

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
        except Exception:
            date_display = date_raw[:10] if date_raw else "N/A"

        _kv_row(c2_tbl, "Company Status", status)
        _kv_row(c2_tbl, "Date of Incorporation", date_display)
        _kv_row(c2_tbl, "Registered State", mca.get("registered_state", ""))
        _kv_row(c2_tbl, "Registered Address", address)
        _kv_row(c2_tbl, "Principal Business Activity", activity)

        if paidup_raw:
            paidup_cr = paidup_raw / 10000000
            _kv_row(c2_tbl, "Paid-up Capital", f"\u20b9{paidup_cr:,.2f} Cr")
        else:
            _kv_row(c2_tbl, "Paid-up Capital", "N/A")

        _kv_row(c2_tbl, "CIN", cin)
        _kv_row(c2_tbl, "Data Source", mca.get("source", "data.gov.in MCA"))
    else:
        _kv_row(c2_tbl, "MCA Verification", "Pending MCA verification")

    # Litigation
    lits = karza.get("active_litigations", [])
    _kv_row(c2_tbl, "Litigation History", "; ".join(lits) if lits else "No severe litigations detected", WARN_AMBER if lits else SUCCESS_GREEN)

    # eCourts
    ecourts = data.get("ecourts") or (pdf_scan.get("ecourts") if pdf_scan else {}) or {}
    ec_cases = ecourts.get("cases_found", 0)
    ec_high = ecourts.get("high_risk_cases", 0)
    _kv_row(c2_tbl, "eCourts Cases Found", str(ec_cases))
    _kv_row(c2_tbl, "High-Risk Cases", f"{ec_high} [LEGAL-01]" if ec_high > 0 else "0", DANGER_RED if ec_high > 0 else SUCCESS_GREEN)

    # NewsScanner
    adverse = news_data.get("adverse_media_detected", False)
    _kv_row(c2_tbl, "Adverse Media (NewsScanner)", "YES [MEDIA-01]" if adverse else "Clear", DANGER_RED if adverse else SUCCESS_GREEN)

    # Auditor Continuity
    aud_change = restate.get("auditor_changed", False)
    _kv_row(c2_tbl, "Auditor Continuity", "Changed [AUDIT-03]" if aud_change else "Continuous", WARN_AMBER if aud_change else SUCCESS_GREEN)
    doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6: CAPACITY
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "6. CAPACITY")
    _add_sub_header(doc, "Repayment capacity from operations", PRAMAAN_BLUE)
    c3_tbl = _create_styled_table(doc, 0, 2)
    c3_tbl.columns[0].width = Inches(2.5)

    rev_obj = figs.get("Revenue", {})
    rev_val = rev_obj.get("value") if rev_obj else None
    rev_prev = rev_obj.get("previous_value") if rev_obj else None
    if rev_val is not None:
        revenue_str = f"\u20b9{rev_prev:.2f} Cr" if (rev_val < 100 and rev_prev is not None) else f"\u20b9{rev_val:.2f} Cr"
    else:
        revenue_str = "Not extracted"

    ebitda_obj = figs.get("EBITDA", {})
    ebitda_str = f"\u20b9{ebitda_obj.get('value'):.2f} Cr" if ebitda_obj and ebitda_obj.get("value") is not None else "Not extracted"

    pat_obj = figs.get("PAT", {})
    pat_str = f"\u20b9{pat_obj.get('value'):.2f} Cr" if pat_obj and pat_obj.get("value") is not None else "Not extracted"

    _kv_row(c3_tbl, "Total Revenue (Reported)", revenue_str)
    _kv_row(c3_tbl, "EBITDA", ebitda_str)
    _kv_row(c3_tbl, "PAT", pat_str)

    # Bank Statement Summary
    if bank_stmt.get("total_transactions", 0) > 0:
        _kv_row(c3_tbl, "Bank Transactions Analyzed", str(bank_stmt.get("total_transactions", 0)))
        _kv_row(c3_tbl, "Bank Total Credits", f"\u20b9{bank_stmt.get('total_credits', 0):,.0f}")
        _kv_row(c3_tbl, "Bank Total Debits", f"\u20b9{bank_stmt.get('total_debits', 0):,.0f}")
        _kv_row(c3_tbl, "Average Monthly Balance", f"\u20b9{bank_stmt.get('avg_monthly_balance', 0):,.0f}")

    cap = site_visit.get("capacity_utilisation_pct")
    _kv_row(c3_tbl, "Site Visit Capacity", f"{cap}% — BELOW THRESHOLD [PRIMARY-01]" if cap and cap < 60 else f"{cap}%" if cap else "No quantitative data", DANGER_RED if cap and cap < 60 else None)
    doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 7: CAPITAL
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "7. CAPITAL")
    _add_sub_header(doc, "Net worth and financial leverage", PRAMAAN_BLUE)
    c4_tbl = _create_styled_table(doc, 0, 2)
    c4_tbl.columns[0].width = Inches(2.5)

    nw_obj = figs.get("Net Worth", {})
    nw_val = nw_obj.get("value") if nw_obj else None
    td_obj = figs.get("Total Debt", {})
    td_val = td_obj.get("value") if td_obj else None

    nw_str = f"\u20b9{nw_val:.2f} Cr" if nw_val is not None else data.get("net_worth", "Pending Extraction")
    td_str = f"\u20b9{td_val:.2f} Cr" if td_val is not None else f"\u20b9{karza.get('charge_amount_cr', 0):.2f} Cr (MCA Charges)" if karza.get("mca_charge_registered") else "None registered"

    if nw_val is not None and td_val is not None and nw_val != 0:
        de_ratio = td_val / nw_val
        de_str = f"{de_ratio:.2f}x"
    else:
        de_str = data.get("debt_equity", "N/A")

    _kv_row(c4_tbl, "Net Worth", nw_str)
    _kv_row(c4_tbl, "Total Debt", td_str)
    _kv_row(c4_tbl, "Debt / Equity Ratio", de_str)

    restate_det = restate.get("restatements_detected", False)
    _kv_row(c4_tbl, "Financial Restatements", "Detected [RESTATE-01]" if restate_det else "None", DANGER_RED if restate_det else SUCCESS_GREEN)
    doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 8: COLLATERAL & CONDITIONS
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "8. COLLATERAL & CONDITIONS")

    # Collateral
    _add_sub_header(doc, "Security Coverage", PRAMAAN_BLUE)
    c5_tbl = _create_styled_table(doc, 0, 2)
    c5_tbl.columns[0].width = Inches(2.5)

    holders = karza.get("charge_holders", [])
    _kv_row(c5_tbl, "Registered Charges (MCA)", ", ".join(holders) if holders else "None")

    col_data = pdf_scan.get("collateral", {}) if pdf_scan else {}
    if col_data:
        has_unsec = col_data.get("has_unsecured_loans", False)
        _kv_row(c5_tbl, "Unsecured Borrowings", "Detected [P-31]" if has_unsec else "None", DANGER_RED if has_unsec else SUCCESS_GREEN)

        findings = col_data.get("findings", [])
        for i, f in enumerate(findings):
            _kv_row(c5_tbl, f"Collateral Finding {i+1}", f"{f.get('security_type')} on {f.get('asset_type')}")

    # Conditions
    caro = pdf_scan.get("caro_default_found", False) if pdf_scan else False
    eom = pdf_scan.get("emphasis_of_matter_found", False) if pdf_scan else False
    _kv_row(c5_tbl, "CARO Findings", "Default [AUDIT-01]" if caro else "Clear", DANGER_RED if caro else SUCCESS_GREEN)
    _kv_row(c5_tbl, "Emphasis of Matter", "Flagged [AUDIT-02]" if eom else "Clear", WARN_AMBER if eom else SUCCESS_GREEN)
    doc.add_paragraph()

    # MD&A Sentiment
    if mda and mda.get("status") == "success":
        _add_sub_header(doc, "MD&A SENTIMENT ANALYSIS", PRAMAAN_BLUE)
        mda_tbl = _create_styled_table(doc, 0, 2)
        mda_tbl.columns[0].width = Inches(2.5)

        score = mda.get("sentiment_score", 0)
        risk = mda.get("risk_intensity", 0)

        _kv_row(mda_tbl, "Sentiment Score", f"{score} (positive = confident, negative = distressed)", DANGER_RED if score < 0 else SUCCESS_GREEN)
        _kv_row(mda_tbl, "Risk Intensity", str(risk), DANGER_RED if risk > 0.04 else SUCCESS_GREEN)
        _kv_row(mda_tbl, "Methodology", "Loughran-McDonald Financial Sentiment Dictionary")
        doc.add_paragraph()

        hw = mda.get("extracted_headwinds", [])
        if hw:
            _add_body_para(doc, "Key Risk Sentences from MD&A:", bold=True, color=WARN_AMBER)
            for h in hw[:5]:
                _add_bullet(doc, h)
            doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 9: CROSS-VERIFICATION SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    if cross_ver and cross_ver.get("verifications"):
        _add_section_header(doc, "9. CROSS-VERIFICATION SUMMARY")
        _add_sub_header(doc, "Automated verification of annual report claims against external data", PRAMAAN_BLUE)

        summary = cross_ver.get("summary", {})
        cv_tbl = _create_styled_table(doc, 0, 2)
        cv_tbl.columns[0].width = Inches(2.5)
        _kv_row(cv_tbl, "Claims Verified", str(summary.get("verified", 0)), SUCCESS_GREEN)
        _kv_row(cv_tbl, "Claims Contradicted", str(summary.get("mismatched", 0)), DANGER_RED if summary.get("mismatched", 0) > 0 else SUCCESS_GREEN)
        _kv_row(cv_tbl, "Partial Matches", str(summary.get("partial", 0)), WARN_AMBER if summary.get("partial", 0) > 0 else SUCCESS_GREEN)
        _kv_row(cv_tbl, "Unverifiable", str(summary.get("unverifiable", 0)))
        doc.add_paragraph()

        # Detail contradicted claims
        contradicted = [v for v in cross_ver["verifications"] if v.get("overall_status") == "MISMATCH" and v.get("claim_id") != "gst_bank_reconciliation"]
        if contradicted:
            _add_body_para(doc, "CONTRADICTED CLAIMS:", bold=True, color=DANGER_RED)
            for v in contradicted:
                claim_text = v.get("claim_text", v.get("claim_id", "Unknown"))
                checks = v.get("checks", [])
                detail = checks[0].get("detail", "") if checks else ""
                first_line = detail.split("\n")[0] if detail else ""
                _add_bullet(doc, f"{claim_text} — {first_line}", color=DANGER_RED)
            doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 10: RISK RULE MATRIX
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "10. RISK RULE MATRIX")
    penalties = decision_d.get("applied_penalties", [])
    if penalties:
        p_tbl = _create_styled_table(doc, rows=1, cols=4)
        _add_table_header_row(p_tbl, ["Rule Name", "Penalty (bps)", "Limit Impact", "Severity"])

        for p in penalties:
            row = p_tbl.add_row()
            raw_rule = p.get("rule_id", "")
            mapped = RULE_DISPLAY_NAMES.get(raw_rule, raw_rule)

            row.cells[0].text = f"{mapped}\n({p.get('trigger', '')})"
            row.cells[1].text = f"+{p.get('rate_penalty_bps', 0)} bps"
            row.cells[2].text = f"-{p.get('limit_reduction_pct', 0)}%"
            sev = "HIGH" if p.get('limit_reduction_pct', 0) > 10 else "MEDIUM"
            if raw_rule == "P-09": sev = "CRITICAL"
            row.cells[3].text = sev
            for run in row.cells[3].paragraphs[0].runs:
                run.bold = True
                if sev in ("CRITICAL", "HIGH"):
                    run.font.color.rgb = _rgb(DANGER_RED)
    else:
        _add_body_para(doc, "No risk rules triggered.", bold=True, color=SUCCESS_GREEN)
    doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 11: DECISION & CONDITIONS PRECEDENT
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "11. DECISION & CONDITIONS PRECEDENT")

    # Rate waterfall
    rate_steps = [f"Base Rate: {decision_d.get('base_rate_pct', 0.0):.2f}%"]
    lim_steps  = [f"Base Limit: \u20b9{decision_d.get('base_limit_cr', 0.0):.2f} Cr"]

    for p in penalties:
        bps = p.get("rate_penalty_bps", 0)
        lim = p.get("limit_reduction_pct", 0)
        mapped = RULE_DISPLAY_NAMES.get(p.get('rule_id'), p.get('rule_id'))
        if bps > 0: rate_steps.append(f"+ {bps} bps ({mapped})")
        if lim > 0: lim_steps.append(f"- {lim}% ({mapped})")

    rate_steps.append(f"FINAL RATE: {decision_d.get('final_rate_pct', 0.0):.2f}%")
    lim_steps.append(f"FINAL LIMIT: \u20b9{decision_d.get('final_limit_cr', 0.0):.2f} Cr")

    _add_body_para(doc, "Rate Calculation Waterfall:", bold=True)
    for s in rate_steps:
        _add_bullet(doc, s, bold="FINAL" in s)

    _add_body_para(doc, "Limit Calculation Waterfall:", bold=True)
    for s in lim_steps:
        _add_bullet(doc, s, bold="FINAL" in s)

    doc.add_paragraph()
    _add_body_para(doc, "Conditions Precedent (items to verify before disbursement):", bold=True)

    conds = []
    if "P-03" in triggered: conds.append("Obtain auditor clarification on CARO Clause (vii) default")
    if "P-06" in triggered: conds.append("Investigate circular trading flows and obtain management explanation")
    if "P-13" in triggered: conds.append("Obtain management response to adverse media findings")
    if "P-07" in triggered: conds.append("Re-verify plant capacity with independent chartered engineer")
    if "P-33" in triggered: conds.append("Reconcile GST turnover with bank credits — obtain CA certificate")
    if "P-28" in triggered: conds.append("Investigate round-trip bank transactions and obtain counterparty details")
    conds.append("Obtain board resolution, latest bank statements, ITR for 3 years")

    for c in conds:
        _add_bullet(doc, c)
    doc.add_paragraph()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 12: DISCLAIMER
    # ══════════════════════════════════════════════════════════════════════════
    _add_section_header(doc, "12. DISCLAIMER")
    disc = (
        "This Credit Appraisal Memorandum was generated by Project Pramaan "
        "Intelli-Credit Engine v1.0. All findings are extracted by deterministic "
        "regex from source documents and verified against external bureau APIs. "
        "No AI inference or hallucination. Every finding is traceable to the "
        "original document, page number, or external data source. "
        "This memo is auto-generated and should be reviewed by a credit officer "
        "before final sanction."
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
