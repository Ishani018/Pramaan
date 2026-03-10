"""
Claims Extractor
=================
Compiles structured "claims" from the annual report extraction results.
Each claim represents something the annual report asserts (revenue, no defaults,
healthy operations, etc.) that can later be cross-verified against external sources.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def extract_claims(
    extracted_figures: Dict[str, Any],
    scan_dict: Dict[str, Any],
    shareholding_data: Optional[Any] = None,
    rating_result: Optional[Any] = None,
    mda_insights: Optional[Dict[str, Any]] = None,
    restatement_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Extract structured claims from annual report analysis results.

    Returns a dict keyed by claim_id, each with:
      - claim: human-readable claim text
      - value / clean / relevant numeric data
      - source: where in the AR this was found
      - confidence: HIGH / MEDIUM / LOW
    """
    claims: Dict[str, Dict[str, Any]] = {}

    # ── Revenue claim ───────────────────────────────────────────────────────
    revenue = (
        extracted_figures.get("Revenue", {}).get("value") or
        extracted_figures.get("revenue") or 
        extracted_figures.get("revenue_cr")
    )
    if revenue and revenue > 0:
        claims["revenue"] = {
            "claim": f"Revenue from operations: {revenue:,.1f} Cr",
            "value": float(revenue),
            "unit": "Cr",
            "source": "Annual Report - Profit & Loss Statement",
            "confidence": "HIGH",
        }
    else:
        claims["revenue"] = {
            "claim": "Revenue figure not extracted from annual report",
            "value": 0,
            "unit": "Cr",
            "source": "Annual Report",
            "confidence": "LOW",
        }

    # ── Profitability claim ─────────────────────────────────────────────────
    ebitda = (
        extracted_figures.get("EBITDA", {}).get("value") or 
        extracted_figures.get("ebitda") or 
        extracted_figures.get("ebitda_cr")
    )
    pat = (
        extracted_figures.get("PAT", {}).get("value") or 
        extracted_figures.get("pat") or 
        extracted_figures.get("net_profit") or 
        extracted_figures.get("pat_cr")
    )
    if ebitda or pat:
        parts = []
        if ebitda:
            parts.append(f"EBITDA {ebitda:,.1f} Cr")
        if pat:
            parts.append(f"PAT {pat:,.1f} Cr")
        claims["profitability"] = {
            "claim": f"Reported profitability: {', '.join(parts)}",
            "ebitda_value": float(ebitda) if ebitda else None,
            "pat_value": float(pat) if pat else None,
            "unit": "Cr",
            "source": "Annual Report - Profit & Loss Statement",
            "confidence": "HIGH" if ebitda and pat else "MEDIUM",
        }

    # ── No statutory defaults claim ─────────────────────────────────────────
    caro_found = scan_dict.get("caro_default_found", False)
    adverse_found = scan_dict.get("adverse_opinion_found", False)
    claims["no_statutory_defaults"] = {
        "claim": "CARO defaults / auditor qualification detected" if (caro_found or adverse_found)
                 else "No statutory defaults or auditor qualifications detected",
        "clean": not (caro_found or adverse_found),
        "caro_default_found": caro_found,
        "adverse_opinion_found": adverse_found,
        "source": "Annual Report - Auditor's Report",
        "confidence": "HIGH",
    }

    # ── Going concern claim ─────────────────────────────────────────────────
    eom_found = scan_dict.get("emphasis_of_matter_found", False)
    claims["going_concern"] = {
        "claim": "Going concern / emphasis of matter flagged by auditor" if eom_found
                 else "No going concern issues raised by auditor",
        "clean": not eom_found,
        "emphasis_of_matter_found": eom_found,
        "source": "Annual Report - Auditor's Report",
        "confidence": "HIGH",
    }

    # ── Promoter stability claim ────────────────────────────────────────────
    if shareholding_data:
        holding = getattr(shareholding_data, "promoter_holding_pct", None) or 0
        pledged = getattr(shareholding_data, "pledged_pct", None) or 0
        claims["promoter_stability"] = {
            "claim": f"Promoter holding at {holding:.1f}%, pledged {pledged:.1f}%",
            "holding_pct": float(holding),
            "pledged_pct": float(pledged),
            "source": "Annual Report - Shareholding Pattern",
            "confidence": "HIGH" if holding > 0 else "LOW",
        }

    # ── Credit rating claim ─────────────────────────────────────────────────
    if rating_result:
        rating = getattr(rating_result, "latest_rating", None)
        agency = getattr(rating_result, "latest_agency", None)
        inv_grade = getattr(rating_result, "is_investment_grade", None)
        downgrade = getattr(rating_result, "downgrade_detected", False)
        if rating:
            claims["credit_rating"] = {
                "claim": f"Rated {rating} by {agency or 'rating agency'}"
                         + (", investment grade" if inv_grade else ", sub-investment grade")
                         + (" (DOWNGRADE DETECTED)" if downgrade else ""),
                "rating": rating,
                "agency": agency,
                "is_investment_grade": inv_grade,
                "downgrade_detected": downgrade,
                "source": "Annual Report - Rating Disclosures",
                "confidence": "HIGH",
            }

    # ── Litigation status claim ─────────────────────────────────────────────
    # If no CARO defaults and no adverse opinion, the AR implicitly claims clean litigation
    claims["litigation_status"] = {
        "claim": "Auditor report does not flag material litigation"
                 if not caro_found else "Auditor report flags statutory issues",
        "clean": not caro_found,
        "source": "Annual Report - Auditor's Report / Notes to Accounts",
        "confidence": "MEDIUM",
    }

    # ── Management outlook claim ────────────────────────────────────────────
    if mda_insights and mda_insights.get("status") == "success":
        sentiment = mda_insights.get("sentiment_score", 0)
        label = "positive" if sentiment > 0.02 else ("negative" if sentiment < -0.02 else "neutral")
        claims["management_outlook"] = {
            "claim": f"Management outlook {label} (sentiment score: {sentiment:+.3f})",
            "sentiment_score": sentiment,
            "sentiment_label": label,
            "source": "Annual Report - Management Discussion & Analysis",
            "confidence": "MEDIUM",
        }

    # ── Financial consistency claim ─────────────────────────────────────────
    if restatement_data:
        restated = restatement_data.get("restatements_detected", False)
        auditor_changed = restatement_data.get("auditor_changed", False)
        claims["financial_consistency"] = {
            "claim": ("Prior year figures restated" if restated else "No prior year restatements")
                     + ("; auditor changed" if auditor_changed else ""),
            "restated": restated,
            "auditor_changed": auditor_changed,
            "source": "Annual Report - Multi-Year Comparison",
            "confidence": "HIGH" if not restated else "MEDIUM",
        }

    logger.info(f"Extracted {len(claims)} claims from annual report")
    return claims
