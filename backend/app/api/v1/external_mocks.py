"""
Mock External Intelligence APIs
================================
Simulates responses from third-party bureau APIs used by the Credit Committee.

  GET /api/v1/mock/perfios  – GST reconciliation (Agent A: Capacity / Ghost Input)
  GET /api/v1/mock/karza    – Litigation & Director KYB (Agent C: Character / Web Sleuth)
  GET /api/v1/mock/cibil    – Credit bureau score & facility details
  GET /api/v1/mock/ecourts  – Court case records (synthetic fallback)
  GET /api/v1/mock/news     – Adverse media articles (synthetic fallback)

These are deterministic mock fixtures. In production they would call the real APIs
and return identical JSON schemas so the orchestrator layer never changes.
All mocks are entity-aware via _last_entity (set by /mock/set-entity).
"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mock", tags=["External Intelligence (Mock)"])

_last_entity = {"name": "Unknown Entity", "cin": "U27100MH2010PTC123456"}

class EntityUpdate(BaseModel):
    entity_name: str
    cin: str

@router.post(
    "/set-entity",
    summary="Update the simulated entity",
    description="Updates the underlying mock entity to dynamically match the uploaded PDF."
)
async def set_entity(payload: EntityUpdate):
    _last_entity["name"] = payload.entity_name
    _last_entity["cin"] = payload.cin
    return {"status": "success", "entity": _last_entity}


# ═════════════════════════════════════════════════════════════════════════════
# PERFIOS — GST Reconciliation
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/perfios",
    summary="Perfios – GST Reconciliation Mock",
    description=(
        "Simulates a Perfios bureau response for GST-2A vs 3B reconciliation. "
        "Includes monthly GSTR-3B filings, top suppliers from GSTR-2A, ITC breakdown. "
        "gstr_2a_3b_mismatch_pct > 15 triggers Rule P-01 (Ghost Input Trap)."
    ),
)
async def mock_perfios():
    """
    Fixture: 18.5% mismatch → P-01 triggered (+100 bps / −10% limit).
    2 delayed filings + 1 not filed in 12 months.
    """
    return {
        "status": "success",
        "provider": "Perfios (mock)",
        "entity": _last_entity["name"],
        "assessment_period": "FY 2023-24",
        "gstin": "27AABCA1234A1Z5",
        "gst_registration_status": "Active",

        # ── Headline metrics ────────────────────────────────────────────
        "gstr_2a_3b_mismatch_pct": 18.5,      # > 15% → P-01 Ghost Input Trap
        "circular_trading_flag": False,
        "gst_filing_consistency": "Irregular",  # 2 delayed + 1 not filed
        "gst_filing_discipline_score": 83.3,
        "itc_reversal_required": True,
        "itc_reversal_amount_lakh": 12.4,
        "gst_turnover_cr": 0.58,      # ~₹0.58 Cr — aligns with sample CSVs (~₹0.48 Cr credits)
        "annual_gst_liability_lakh": 102.6,
        "annual_itc_claimed_lakh": 80.2,

        # ── Monthly GSTR-3B filings (12 months) ────────────────────────
        "gstr_3b_filings": [
            {"month": "Apr-23", "status": "Filed",     "tax_paid_lakh": 8.2,  "itc_claimed_lakh": 6.1},
            {"month": "May-23", "status": "Filed",     "tax_paid_lakh": 7.9,  "itc_claimed_lakh": 5.8},
            {"month": "Jun-23", "status": "Filed",     "tax_paid_lakh": 9.1,  "itc_claimed_lakh": 7.0},
            {"month": "Jul-23", "status": "Delayed",   "tax_paid_lakh": 6.5,  "itc_claimed_lakh": 5.2},
            {"month": "Aug-23", "status": "Filed",     "tax_paid_lakh": 8.8,  "itc_claimed_lakh": 6.4},
            {"month": "Sep-23", "status": "Filed",     "tax_paid_lakh": 10.3, "itc_claimed_lakh": 7.9},
            {"month": "Oct-23", "status": "Filed",     "tax_paid_lakh": 9.7,  "itc_claimed_lakh": 7.1},
            {"month": "Nov-23", "status": "Delayed",   "tax_paid_lakh": 5.1,  "itc_claimed_lakh": 4.8},
            {"month": "Dec-23", "status": "Filed",     "tax_paid_lakh": 11.0, "itc_claimed_lakh": 8.5},
            {"month": "Jan-24", "status": "Filed",     "tax_paid_lakh": 8.6,  "itc_claimed_lakh": 6.3},
            {"month": "Feb-24", "status": "Filed",     "tax_paid_lakh": 9.4,  "itc_claimed_lakh": 7.2},
            {"month": "Mar-24", "status": "Not Filed", "tax_paid_lakh": 0,    "itc_claimed_lakh": 0},
        ],

        # ── Top suppliers from GSTR-2A ──────────────────────────────────
        "top_suppliers_gstr2a": [
            {"name": "Vertex Holdings Pvt Ltd",   "gstin": "27AABCV1234A1Z5", "invoice_value_lakh": 42.3, "itc_lakh": 7.6},
            {"name": "Nova Trading Corp",         "gstin": "29AADCN5678B1Z2", "invoice_value_lakh": 31.1, "itc_lakh": 5.6},
            {"name": "Bharat Raw Materials Ltd",  "gstin": "24AABCB9012C1Z8", "invoice_value_lakh": 25.8, "itc_lakh": 4.6},
            {"name": "Sai Logistics Pvt Ltd",     "gstin": "27AADCS3456D1Z1", "invoice_value_lakh": 18.9, "itc_lakh": 3.4},
            {"name": "Rajan & Sons Traders",      "gstin": "33AABCR7890E1Z4", "invoice_value_lakh": 12.5, "itc_lakh": 2.3},
        ],

        "metadata": {
            "data_freshness": "2024-03-31",
            "rule_triggered": "P-01",
            "trigger_condition": "gstr_2a_3b_mismatch_pct > 15",
            "filing_summary": "9 filed on time, 2 delayed, 1 not filed",
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# KARZA — Litigation & Director KYB
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/karza",
    summary="Karza – Litigation, Director KYB & Compliance Mock",
    description=(
        "Simulates a Karza bureau response for litigation history, director KYB, "
        "GST registrations, and compliance timeline."
    ),
)
async def mock_karza():
    """
    Fixture: One Section 138 cheque bounce case pending — secondary watch flag.
    3 directors with DINs, 2 GST registrations (1 cancelled), compliance timeline.
    """
    return {
        "status": "success",
        "provider": "Karza (mock)",
        "entity": _last_entity["name"],
        "cin": _last_entity["cin"],

        # ── Litigation ──────────────────────────────────────────────────
        "active_litigations": [
            "Section 138 NI Act – Cheque Bounce – Pending at JMFC Mumbai"
        ],
        "total_litigation_count": 1,
        "director_disqualified": False,

        # ── Charges ─────────────────────────────────────────────────────
        "mca_charge_registered": True,
        "charge_amount_cr": 7.0,
        "charge_holders": ["HDFC Bank Ltd"],
        "epfo_compliance": "Regular",

        # ── Directors ───────────────────────────────────────────────────
        "directors": [
            {"name": "Rajesh Kumar Agarwal", "din": "00123456", "designation": "Managing Director",    "appointment_date": "2015-04-01"},
            {"name": "Sunita Devi Agarwal",  "din": "00789012", "designation": "Whole-Time Director",  "appointment_date": "2015-04-01"},
            {"name": "Amit Prakash Desai",   "din": "01234567", "designation": "Independent Director", "appointment_date": "2020-08-15"},
        ],

        # ── GST Registrations ───────────────────────────────────────────
        "gst_registrations": [
            {"gstin": "27AABCA1234A1Z5", "state": "Maharashtra", "status": "Active",    "registration_date": "2017-07-01"},
            {"gstin": "29AABCA1234A1Z8", "state": "Karnataka",   "status": "Cancelled", "cancellation_date": "2023-03-15"},
        ],

        # ── Compliance Timeline ─────────────────────────────────────────
        "compliance_timeline": [
            {"date": "2024-01-10", "event": "Annual Return Filed (FY 2022-23)",   "status": "On Time"},
            {"date": "2023-09-28", "event": "ROC Filing - Form AOC-4",            "status": "Delayed by 15 days"},
            {"date": "2023-06-30", "event": "Board Meeting held",                 "status": "Compliant"},
            {"date": "2023-03-15", "event": "GST Registration Cancelled (Karnataka)", "status": "Voluntary Surrender"},
            {"date": "2022-11-20", "event": "Charge Registered - HDFC Bank",      "status": "7.0 Cr secured loan"},
        ],
        "roc_filing_status": "Up to Date",
        "annual_return_filed": True,

        "metadata": {
            "data_freshness": "2024-01-15",
            "rule_triggered": None,
            "watch_flag": "Section 138 pending — credit committee manual note required",
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# NETWORK GRAPH — Circular Trading
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/network-graph",
    summary="Network Graph – Circular Trading Fraud Mock",
    description=(
        "Simulates a network intelligence response detecting a circular money-laundering loop. "
        "Returns a node-edge graph showing Applicant → Vertex Holdings → Nova Corp → Applicant. "
        "circular_trading_detected=true triggers Rule P-06 (Circular Fraud Detected, −50% limit)."
    ),
)
async def mock_network_graph():
    """
    Fixture: Three-entity circular trading loop.
    """
    return {
        "status": "success",
        "provider": "Network Intelligence (mock)",
        "entity": _last_entity["name"],
        "circular_trading_detected": True,
        "nodes": [
            {"id": "acme",   "label": f"{_last_entity['name']}\n(Applicant)", "type": "applicant", "amount_cr": 5.0},
            {"id": "vertex", "label": "Vertex Holdings\n(Shell)",              "type": "shell",     "amount_cr": 4.8},
            {"id": "nova",   "label": "Nova Corp\n(Shell)",                    "type": "shell",     "amount_cr": 4.5},
            {"id": "dir1",   "label": "Rahul Sharma\n(Director)",              "type": "director",  "amount_cr": 0},
            {"id": "dir2",   "label": "Amit Desai\n(Director)",                "type": "director",  "amount_cr": 0},
        ],
        "links": [
            {"source": "acme",   "target": "vertex", "value": 5.0, "label": "₹5.0 Cr"},
            {"source": "vertex", "target": "nova",   "value": 4.8, "label": "₹4.8 Cr"},
            {"source": "nova",   "target": "acme",   "value": 4.5, "label": "₹4.5 Cr"},
            {"source": "dir1",   "target": "acme",   "value": 0.5, "label": "MD"},
            {"source": "dir1",   "target": "nova",   "value": 0.5, "label": "Beneficiary"},
            {"source": "dir2",   "target": "vertex", "value": 0.5, "label": "Promoter"},
        ],
        "metadata": {
            "data_freshness": "2024-01-15",
            "rule_triggered": "P-06",
            "trigger_condition": "circular_trading_detected == true",
            "loop_value_cr": 5.0,
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# CIBIL — Credit Bureau Score & Facilities
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/cibil",
    summary="CIBIL Commercial – Credit Bureau Score Mock",
    description=(
        "Simulates a CIBIL Commercial credit bureau response. "
        "Returns credit score, rating, DPD history, facility-level details, and outstanding."
    ),
)
async def mock_cibil():
    """
    Fixture: Moderate credit score (72) with minor DPD history.
    SBI Cash Credit in SMA-1 (30 DPD). Suit filed 3.5 Cr.
    """
    return {
        "status": "success",
        "provider": "CIBIL Commercial (mock)",
        "entity": _last_entity["name"],
        "cin": _last_entity["cin"],

        # ── Score & Rating ──────────────────────────────────────────────
        "credit_score": 72,
        "rating": "BB+",
        "score_range": "1–100",

        # ── DPD History ─────────────────────────────────────────────────
        "dpd_30_count": 2,
        "dpd_60_count": 0,
        "dpd_90_count": 0,
        "suit_filed_amount_cr": 3.5,

        # ── Portfolio Summary ───────────────────────────────────────────
        "total_credit_facilities": 4,
        "total_outstanding_cr": 12.8,
        "overdue_amount_cr": 0.8,
        "oldest_account_age_years": 8,
        "enquiry_count_6m": 5,
        "written_off_amount_cr": 0,

        # ── Facility-Level Detail ───────────────────────────────────────
        "facilities": [
            {"type": "Term Loan",        "lender": "HDFC Bank",  "sanctioned_cr": 7.0, "outstanding_cr": 6.2, "dpd_current": 0,  "status": "Standard"},
            {"type": "Cash Credit",      "lender": "SBI",        "sanctioned_cr": 3.0, "outstanding_cr": 2.8, "dpd_current": 30, "status": "SMA-1"},
            {"type": "Working Capital",  "lender": "ICICI Bank", "sanctioned_cr": 2.5, "outstanding_cr": 2.1, "dpd_current": 0,  "status": "Standard"},
            {"type": "Letter of Credit", "lender": "Axis Bank",  "sanctioned_cr": 1.5, "outstanding_cr": 1.7, "dpd_current": 0,  "status": "Standard"},
        ],

        "metadata": {
            "data_freshness": "2024-01-20",
            "bureau": "TransUnion CIBIL",
            "report_type": "Commercial Credit Report (CCR)",
        },
    }


# ═════════════════════════════════════════════════════════════════════════════
# eCOURTS — Synthetic Court Cases (fallback when real API unreachable)
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/ecourts",
    summary="eCourts – Synthetic Court Case Records",
    description=(
        "Synthetic fallback for eCourts data when the real API is unreachable. "
        "Returns 3 cases: 1 NCLT insolvency petition (CRITICAL), 1 civil recovery, 1 cheque bounce."
    ),
)
async def mock_ecourts():
    """
    Fixture: 3 cases, 1 high-risk NCLT Section 7 IBC.
    Triggers P-15 (Active Court Proceedings).
    """
    return {
        "status": "success",
        "provider": "eCourts (mock)",
        "entity": _last_entity["name"],
        "cases_found": 3,
        "high_risk_cases": 1,
        "cases": [
            {
                "case_number": "CS/2023/04521",
                "court": "City Civil Court, Mumbai",
                "case_type": "Civil Suit",
                "filing_date": "2023-06-15",
                "parties": f"{_last_entity['name']} vs Vertex Holdings Pvt Ltd",
                "status": "Pending",
                "next_hearing": "2024-03-20",
                "subject": "Recovery of trade dues",
                "amount_cr": 2.3,
            },
            {
                "case_number": "CP/2023/00187",
                "court": "NCLT Mumbai Bench",
                "case_type": "Company Petition",
                "filing_date": "2023-09-01",
                "parties": f"HDFC Bank vs {_last_entity['name']}",
                "status": "Admitted",
                "next_hearing": "2024-04-12",
                "subject": "Application under Section 7 IBC — default on term loan",
                "amount_cr": 7.0,
            },
            {
                "case_number": "CC/2022/03891",
                "court": "JMFC Mumbai",
                "case_type": "Criminal Complaint",
                "filing_date": "2022-11-10",
                "parties": f"M/s Sai Logistics vs {_last_entity['name']}",
                "status": "Pending",
                "next_hearing": "2024-02-28",
                "subject": "Section 138 NI Act — Cheque Dishonour",
                "amount_cr": 0.45,
            },
        ],
        "findings": [
            {
                "signal": "NCLT Section 7 IBC application admitted — insolvency proceeding initiated by secured creditor",
                "court": "NCLT Mumbai Bench",
                "filing_date": "2023-09-01",
                "severity": "CRITICAL",
            },
        ],
        "triggered_rules": ["P-15"],
        "source": "eCourts (mock)",
    }


# ═════════════════════════════════════════════════════════════════════════════
# NEWS — Synthetic Adverse Media (fallback when NewsAPI key missing)
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/news",
    summary="News – Synthetic Adverse Media Articles",
    description=(
        "Synthetic fallback for news data when NewsAPI key is not configured. "
        "Returns 3 articles: 1 CRITICAL (NCLT), 1 HIGH (ED probe), 1 neutral."
    ),
)
async def mock_news():
    """
    Fixture: 2 red-flag articles + 1 neutral.
    Triggers P-13 (Adverse Media Detected).
    """
    return {
        "status": "success",
        "provider": "NewsAPI (mock)",
        "entity": _last_entity["name"],
        "articles_found": 3,
        "red_flag_count": 2,
        "articles": [
            {
                "headline": f"NCLT admits insolvency plea against {_last_entity['name']} over \u20b97 Cr loan default",
                "source": "Economic Times",
                "published": "2023-10-15",
                "url": "#",
                "severity": "CRITICAL",
                "summary": "HDFC Bank filed petition under Section 7 of IBC after company defaulted on term loan repayment.",
            },
            {
                "headline": f"ED probes shell company links in {_last_entity['name']} supply chain",
                "source": "Mint",
                "published": "2023-12-02",
                "url": "#",
                "severity": "HIGH",
                "summary": "Enforcement Directorate examining circular transactions between applicant and two shell entities.",
            },
            {
                "headline": f"{_last_entity['name']} reports 12% revenue growth in Q3 FY24",
                "source": "Business Standard",
                "published": "2024-01-20",
                "url": "#",
                "severity": "NONE",
                "summary": "Company reported improved quarterly performance driven by domestic demand.",
            },
        ],
        "red_flags": [
            {
                "headline": f"NCLT admits insolvency plea against {_last_entity['name']} over \u20b97 Cr loan default",
                "source": "Economic Times",
                "severity": "CRITICAL",
                "summary": "HDFC Bank filed petition under Section 7 of IBC after company defaulted on term loan repayment.",
            },
            {
                "headline": f"ED probes shell company links in {_last_entity['name']} supply chain",
                "source": "Mint",
                "severity": "HIGH",
                "summary": "Enforcement Directorate examining circular transactions between applicant and two shell entities.",
            },
        ],
        "adverse_media_detected": True,
        "triggered_rules": ["P-13"],
        "source": "NewsAPI (mock)",
    }


# ═════════════════════════════════════════════════════════════════════════════
# AUDITOR BLACKLIST — Institutional Memory Check
# ═════════════════════════════════════════════════════════════════════════════

# Simulated institutional blacklist database — in production this would be a
# persistent database maintained by the bank's risk/compliance team.
AUDITOR_BLACKLIST_DB = {
    # Firm name (uppercased for matching) → blacklist record
    "GUPTA SHARMA & ASSOCIATES": {
        "firm_name": "Gupta Sharma & Associates",
        "frn": "012345S",
        "blacklisted_by": ["Internal — Credit Risk", "NFRA"],
        "reason": "Failed to flag related party transactions in 3 consecutive audits; NFRA order dated 14-Sep-2023 for professional misconduct",
        "blacklisted_since": "2023-10-01",
        "severity": "HIGH",
        "nfra_order": "NFRA/DO/2023/0047",
        "prior_incidents": 2,
    },
    "RAJESH KUMAR & CO": {
        "firm_name": "Rajesh Kumar & Co",
        "frn": "008761N",
        "blacklisted_by": ["RBI Circular", "Internal — Fraud Investigation"],
        "reason": "Audit firm involved in IL&FS subsidiary audits; RBI flagged for inadequate verification of NPA classification",
        "blacklisted_since": "2022-03-15",
        "severity": "CRITICAL",
        "nfra_order": None,
        "prior_incidents": 5,
    },
    "PKR & ASSOCIATES": {
        "firm_name": "PKR & Associates",
        "frn": "015432W",
        "blacklisted_by": ["ICAI Disciplinary Committee"],
        "reason": "ICAI disciplinary action for issuing clean audit report despite known going concern issues; suspended from practice for 6 months",
        "blacklisted_since": "2024-01-20",
        "severity": "MEDIUM",
        "nfra_order": None,
        "prior_incidents": 1,
    },
    "MAXWELL PATEL LLP": {
        "firm_name": "Maxwell Patel LLP",
        "frn": "119876W/W100234",
        "blacklisted_by": ["Internal — Watchlist"],
        "reason": "Under monitoring — audited 3 accounts that subsequently turned NPA within 12 months of clean audit opinion",
        "blacklisted_since": "2024-06-01",
        "severity": "LOW",
        "nfra_order": None,
        "prior_incidents": 0,
    },
}

# Firms on the watchlist (not blacklisted but flagged for enhanced due diligence)
AUDITOR_WATCHLIST_DB = {
    "SR BATLIBOI & CO LLP": {
        "firm_name": "SR Batliboi & Co LLP",
        "frn": "301003E/E300005",
        "reason": "Large firm — no adverse findings, but NFRA inspection pending for FY24 audits",
        "watch_since": "2024-09-01",
        "severity": "INFO",
    },
}


def check_auditor_blacklist(auditor_name: str) -> dict:
    """
    Check an auditor firm name against the institutional blacklist and watchlist.
    Returns a screening result dict.
    """
    if not auditor_name:
        return {
            "status": "NOT_CHECKED",
            "auditor_name": None,
            "message": "No auditor name extracted from annual report",
            "blacklisted": False,
            "watchlisted": False,
            "records": [],
        }

    name_upper = auditor_name.strip().upper()

    # Check blacklist (fuzzy: check if any blacklist key is contained in name or vice versa)
    matched_records = []
    for bl_key, bl_record in AUDITOR_BLACKLIST_DB.items():
        if bl_key in name_upper or name_upper in bl_key:
            matched_records.append({**bl_record, "list_type": "BLACKLISTED"})

    for wl_key, wl_record in AUDITOR_WATCHLIST_DB.items():
        if wl_key in name_upper or name_upper in wl_key:
            matched_records.append({**wl_record, "list_type": "WATCHLIST"})

    is_blacklisted = any(r["list_type"] == "BLACKLISTED" for r in matched_records)
    is_watchlisted = any(r["list_type"] == "WATCHLIST" for r in matched_records)

    if is_blacklisted:
        status = "BLACKLISTED"
        message = f"ALERT: {auditor_name} appears on institutional blacklist"
    elif is_watchlisted:
        status = "WATCHLIST"
        message = f"NOTICE: {auditor_name} is on enhanced monitoring watchlist"
    else:
        status = "CLEAR"
        message = f"{auditor_name} — no adverse records found in institutional memory"

    return {
        "status": status,
        "auditor_name": auditor_name,
        "message": message,
        "blacklisted": is_blacklisted,
        "watchlisted": is_watchlisted,
        "records": matched_records,
        "total_firms_in_blacklist": len(AUDITOR_BLACKLIST_DB),
        "total_firms_in_watchlist": len(AUDITOR_WATCHLIST_DB),
        "database_last_updated": "2024-12-15",
        "source": "Pramaan Institutional Memory (mock)",
    }


@router.get(
    "/auditor-blacklist",
    summary="Auditor Blacklist – Institutional Memory Check",
    description=(
        "Checks the statutory auditor against the bank's institutional blacklist database. "
        "Sources: Internal fraud investigations, NFRA orders, ICAI disciplinary actions, "
        "RBI circulars, and internal watchlist. Returns screening status: "
        "CLEAR / WATCHLIST / BLACKLISTED."
    ),
)
async def mock_auditor_blacklist(auditor_name: str = ""):
    """Mock endpoint — in production, queries persistent institutional memory DB."""
    return check_auditor_blacklist(auditor_name)


# ═════════════════════════════════════════════════════════════════════════════
# LOAN PURPOSE VERIFICATION — Claimed vs Ground Truth
# ═════════════════════════════════════════════════════════════════════════════

def verify_loan_purpose(
    stated_purpose: str,
    bank_top_categories: dict = None,
    mca_activity: str = "",
) -> dict:
    """
    Compares the borrower's stated loan purpose against ground truth signals
    from bank statements, MCA filings, and supply chain data.

    In production this would cross-reference:
      - Loan application / sanction letter stated purpose
      - Actual bank outflow categories (capex vs opex vs related-party)
      - MCA registered business activity
      - Supply chain vendor concentration
    """
    # ── Demo mock data (deterministic) ──────────────────────────────────────
    if not stated_purpose:
        stated_purpose = "Working Capital for manufacturing operations"

    if not bank_top_categories:
        bank_top_categories = {
            "Vendor Payments (Raw Materials)": 31.2,
            "Related Party Transfers": 24.8,
            "Salary & Wages": 12.5,
            "Real Estate / Property": 18.3,
            "Utilities & Overheads": 8.1,
            "Unclassified / Cash Withdrawals": 5.1,
        }

    if not mca_activity:
        mca_activity = "Manufacture of textiles"

    # ── Analyze mismatches ──────────────────────────────────────────────────
    flags = []
    overall_status = "MATCH"  # MATCH | PARTIAL_MISMATCH | MISMATCH

    purpose_lower = stated_purpose.lower()
    is_working_capital = any(k in purpose_lower for k in ["working capital", "operational", "manufacturing"])

    # Flag 1: Related party transfers > 15%
    related_party_pct = bank_top_categories.get("Related Party Transfers", 0)
    if related_party_pct > 15:
        flags.append({
            "flag": "HIGH_RELATED_PARTY_OUTFLOW",
            "severity": "HIGH" if related_party_pct > 25 else "MEDIUM",
            "detail": f"{related_party_pct}% of bank outflows directed to related parties — inconsistent with stated working capital purpose",
            "ground_truth_value": f"{related_party_pct}%",
        })
        overall_status = "MISMATCH" if related_party_pct > 25 else "PARTIAL_MISMATCH"

    # Flag 2: Real estate spending when purpose is working capital
    real_estate_pct = bank_top_categories.get("Real Estate / Property", 0)
    if is_working_capital and real_estate_pct > 10:
        flags.append({
            "flag": "FUND_DIVERSION_REAL_ESTATE",
            "severity": "HIGH",
            "detail": f"{real_estate_pct}% of funds routed to real estate/property despite stated purpose being working capital",
            "ground_truth_value": f"{real_estate_pct}%",
        })
        overall_status = "MISMATCH"

    # Flag 3: Low vendor payments for working capital claims
    vendor_pct = bank_top_categories.get("Vendor Payments (Raw Materials)", 0)
    if is_working_capital and vendor_pct < 35:
        flags.append({
            "flag": "LOW_OPERATIONAL_SPEND",
            "severity": "MEDIUM",
            "detail": f"Only {vendor_pct}% of outflows to vendors/raw materials — expected >50% for genuine working capital usage",
            "ground_truth_value": f"{vendor_pct}%",
        })
        if overall_status == "MATCH":
            overall_status = "PARTIAL_MISMATCH"

    # Flag 4: Unclassified cash > 10%
    unclassified_pct = bank_top_categories.get("Unclassified / Cash Withdrawals", 0)
    if unclassified_pct > 10:
        flags.append({
            "flag": "HIGH_UNCLASSIFIED_OUTFLOWS",
            "severity": "MEDIUM",
            "detail": f"{unclassified_pct}% of outflows are unclassified or cash withdrawals — cannot verify end-use",
            "ground_truth_value": f"{unclassified_pct}%",
        })
        if overall_status == "MATCH":
            overall_status = "PARTIAL_MISMATCH"

    # ── Build ground truth summary ──────────────────────────────────────────
    ground_truth_summary = []
    sorted_cats = sorted(bank_top_categories.items(), key=lambda x: x[1], reverse=True)
    for cat, pct in sorted_cats:
        ground_truth_summary.append({"category": cat, "percentage": pct})

    triggered_rules = []
    if overall_status == "MISMATCH":
        triggered_rules.append("P-34")

    return {
        "status": "verified",
        "stated_purpose": stated_purpose,
        "overall_status": overall_status,
        "mca_business_activity": mca_activity,
        "mca_alignment": _check_mca_alignment(purpose_lower, mca_activity.lower()),
        "fund_utilization": ground_truth_summary,
        "flags": flags,
        "triggered_rules": triggered_rules,
        "verdict": _build_verdict(overall_status, stated_purpose, flags),
    }


def _check_mca_alignment(purpose: str, mca: str) -> dict:
    """Check if stated purpose aligns with MCA-registered business activity."""
    # Simple keyword overlap check
    # For demo, always show a realistic result
    if any(k in mca for k in ["textile", "manufactur", "steel", "chemical", "pharma"]):
        if any(k in purpose for k in ["working capital", "manufactur", "operational"]):
            return {"aligned": True, "detail": f"Stated purpose consistent with MCA activity: '{mca.title()}'"}
    return {"aligned": False, "detail": f"Stated purpose may not align with MCA activity: '{mca.title()}'"}


def _build_verdict(status: str, purpose: str, flags: list) -> str:
    """Build a human-readable verdict string."""
    if status == "MATCH":
        return f"Fund utilization pattern is consistent with the stated purpose: '{purpose}'"
    elif status == "PARTIAL_MISMATCH":
        flag_names = [f["flag"].replace("_", " ").title() for f in flags[:2]]
        return f"Partial concerns detected — {', '.join(flag_names)}. Recommend enhanced monitoring of fund end-use."
    else:
        flag_names = [f["flag"].replace("_", " ").title() for f in flags[:2]]
        return f"Significant fund diversion signals — {', '.join(flag_names)}. Recommend end-use audit before disbursement."
