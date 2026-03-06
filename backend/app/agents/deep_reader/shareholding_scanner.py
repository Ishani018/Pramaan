"""
Shareholding Pattern Scanner — Zero LLM
========================================
Extracts promoter holding %, pledged shares %,
and FII/DII holding from annual report text.
Flags high pledge as early warning signal.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

@dataclass
class ShareholdingResult:
    promoter_holding_pct: Optional[float] = None
    pledged_pct: Optional[float] = None
    fii_holding_pct: Optional[float] = None
    dii_holding_pct: Optional[float] = None
    public_holding_pct: Optional[float] = None
    government_holding_pct: Optional[float] = None
    triggered_rules: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    source: str = "Annual Report — Shareholding Pattern"

PROMOTER_PATTERNS = [
    r'promoter[s]?\s+(?:and\s+promoter\s+group\s+)?holding[:\s]+(\d+\.?\d*)\s*%',
    r'promoter[s]?\s+(?:and\s+promoter\s+group\s+)?[\s\S]{0,30}?(\d+\.?\d*)\s*%',
    r'(\d+\.?\d*)\s*%[\s\S]{0,30}?held\s+by\s+promoter',
    r'promoter\s+shareholding[\s\S]{0,50}?(\d+\.?\d*)\s*%',
    r'promoters\s+hold[\s\S]{0,30}?(\d+\.?\d*)\s*%',
    r'promoter[s]?[\s\S]{0,100}?(\d+\.\d+)[\s\S]{0,20}?(\d+\.\d+)[\s\S]{0,20}?(\d+\.\d+)',
    r'(?:a\)|1\))\s*promoter[\s\S]{0,200}?(\d{1,2}\.\d{2})',
    r'49[\s\S]{0,50}?percent\s+equity\s+stake',
]

PLEDGE_PATTERNS = [
    r'pledged[\s\S]{0,50}?(\d+\.?\d*)\s*%',
    r'(\d+\.?\d*)\s*%[\s\S]{0,30}?pledged',
    r'pledge[d]?\s+shares[\s\S]{0,50}?(\d+\.?\d*)\s*%',
    r'encumbered[\s\S]{0,50}?(\d+\.?\d*)\s*%',
]

FII_PATTERNS = [
    r'foreign\s+institutional\s+investor[s]?[\s\S]{0,50}?(\d+\.?\d*)\s*%',
    r'fii[s]?[\s\S]{0,50}?(\d+\.?\d*)\s*%',
    r'foreign\s+portfolio\s+investor[s]?[\s\S]{0,50}?(\d+\.?\d*)\s*%',
    r'fpi[s]?[\s\S]{0,50}?(\d+\.?\d*)\s*%',
]

GOVT_PATTERNS = [
    r'government[\s\S]{0,50}?(\d+\.?\d*)\s*%',
    r'central\s+government[\s\S]{0,50}?(\d+\.?\d*)\s*%',
    r'state\s+government[\s\S]{0,50}?(\d+\.?\d*)\s*%',
    r'president\s+of\s+india[\s\S]{0,50}?(\d+\.?\d*)\s*%',
]

def _extract_pct(text: str, patterns: List[str]) -> Optional[float]:
    """Try each pattern, return first valid percentage found."""
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                val = float(match)
                if 0.1 <= val <= 100:
                    return round(val, 2)
            except ValueError:
                continue
    return None


class ShareholdingScanner:

    def scan(self, full_text: str) -> ShareholdingResult:
        result = ShareholdingResult()

        # Focus on shareholding section only
        text_lower = full_text.lower()
        
        # Try multiple marker variations, 
        # pick the one with actual percentage data

        search_markers = [
            "statement showing shareholding pattern",
            "shareholding pattern as on",
            "category of shareholders",
            "promoter and promoter group",
            "table i - summary statement",
        ]

        section_text = full_text  # fallback

        for marker in search_markers:
            idx = text_lower.find(marker)
            if idx != -1:
                candidate = full_text[idx:idx+8000]
                # Verify this section has actual % numbers
                if re.search(r'\d+\.\d{2}', candidate):
                    section_text = candidate
                    logger.info(
                        f"ShareholdingScanner: "
                        f"found section at '{marker}' "
                        f"idx={idx}, "
                        f"sample='{candidate[:200]}'")
                    break

        # Extract all metrics
        result.promoter_holding_pct = _extract_pct(
            section_text, PROMOTER_PATTERNS)
        result.pledged_pct = _extract_pct(
            section_text, PLEDGE_PATTERNS)
        result.fii_holding_pct = _extract_pct(
            section_text, FII_PATTERNS)
        result.government_holding_pct = _extract_pct(
            section_text, GOVT_PATTERNS)

        # Trigger rules based on findings
        
        # P-17: High pledge ratio
        if (result.pledged_pct is not None 
                and result.pledged_pct > 50):
            result.triggered_rules.append("P-17")
            result.findings.append(
                f"High promoter pledge: {result.pledged_pct}% "
                f"of promoter shares pledged")
            logger.warning(
                f"P-17 TRIGGERED: pledge={result.pledged_pct}%")

        # P-18: Very low promoter holding
        if (result.promoter_holding_pct is not None 
                and result.promoter_holding_pct < 26):
            result.triggered_rules.append("P-18")
            result.findings.append(
                f"Low promoter holding: {result.promoter_holding_pct}% "
                f"(below 26% threshold)")
            logger.warning(
                f"P-18 TRIGGERED: promoter={result.promoter_holding_pct}%")

        logger.info(
            f"ShareholdingScanner: "
            f"promoter={result.promoter_holding_pct}%, "
            f"pledged={result.pledged_pct}%, "
            f"fii={result.fii_holding_pct}%, "
            f"govt={result.government_holding_pct}%, "
            f"rules={result.triggered_rules}")

        return result
