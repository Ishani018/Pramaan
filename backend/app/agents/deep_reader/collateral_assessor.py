"""
Collateral Assessor
===================
Scans annual report text (specifically notes on borrowings) to 
determine the collateral/security cover for loans.
Detects unencumbered assets, first charges, and unsecured loans.
Triggers P-31 if major borrowings are unsecured.

Zero-LLM — regex-based extraction.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(f"pramaan.{__name__}")

@dataclass
class CollateralFinding:
    asset_type: str
    security_type: str  # e.g., "First Charge", "Unsecured"
    snippet: str

@dataclass
class CollateralResult:
    findings: List[CollateralFinding] = field(default_factory=list)
    has_unsecured_loans: bool = False
    is_fully_secured: bool = False
    triggered_rules: List[str] = field(default_factory=list)
    summary: str = ""

class CollateralAssessor:
    """Extract collateral details from text."""

    # Patterns to look for security types
    SECURED_PATTERN = re.compile(
        r'((first|second|exclusive|pari[- ]passu|hypothecation|charge|pledge)[^.]{0,80}(fixed assets|inventory|receivables|current assets|property|plant|machinery))',
        re.IGNORECASE
    )
    
    UNSECURED_PATTERN = re.compile(
        r'(unsecured\s+(?:loans|borrowings|debentures|facilities))',
        re.IGNORECASE
    )

    def analyze(self, full_text: str) -> CollateralResult:
        result = CollateralResult()
        if not full_text:
            return result

        # Limit to reasonable length if too large, usually found in "Borrowings" notes
        search_text = full_text

        # 1. Look for Unsecured Loans
        unsecured_matches = list(self.UNSECURED_PATTERN.finditer(search_text))
        if unsecured_matches:
            result.has_unsecured_loans = True
            for m in unsecured_matches[:2]:  # cap at 2
                ctx_start = max(0, m.start() - 30)
                ctx_end = min(len(search_text), m.end() + 80)
                result.findings.append(CollateralFinding(
                    asset_type="N/A",
                    security_type="Unsecured",
                    snippet=search_text[ctx_start:ctx_end].strip()
                ))

        # 2. Look for Secured Loans
        secured_matches = list(self.SECURED_PATTERN.finditer(search_text))
        if secured_matches:
            result.is_fully_secured = not result.has_unsecured_loans
            for m in secured_matches[:3]:  # cap at 3
                ctx_start = max(0, m.start() - 30)
                ctx_end = min(len(search_text), m.end() + 80)
                security = m.group(2).title() if m.group(2) else "Charge"
                asset = m.group(3).title() if m.group(3) else "Assets"
                result.findings.append(CollateralFinding(
                    asset_type=asset,
                    security_type=security,
                    snippet=search_text[ctx_start:ctx_end].strip()
                ))

        if not result.findings:
            result.summary = "No explicit collateral details found in text."
        elif result.has_unsecured_loans:
            result.summary = "Significant unsecured borrowings detected."
            result.triggered_rules.append("P-31")
            logger.warning(f"CollateralAssessor: P-31 TRIGGERED — {result.summary}")
        else:
            result.summary = "Borrowings appear predominantly secured."

        return result
