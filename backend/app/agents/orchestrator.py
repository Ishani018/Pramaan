"""
Credit Decision Orchestrator
==============================
Deterministic penalty accumulator that aggregates signals from:
  - ComplianceScanner (PDF auditor scan) → P-03
  - Perfios mock data                    → P-01
  - Karza mock data                      → watch flag only (no auto-penalty)

Returns a unified decision dict compatible with the frontend Waterfall Chart.
"""
from typing import Any, Dict, List

BASE_RATE_PCT  = 9.0
BASE_LIMIT_CR  = 10.0

# Rule definitions — single source of truth used by both backend and CAM generator
RULE_DEFINITIONS = {
    "P-01": {
        "name": "Ghost Input Trap",
        "trigger_description": "GSTR-2A vs 3B mismatch > 15% (Perfios)",
        "rate_penalty_bps": 100,
        "limit_reduction_pct": 10,
        "requires_manual_review": False,
    },
    "P-02": {
        "name": "Hidden Family Web",
        "trigger_description": "RPT outflows to director-connected entities (manual)",
        "rate_penalty_bps": 75,
        "limit_reduction_pct": 10,
        "requires_manual_review": True,
    },
    "P-03": {
        "name": "Statutory Default / Auditor Qualification",
        "trigger_description": "CARO 2020 Clause (vii) default or qualified/adverse auditor opinion",
        "rate_penalty_bps": 150,
        "limit_reduction_pct": 20,
        "requires_manual_review": False,
    },
    "P-04": {
        "name": "Emphasis of Matter / Going Concern",
        "trigger_description": "Auditor flagged going concern or material uncertainty",
        "rate_penalty_bps": 75,
        "limit_reduction_pct": 0,
        "requires_manual_review": True,
    },
    "P-07": {
        "name": "PRIMARY-01: Site Visit Risk",
        "trigger_description": "Adverse observations from factory visit or management interview",
        "rate_penalty_bps": 75,
        "limit_reduction_pct": 10,
        "requires_manual_review": True,
        "severity": "HIGH"
    },
    "P-09": {
        "name": "Financial Restatement",
        "trigger_description": "Prior year financial comparative figures restated by >2%",
        "rate_penalty_bps": 200,
        "limit_reduction_pct": 40,
        "requires_manual_review": True,
        "severity": "CRITICAL",
    },
    "P-14": {
        "name": "CORP-01: Company Not Active",
        "trigger_description": "MCA21 shows company struck off or under liquidation",
        "rate_penalty_bps": 0,
        "limit_reduction_pct": 100,
        "requires_manual_review": True,
        "severity": "CRITICAL"
    },
    "P-10": {
        "name": "Auditor Rotation / Change",
        "trigger_description": "Change in statutory auditor detected across reporting periods",
        "rate_penalty_bps": 75,
        "limit_reduction_pct": 10,
        "requires_manual_review": True,
        "severity": "HIGH",
    },
    "P-13": {
        "name": "Adverse Media Detected",
        "trigger_description": "NewsScanner found high-severity red flags (fraud, ED raid, etc.)",
        "rate_penalty_bps": 50,
        "limit_reduction_pct": 0,
        "requires_manual_review": True,
    },
    "P-16": {
        "name": "MGMT-01: Negative Management Sentiment",
        "trigger_description": "MD&A sentiment score negative per Loughran-McDonald lexicon analysis",
        "rate_penalty_bps": 50,
        "limit_reduction_pct": 5,
        "requires_manual_review": False,
        "severity": "MEDIUM"
    },
    "P-15": {
        "name": "LEGAL-01: Active Court Proceedings",
        "trigger_description": "High-risk court cases found via eCourts public API (NCLT/winding up/fraud/DRT)",
        "rate_penalty_bps": 100,
        "limit_reduction_pct": 15,
        "requires_manual_review": True,
        "severity": "HIGH"
    },
}


