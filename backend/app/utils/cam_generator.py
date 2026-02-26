"""
CAM Generator – Credit Appraisal Memo (Word Document)
======================================================
Generates a formatted python-docx Credit Appraisal Memo structured around
the Five Cs of Credit, populated entirely from the aggregated JSON decision data.

Zero LLM — every field is deterministically populated from the input dict.
"""
import logging
from datetime import datetime
from io import BytesIO
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette (RGBColor values for python-docx)
# ---------------------------------------------------------------------------
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

PRAMAAN_BLUE  = (0x0F, 0x33, 0x6B)   # #0F336B
DANGER_RED    = (0xDC, 0x26, 0x26)   # #DC2626
SUCCESS_GREEN = (0x16, 0x7A, 0x3E)   # #167A3E
WARN_AMBER    = (0xB4, 0x5A, 0x09)   # #B45A09
GREY          = (0x64, 0x74, 0x8B)   # #64748B


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _rgb(doc_color: tuple):
    return RGBColor(*doc_color)


def _set_cell_bg(cell, hex_color: str):
    """Set a table cell background fill."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _add_heading(doc, text: str, level: int = 1, color: tuple = PRAMAAN_BLUE):
    h = doc.add_heading(text, level=level)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in h.runs:
        run.font.color.rgb = _rgb(color)
    return h


def _kv_row(table, key: str, value: str, flag_color: tuple | None = None):
    """Add a key-value row to a table."""
    row = table.add_row()
    row.cells[0].text = key
    row.cells[0].paragraphs[0].runs[0].bold = True
    row.cells[1].text = str(value)
    if flag_color:
        for run in row.cells[1].paragraphs[0].runs:
            run.font.color.rgb = _rgb(flag_color)


def _flag_text(found: bool) -> tuple[str, tuple]:
    if found:
        return "⚠ YES — Triggered", DANGER_RED
    return "✓ NO — Clear", SUCCESS_GREEN


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------
def generate_cam(data: Dict[str, Any]) -> bytes:
    """
    Generate a Credit Appraisal Memo as a .docx file in memory.

    Args:
        data: Aggregated credit state dict containing keys:
              entity_name, perfios, karza, pdf_scan, primary_insights,
              decision, triggered_rules

    Returns:
        Raw bytes of the generated .docx file
    """
    if not _DOCX_AVAILABLE:
        raise RuntimeError(
            "python-docx is not installed. Run: pip install python-docx"
        )

    doc = Document()

    # ── Page margins ──────────────────────────────────────────────────────────
    for section in doc.sections:
        section.top_margin    = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)

    # ── Title block ───────────────────────────────────────────────────────────
    title = doc.add_heading("CREDIT APPRAISAL MEMORANDUM", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.color.rgb = _rgb(PRAMAAN_BLUE)
        run.font.size = Pt(18)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run("Project Pramaan — Intelli-Credit Engine")
    r.italic = True
    r.font.color.rgb = _rgb(GREY)
    r.font.size = Pt(10)

    doc.add_paragraph()

    # ── Summary table ─────────────────────────────────────────────────────────
    entity     = data.get("entity_name", "Acme Steels Pvt Ltd")
    decision_d = data.get("decision", {})
    triggered  = data.get("triggered_rules", [])

    meta_table = doc.add_table(rows=0, cols=2)
    meta_table.style = "Table Grid"
    meta_table.columns[0].width = Inches(2.2)
    meta_table.columns[1].width = Inches(4.0)

    meta_rows = [
        ("Entity",             entity),
        ("Date of Appraisal",  datetime.now().strftime("%d %B %Y")),
        ("Prepared by",        "Project Pramaan – Credit Committee Engine"),
        ("Base Limit",         f"₹{decision_d.get('base_limit_cr', 10.0):.1f} Cr"),
        ("Recommended Limit",  f"₹{decision_d.get('final_limit_cr', 10.0):.1f} Cr"),
        ("Base Rate",          f"{decision_d.get('base_rate_pct', 9.0):.2f}%"),
        ("Recommended Rate",   f"{decision_d.get('final_rate_pct', 9.0):.2f}% p.a."),
        ("Decision",           decision_d.get("recommendation", "PENDING").replace("_", " ")),
        ("Triggered Rules",    ", ".join(triggered) if triggered else "None"),
    ]
    for k, v in meta_rows:
        color = None
        if k == "Decision":
            rec = decision_d.get("recommendation", "")
            color = DANGER_RED if "MANUAL" in rec else (SUCCESS_GREEN if rec == "APPROVE" else WARN_AMBER)
        if k == "Triggered Rules" and triggered:
            color = DANGER_RED
        _kv_row(meta_table, k, v, color)

    doc.add_paragraph()
    doc.add_paragraph("─" * 80).runs[0].font.color.rgb = _rgb(GREY)

    # =========================================================================
    # Five Cs of Credit
    # =========================================================================

    # ── C1: CHARACTER (Karza) ─────────────────────────────────────────────────
    _add_heading(doc, "1. CHARACTER", level=1)
    doc.add_paragraph(
        "Source: Karza Litigation & Director KYB (deterministic API mock)"
    ).runs[0].italic = True

    karza = data.get("karza", {})
    c1_table = doc.add_table(rows=0, cols=2)
    c1_table.style = "Table Grid"
    litigations = karza.get("active_litigations", [])
    lit_text = "; ".join(litigations) if litigations else "None"
    _kv_row(c1_table, "Active Litigations",    lit_text,
            WARN_AMBER if litigations else SUCCESS_GREEN)
    _kv_row(c1_table, "Director Disqualified",
            "YES" if karza.get("director_disqualified") else "No",
            DANGER_RED if karza.get("director_disqualified") else SUCCESS_GREEN)
    _kv_row(c1_table, "MCA Charge Registered",
            f"Yes — ₹{karza.get('charge_amount_cr', 0):.1f} Cr ({', '.join(karza.get('charge_holders', []))})"
            if karza.get("mca_charge_registered") else "No",
            WARN_AMBER if karza.get("mca_charge_registered") else SUCCESS_GREEN)
    _kv_row(c1_table, "EPFO Compliance",       karza.get("epfo_compliance", "—"))
    if karza.get("metadata", {}).get("watch_flag"):
        _kv_row(c1_table, "Watch Flag",
                karza["metadata"]["watch_flag"], WARN_AMBER)
    doc.add_paragraph()

    # ── C2: CAPACITY (Perfios + Primary Insights) ─────────────────────────────
    _add_heading(doc, "2. CAPACITY", level=1)
    doc.add_paragraph(
        "Sources: Perfios GST Reconciliation (mock) + Site Visit Notes"
    ).runs[0].italic = True

    perfios = data.get("perfios", {})
    mismatch = perfios.get("gstr_2a_3b_mismatch_pct", 0)

    c2_table = doc.add_table(rows=0, cols=2)
    c2_table.style = "Table Grid"
    _kv_row(c2_table, "GSTR-2A vs 3B Mismatch",
            f"{mismatch:.1f}%",
            DANGER_RED if mismatch > 15 else SUCCESS_GREEN)
    _kv_row(c2_table, "P-01 Ghost Input Rule",
            "TRIGGERED (+100 bps)" if mismatch > 15 else "Clear",
            DANGER_RED if mismatch > 15 else SUCCESS_GREEN)
    _kv_row(c2_table, "Circular Trading Flag",
            "YES" if perfios.get("circular_trading_flag") else "No")
    _kv_row(c2_table, "ITC Reversal Required",
            f"Yes — ₹{perfios.get('itc_reversal_amount_lakh', 0):.1f} Lakh"
            if perfios.get("itc_reversal_required") else "No",
            WARN_AMBER if perfios.get("itc_reversal_required") else SUCCESS_GREEN)
    _kv_row(c2_table, "GST Filing Consistency", perfios.get("gst_filing_consistency", "—"))
    doc.add_paragraph()

    # Site visit notes
    notes = data.get("primary_insights", "").strip()
    doc.add_paragraph("Primary Insights — Site Visit Notes:").runs[0].bold = True
    doc.add_paragraph(notes if notes else "(No notes provided by credit officer)")
    doc.add_paragraph()

    # ── C3: CAPITAL ───────────────────────────────────────────────────────────
    _add_heading(doc, "3. CAPITAL", level=1)
    doc.add_paragraph(
        "Source: Balance Sheet (manual entry required — not yet connected to automated extraction)"
    ).runs[0].italic = True
    c3_table = doc.add_table(rows=0, cols=2)
    c3_table.style = "Table Grid"
    _kv_row(c3_table, "Net Worth",        data.get("net_worth", "— Pending officer entry"))
    _kv_row(c3_table, "Debt / Equity",    data.get("debt_equity", "— Pending officer entry"))
    _kv_row(c3_table, "EBITDA Margin",    data.get("ebitda_margin", "— Pending officer entry"))
    _kv_row(c3_table, "Current Ratio",    data.get("current_ratio", "— Pending officer entry"))
    doc.add_paragraph()

    # ── C4: COLLATERAL ────────────────────────────────────────────────────────
    _add_heading(doc, "4. COLLATERAL", level=1)
    doc.add_paragraph(
        "Source: MCA Charge Register + Officer Field Assessment"
    ).runs[0].italic = True
    c4_table = doc.add_table(rows=0, cols=2)
    c4_table.style = "Table Grid"
    charge = karza.get("mca_charge_registered", False)
    _kv_row(c4_table, "Existing Charge",
            f"₹{karza.get('charge_amount_cr', 0):.1f} Cr — {', '.join(karza.get('charge_holders', []))}"
            if charge else "None registered on MCA",
            WARN_AMBER if charge else SUCCESS_GREEN)
    _kv_row(c4_table, "Proposed Security",  data.get("proposed_security",  "— Pending officer entry"))
    _kv_row(c4_table, "Security Coverage",  data.get("security_coverage",  "— Pending officer entry"))
    doc.add_paragraph()

    # ── C5: CONDITIONS (PDF Auditor Compliance Scan & YoY Restatements) ───────
    _add_heading(doc, "5. CONDITIONS", level=1)
    doc.add_paragraph(
        "Source: Independent Auditor's Report & YoY Comparative Data — Deterministic Scan (zero-LLM)"
    ).runs[0].italic = True

    pdf_scan = data.get("pdf_scan", {})
    caro_found    = pdf_scan.get("caro_default_found", False)
    adverse_found = pdf_scan.get("adverse_opinion_found", False)
    emphasis_found = pdf_scan.get("emphasis_of_matter_found", False)

    c5_table = doc.add_table(rows=0, cols=2)
    c5_table.style = "Table Grid"

    caro_text,    caro_color    = _flag_text(caro_found)
    adverse_text, adverse_color = _flag_text(adverse_found)
    _kv_row(c5_table, "CARO 2020 Statutory Default",   caro_text,    caro_color)
    _kv_row(c5_table, "Auditor Qualification",          adverse_text, adverse_color)
    _kv_row(c5_table, "Emphasis of Matter",
            "⚠ YES" if emphasis_found else "✓ NO",
            WARN_AMBER if emphasis_found else SUCCESS_GREEN)

    restatement_data = data.get("restatement_data", {})
    if restatement_data:
        restatement_found = restatement_data.get("restatements_detected", False)
        auditor_changed = restatement_data.get("auditor_changed", False)
        _kv_row(c5_table, "Financial Restatement (>2%)",
                "⚠ YES [CRITICAL]" if restatement_found else "✓ NO",
                DANGER_RED if restatement_found else SUCCESS_GREEN)
        _kv_row(c5_table, "Auditor Rotation/Change",
                "⚠ YES [HIGH]" if auditor_changed else "✓ NO",
                WARN_AMBER if auditor_changed else SUCCESS_GREEN)

    if pdf_scan.get("sections_detected", {}).get("auditors_report"):
        sr = pdf_scan["sections_detected"]["auditors_report"]
        _kv_row(c5_table, "Auditor Report Pages",
                f"p.{sr.get('start_page', '?')} – {sr.get('end_page', '?')} "
                f"({sr.get('page_count', '?')} pages, conf={sr.get('confidence', 0):.0%})")

    # Evidence snippets
    caro_findings = pdf_scan.get("caro_findings", [])
    qual_findings = pdf_scan.get("auditor_qualification_findings", [])

    for group_label, findings, color in [
        ("CARO 2020 Evidence", caro_findings,    DANGER_RED),
        ("Auditor Qualification Evidence", qual_findings, WARN_AMBER),
    ]:
        if findings:
            doc.add_paragraph()
            p = doc.add_paragraph(f"{group_label}:")
            p.runs[0].bold = True
            p.runs[0].font.color.rgb = _rgb(color)
            for i, f in enumerate(findings[:3], 1):   # cap at 3 snippets
                doc.add_paragraph(
                    f"[{i}] {f.get('pattern', '')} — "
                    f"{f.get('snippet', '')[:300]}…",
                    style="List Bullet"
                ).runs[0].font.size = Pt(9)

    doc.add_paragraph()

    # ── Applied Penalties Summary ─────────────────────────────────────────────
    _add_heading(doc, "PENALTY ACCUMULATION", level=1, color=DANGER_RED if triggered else SUCCESS_GREEN)
    penalties = decision_d.get("applied_penalties", [])
    if penalties:
        pen_table = doc.add_table(rows=0, cols=4)
        pen_table.style = "Table Grid"

        # Header row
        hdr = pen_table.add_row()
        for i, h in enumerate(["Rule", "Description", "Rate Penalty", "Limit Cut"]):
            hdr.cells[i].text = h
            hdr.cells[i].paragraphs[0].runs[0].bold = True
            _set_cell_bg(hdr.cells[i], "0F336B")
            for run in hdr.cells[i].paragraphs[0].runs:
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        for p in penalties:
            row = pen_table.add_row()
            row.cells[0].text = p.get("rule_id", "")
            row.cells[1].text = p.get("trigger", "")
            row.cells[2].text = f"+{p.get('rate_penalty_bps', 0)} bps"
            row.cells[3].text = f"-{p.get('limit_reduction_pct', 0)}%"
    else:
        doc.add_paragraph("No penalties applied — report is clean.").runs[0].font.color.rgb = _rgb(SUCCESS_GREEN)

    doc.add_paragraph()
    doc.add_paragraph("─" * 80).runs[0].font.color.rgb = _rgb(GREY)

    # ── Signature block ───────────────────────────────────────────────────────
    _add_heading(doc, "CREDIT COMMITTEE SIGN-OFF", level=2)
    sign_table = doc.add_table(rows=2, cols=3)
    sign_table.style = "Table Grid"
    for i, role in enumerate(["Relationship Manager", "Credit Analyst", "Credit Committee Head"]):
        sign_table.rows[0].cells[i].text = role
        sign_table.rows[1].cells[i].text = "\n\nSignature: ________________\nDate: ________________"

    doc.add_paragraph()
    foot = doc.add_paragraph(
        f"Generated by Project Pramaan — {datetime.now().strftime('%d %b %Y %H:%M')}  |  "
        "Deterministic. No AI-generated text. Every finding traceable to source document."
    )
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    foot.runs[0].font.color.rgb = _rgb(GREY)
    foot.runs[0].font.size = Pt(8)

    # ── Serialise to bytes ────────────────────────────────────────────────────
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    logger.info(f"CAM generated for entity='{entity}' ({buffer.getbuffer().nbytes:,} bytes)")
    return buffer.read()
