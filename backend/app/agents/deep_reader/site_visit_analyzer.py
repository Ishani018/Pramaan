"""
SiteVisitAnalyzer
=================
Analyzes free-text site visit / management meeting notes
from the credit officer. Extracts risk signals and fires
rules that adjust the final rate and limit.
Zero-LLM — pure keyword + pattern matching.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(f"pramaan.{__name__}")


@dataclass
class SiteVisitFinding:
    rule_id: str
    rule_name: str
    description: str
    matched_text: str
    severity: str        # HIGH / MEDIUM / LOW
    rate_penalty_bps: int
    limit_reduction_pct: int


@dataclass 
class SiteVisitResult:
    raw_notes: str
    findings: list[SiteVisitFinding] = field(
        default_factory=list)
    triggered_rules: list[str] = field(
        default_factory=list)
    total_penalty_bps: int = 0
    total_limit_reduction_pct: int = 0
    risk_summary: str = ""


# ── SIGNAL LIBRARY ─────────────────────────────────────
# Each signal has:
#   patterns   — list of regex to match in notes
#   rule_id    — P-XX identifier
#   rule_name  — short display name
#   desc       — explanation shown in UI/CAM
#   severity   — HIGH / MEDIUM / LOW
#   bps        — rate penalty in basis points
#   limit_pct  — limit reduction percentage

SITE_VISIT_SIGNALS = [
    {
        "patterns": [
            r'\b(\d{1,3})\s*%\s*capacity\b',
            r'operating\s+at\s+(\d{1,3})\s*(?:percent|%)',
            r'capacity\s+utilis?ation\s+(?:of\s+)?(\d{1,3})\s*(?:percent|%)',
            r'running\s+at\s+(\d{1,3})\s*%',
            r'plant\s+(?:is\s+)?(?:at|running)\s+(\d{1,3})\s*%',
        ],
        "threshold": 60,   # trigger if capacity < 60%
        "threshold_type": "below",
        "rule_id": "P-19",
        "rule_name": "SITE-01: Low Capacity Utilisation",
        "desc": "Factory/plant operating below 60% capacity — "
                "indicates weak demand or operational issues",
        "severity": "HIGH",
        "bps": 100,
        "limit_pct": 15,
    },
    {
        "patterns": [
            r'\bvacant\b',
            r'\bshut\s*down\b',
            r'\bclosed\b(?!\s+account)',
            r'\bnon.?operational\b',
            r'\bno\s+(?:activity|workers|production)\b',
            r'\bempty\s+(?:plant|factory|premises|floor)\b',
            r'\bpremises\s+(?:appear|found|seem)\s+'
            r'(?:vacant|empty|abandoned)\b',
        ],
        "threshold": None,
        "rule_id": "P-20",
        "rule_name": "SITE-02: Premises Vacant / Shut",
        "desc": "Physical premises found vacant, shut or "
                "non-operational during site visit",
        "severity": "HIGH",
        "bps": 150,
        "limit_pct": 25,
    },
    {
        "patterns": [
            r'\bworkers?\s+(?:on\s+strike|striking)\b',
            r'\blabou?r\s+dispute\b',
            r'\bunion\s+(?:dispute|strike|action)\b',
            r'\bstrike\b',
            r'\bwork\s*(?:ers?)?\s*stoppage\b',
        ],
        "threshold": None,
        "rule_id": "P-21",
        "rule_name": "SITE-03: Labour Dispute",
        "desc": "Active labour dispute or strike reported "
                "at site visit",
        "severity": "HIGH",
        "bps": 100,
        "limit_pct": 15,
    },
    {
        "patterns": [
            r'\bmanagement\s+(?:unavailable|absent|'
            r'refused|evasive|uncooperative)\b',
            r'\brefused\s+to\s+(?:meet|answer|provide|'
            r'show|disclose)\b',
            r'\bnot\s+(?:available|present|cooperative)\b',
            r'\bevasive\s+(?:on|about|regarding)\b',
            r'\bdid\s+not\s+(?:respond|cooperate|allow)\b',
        ],
        "threshold": None,
        "rule_id": "P-22",
        "rule_name": "SITE-04: Management Non-Cooperative",
        "desc": "Management was unavailable, evasive or "
                "refused to cooperate during due diligence",
        "severity": "HIGH",
        "bps": 125,
        "limit_pct": 20,
    },
    {
        "patterns": [
            r'\binventory\s+(?:piled|excess|overstocked|'
            r'accumulate|bloated)\b',
            r'\bexcess\s+(?:stock|inventory)\b',
            r'\bstock\s+(?:piling|pile.?up|accumulation)\b',
            r'\bwarehouses?\s+(?:full|overflow|packed)\b',
            r'\bunsold\s+(?:goods|stock|inventory)\b',
        ],
        "threshold": None,
        "rule_id": "P-23",
        "rule_name": "SITE-05: Inventory Build-up",
        "desc": "Excess / unsold inventory observed — "
                "possible demand slowdown or cash flow stress",
        "severity": "MEDIUM",
        "bps": 50,
        "limit_pct": 10,
    },
    {
        "patterns": [
            r'\bmachinery\s+(?:old|outdated|obsolete|'
            r'worn|rusted|broken|not\s+maintained)\b',
            r'\bequipment\s+(?:poor|bad|deteriorat|'
            r'obsolete|aged)\b',
            r'\bpoor\s+(?:maintenance|upkeep|condition)\b',
            r'\bfixed\s+assets?\s+(?:deteriorat|worn|old)\b',
            r'\binfrastructure\s+(?:poor|bad|deteriorat)\b',
        ],
        "threshold": None,
        "rule_id": "P-24",
        "rule_name": "SITE-06: Poor Asset Condition",
        "desc": "Machinery / equipment found in poor or "
                "deteriorating condition during site visit",
        "severity": "MEDIUM",
        "bps": 50,
        "limit_pct": 10,
    },
    {
        "patterns": [
            r'\bkey\s+(?:person|man|management)\s+'
            r'(?:risk|dependency|dependent)\b',
            r'\bentire(?:ly)?\s+(?:dependent|run)\s+by\s+'
            r'(?:one|single|1)\s+(?:person|promoter|'
            r'individual)\b',
            r'\bno\s+second\s+(?:line|tier)\s+(?:of\s+)?'
            r'management\b',
            r'\bsole\s+decision\s+maker\b',
        ],
        "threshold": None,
        "rule_id": "P-25",
        "rule_name": "SITE-07: Key Man Risk",
        "desc": "Business appears entirely dependent on "
                "single promoter / individual — key man risk",
        "severity": "MEDIUM",
        "bps": 50,
        "limit_pct": 5,
    },
    {
        "patterns": [
            r'\bbooks?\s+(?:not\s+)?(?:maintained|updated|'
            r'available|produced)\b',
            r'\brecords?\s+(?:not\s+)?(?:maintained|'
            r'available|produced|incomplete)\b',
            r'\bno\s+(?:books|accounts?|records?)\b',
            r'\baccounts?\s+(?:not\s+maintained|incomplete|'
            r'not\s+available)\b',
        ],
        "threshold": None,
        "rule_id": "P-26",
        "rule_name": "SITE-08: Records Not Maintained",
        "desc": "Books of accounts or business records "
                "not maintained or made available",
        "severity": "HIGH",
        "bps": 100,
        "limit_pct": 20,
    },
]


class SiteVisitAnalyzer:

    def analyze(self, notes: str) -> SiteVisitResult:
        """
        Analyze free-text site visit notes.
        Returns SiteVisitResult with triggered rules
        and total penalties.
        """
        if not notes or not notes.strip():
            logger.info(
                "SiteVisitAnalyzer: no notes provided")
            return SiteVisitResult(raw_notes="")

        result = SiteVisitResult(raw_notes=notes)
        notes_lower = notes.lower()

        for signal in SITE_VISIT_SIGNALS:
            matched_text = None
            matched_value = None

            for pattern in signal["patterns"]:
                m = re.search(
                    pattern, notes_lower, re.IGNORECASE)
                if m:
                    matched_text = notes[
                        max(0, m.start()-20):
                        m.end()+20].strip()

                    # For capacity signals, extract %
                    if signal.get("threshold") is not None:
                        try:
                            matched_value = float(
                                m.group(1))
                        except (IndexError, ValueError):
                            matched_value = 0
                    break

            if not matched_text:
                continue

            # Check threshold if applicable
            if signal.get("threshold") is not None:
                if signal["threshold_type"] == "below":
                    if (matched_value is None or
                            matched_value >= 
                            signal["threshold"]):
                        # Capacity >= 60% is fine
                        continue
                    # Capacity < 60% — fire rule
                    desc = (
                        f"Factory operating at "
                        f"{matched_value:.0f}% capacity "
                        f"(threshold: <{signal['threshold']}%)")
                else:
                    continue

            finding = SiteVisitFinding(
                rule_id=signal["rule_id"],
                rule_name=signal["rule_name"],
                description=(
                    signal["desc"] if not matched_value
                    else (
                        f"Factory operating at "
                        f"{matched_value:.0f}% capacity — "
                        f"below {signal['threshold']}% threshold"
                    )
                ),
                matched_text=matched_text,
                severity=signal["severity"],
                rate_penalty_bps=signal["bps"],
                limit_reduction_pct=signal["limit_pct"],
            )

            result.findings.append(finding)
            result.triggered_rules.append(
                signal["rule_id"])
            result.total_penalty_bps += signal["bps"]
            result.total_limit_reduction_pct += (
                signal["limit_pct"])

            logger.warning(
                f"SiteVisitAnalyzer: "
                f"{signal['rule_id']} TRIGGERED — "
                f"{signal['rule_name']} | "
                f"+{signal['bps']}bps | "
                f"matched: '{matched_text}'")

        # Build risk summary
        if result.findings:
            high = [f for f in result.findings
                    if f.severity == "HIGH"]
            med  = [f for f in result.findings
                    if f.severity == "MEDIUM"]
            result.risk_summary = (
                f"{len(result.findings)} site visit risk(s) "
                f"detected — {len(high)} HIGH, {len(med)} MEDIUM. "
                f"Total additional penalty: "
                f"+{result.total_penalty_bps}bps, "
                f"limit reduction: "
                f"-{result.total_limit_reduction_pct}%"
            )
        else:
            result.risk_summary = (
                "No risk signals detected in site visit notes")

        logger.info(
            f"SiteVisitAnalyzer: "
            f"{len(result.findings)} findings, "
            f"rules={result.triggered_rules}, "
            f"penalty={result.total_penalty_bps}bps")

        return result