def orchestrate_decision(
    pdf_scan_result: Dict[str, Any] | None,
    perfios_data: Dict[str, Any] | None,
    karza_data: Dict[str, Any] | None,
    restatement_data: Dict[str, Any] | None = None,
    news_data: Dict[str, Any] | None = None,
    site_visit_scan: Dict[str, Any] | None = None,
    mca_data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Aggregate all signals and compute the final credit decision.

    Args:
        pdf_scan_result: Response from ComplianceScanner / analyze-report
        perfios_data:    Response from GET /mock/perfios
        karza_data:      Response from GET /mock/karza
        restatement_data: Response from RestatementDetector (P-09, P-10)
        news_data:       Response from NewsScanner (P-13)
        site_visit_scan: Response from SiteVisitScanner (P-07)

    Returns:
        Unified decision dict:
          {
            base_rate_pct, final_rate_pct,
            base_limit_cr, final_limit_cr,
            recommendation, applied_penalties,
            triggered_rules, requires_manual_review
          }
    """
    triggered: List[str] = []

    # ── P-01: Ghost Input Trap (Perfios) ─────────────────────────────────────
    if perfios_data and perfios_data.get("status") == "success":
        mismatch = perfios_data.get("gstr_2a_3b_mismatch_pct", 0)
        if mismatch > 15:
            triggered.append("P-01")

    # ── P-03: Statutory Default / Auditor Qualification (PDF scan) ───────────
    if pdf_scan_result:
        if pdf_scan_result.get("caro_default_found") or pdf_scan_result.get("adverse_opinion_found"):
            if "P-03" not in triggered:
                triggered.append("P-03")

        # ── P-04: Emphasis of Matter (PDF scan) ──────────────────────────────
        if pdf_scan_result.get("emphasis_of_matter_found"):
            if "P-04" not in triggered:
                triggered.append("P-04")

    if restatement_data:
        if restatement_data.get("restatements_detected"):
            if "P-09" not in triggered:
                triggered.append("P-09")
        if restatement_data.get("auditor_changed"):
            if "P-10" not in triggered:
                triggered.append("P-10")

    # ── P-13: Adverse Media Detected ─────────────────────────────────────────
    if news_data and news_data.get("adverse_media_detected"):
        if "P-13" not in triggered:
            triggered.append("P-13")

    # ── P-07: Site Visit Scans ────────────────────────────────────────────────
    if site_visit_scan and site_visit_scan.get("triggered_rules"):
        for rule in site_visit_scan["triggered_rules"]:
            if rule not in triggered:
                triggered.append(rule)

    # ── P-14: MCA Scanner ─────────────────────────────────────────────────────
    if mca_data and mca_data.get("triggered_rules"):
        for rule in mca_data["triggered_rules"]:
            if rule not in triggered:
                triggered.append(rule)

    # ── Apply penalties ───────────────────────────────────────────────────────
    rate  = BASE_RATE_PCT
    limit = BASE_LIMIT_CR
    applied: List[Dict] = []
    manual_review = False

    for rule_id in triggered:
        rule = RULE_DEFINITIONS.get(rule_id)
        if not rule:
            continue
        bps      = rule["rate_penalty_bps"]
        cut_pct  = rule["limit_reduction_pct"]
        rate    += bps / 100
        limit    = limit * (1 - cut_pct / 100)
        applied.append({
            "rule_id":             rule_id,
            "name":                rule["name"],
            "trigger":             rule["trigger_description"],
            "rate_penalty_bps":    bps,
            "limit_reduction_pct": cut_pct,
        })
        if rule.get("requires_manual_review"):
            manual_review = True

    if manual_review:
        recommendation = "MANUAL_REVIEW"
    elif triggered:
        recommendation = "CONDITIONAL_APPROVAL"
    else:
        recommendation = "APPROVE"

    return {
        "base_rate_pct":       BASE_RATE_PCT,
        "final_rate_pct":      round(rate, 2),
        "base_limit_cr":       BASE_LIMIT_CR,
        "final_limit_cr":      round(limit, 2),
        "recommendation":      recommendation,
        "applied_penalties":   applied,
        "triggered_rules":     triggered,
        "requires_manual_review": manual_review,
        # Karza watch note (not a penalty, but surfaced in decision output)
        "karza_watch": (
            karza_data.get("metadata", {}).get("watch_flag")
            if karza_data else None
        ),
    }

# ---------------------------------------------------------------------------
# Decision Narrative Generator
# ---------------------------------------------------------------------------
def generate_decision_narrative(
    decision: Dict[str, Any],
    triggered_rules: List[str],
    pdf_scan: Dict[str, Any] | None = None,
    perfios_data: Dict[str, Any] | None = None,
    restatement_data: Dict[str, Any] | None = None,
    news_data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Produce a plain-English, step-by-step narrative explaining the credit
    decision.  Each step shows what was found, which rule fired, and the
    penalty applied.

    Args:
        decision:        The dict returned by orchestrate_decision()
        triggered_rules: List of triggered rule IDs (e.g. ["P-01", "P-03"])
        pdf_scan:        Response from ComplianceScanner / analyze-report
        perfios_data:    Response from GET /mock/perfios

    Returns:
        {
          "narrative": "Step 1: … Step 2: … Final Decision: …",
          "steps":     [ { "step": 1, "description": "…" }, … ]
        }
    """
    steps: List[Dict[str, Any]] = []
    lines: List[str] = []

    # ── Step 1 is always the baseline ────────────────────────────────────────
    step_num = 1
    base_desc = (
        f"Base rate set at {BASE_RATE_PCT}% (repo rate + bank spread). "
        f"Base limit set at ₹{BASE_LIMIT_CR} Cr."
    )
    steps.append({"step": step_num, "description": base_desc})
    lines.append(f"Step {step_num}: {base_desc}")

    # ── One step per triggered rule ──────────────────────────────────────────
    running_rate = BASE_RATE_PCT
    running_limit = BASE_LIMIT_CR

    for rule_id in triggered_rules:
        rule = RULE_DEFINITIONS.get(rule_id)
        if not rule:
            continue

        step_num += 1
        bps = rule["rate_penalty_bps"]
        cut_pct = rule["limit_reduction_pct"]

        # Build a specific "what was found" string
        finding = _describe_finding(rule_id, pdf_scan, perfios_data, restatement_data, news_data)

        # Apply penalty
        running_rate += bps / 100
        running_limit = running_limit * (1 - cut_pct / 100)

        # Build penalty description
        penalty_parts: List[str] = []
        if bps > 0:
            penalty_parts.append(f"+{bps} bps to rate (now {running_rate:.1f}%)")
        if cut_pct > 0:
            penalty_parts.append(
                f"−{cut_pct}% limit cut (now ₹{running_limit:.2f} Cr)"
            )
        penalty_str = "; ".join(penalty_parts) if penalty_parts else "no auto-penalty"

        desc = f"{rule['name']} — {finding} → {penalty_str}."
        steps.append({"step": step_num, "description": desc})
        lines.append(f"Step {step_num}: {desc}")

    # ── Final Decision step ──────────────────────────────────────────────────
    final_rate = decision.get("final_rate_pct", running_rate)
    final_limit = decision.get("final_limit_cr", running_limit)
    reco = decision.get("recommendation", "N/A")

    final_desc = f"Rate {final_rate}% | Limit ₹{final_limit} Cr | {reco}"
    lines.append(f"Final Decision: {final_desc}")
    steps.append({"step": step_num + 1, "description": f"Final Decision: {final_desc}"})

    return {
        "narrative": "\n".join(lines),
        "steps": steps,
    }


def _describe_finding(
    rule_id: str,
    pdf_scan: Dict[str, Any] | None,
    perfios_data: Dict[str, Any] | None,
    restatement_data: Dict[str, Any] | None = None,
    news_data: Dict[str, Any] | None = None,
) -> str:
    """Return a human-readable description of what triggered a specific rule."""

    if rule_id == "P-01" and perfios_data:
        mismatch = perfios_data.get("gstr_2a_3b_mismatch_pct", "N/A")
        return f"GSTR-2A vs 3B mismatch at {mismatch}% (threshold: 15%)"

    if rule_id == "P-03" and pdf_scan:
        parts = []
        if pdf_scan.get("caro_default_found"):
            parts.append("CARO 2020 statutory default detected")
        if pdf_scan.get("adverse_opinion_found"):
            parts.append("adverse/qualified auditor opinion found")
        return " and ".join(parts) if parts else "statutory default or qualification detected"

    if rule_id == "P-04" and pdf_scan:
        return "auditor flagged going concern / material uncertainty in Emphasis of Matter paragraph"

    if rule_id == "P-09" and restatement_data:
        restatements = restatement_data.get("restatements", [])
        if restatements:
            first = restatements[0]
            return f"{first['figure']} restated by {first['change_pct']}% in {first['year_restated']} comparative"
        return "prior year financial figures restated"

    if rule_id == "P-10" and restatement_data:
        history = restatement_data.get("auditor_history", {})
        return f"auditor changed across reporting periods (history: {list(history.values())})"

    if rule_id == "P-02":
        return "related-party outflows to director-connected entities flagged"

    if rule_id == "P-13" and news_data:
        flags = [rf["headline"] for rf in news_data.get("red_flags", []) if rf.get("severity") == "HIGH"]
        if flags:
            return f"adverse media detected: {flags[0]}"
        return "adverse media detected based on company name search"

    # Fallback: use the trigger_description from RULE_DEFINITIONS
    rule = RULE_DEFINITIONS.get(rule_id)
    return rule["trigger_description"] if rule else "unknown trigger"
