"""
Deep Reader Agent – Compliance Scanner
=======================================
Deterministic, zero-LLM regex scanner for credit risk signals in auditor text.

Scans the extracted text of the Independent Auditor's Report and its Annexure for:
  1. CARO 2020 Clause (vii) – statutory defaults (PF, ESI, TDS, GST, Custom Duties, etc.)
  2. Auditor qualifications – "Except for", "Adverse opinion", "Qualified opinion"
  3. Emphasis of Matter paragraphs – softer risk signals requiring manual review

Every match returns the surrounding context snippet (±200 chars) for full traceability.
The scanner never invents findings — it only reports what is explicitly stated.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Regex patterns  (compiled at import time for performance)
# ---------------------------------------------------------------------------

# CARO 2020 patterns
_CARO_PATTERNS = [
    # Explicit CARO 2020 + clause (vii) reference
    re.compile(
        r"(?i)(caro[\s,\-]*2020[\s\S]{0,200}?clause[\s\-]*\(?\s*vii\s*\)?|"
        r"clause[\s\-]*\(?\s*vii\s*\)?[\s\S]{0,200}?caro[\s,\-]*2020)"
    ),
    # Statutory dues overdue + amount
    re.compile(
        r"(?i)(statutory\s+dues[\s\S]{0,200}?(?:not\s+deposited|outstanding|overdue|arrear|default)|"
        r"(?:provident\s+fund|pf|esi|tds|gst|custom\s+dut|income[\s-]tax|service\s+tax)[\s\S]{0,150}?"
        r"(?:not\s+deposited|arrear|default|overdue|outstanding))"
    ),
    # "Amounts not deposited on account of …"
    re.compile(
        r"(?i)(amounts?\s+(?:not\s+)?deposited[\s\S]{0,200}?(?:pf|esi|tds|gst|income.tax|custom))"
    ),
]

# Auditor qualification patterns
_QUALIFICATION_PATTERNS = [
    re.compile(r"(?i)except\s+for[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL),
    re.compile(r"(?i)adverse\s+opinion[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL),
    re.compile(r"(?i)qualified\s+opinion[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL),
    re.compile(r"(?i)disclaimer\s+of\s+opinion[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL),
]

# Emphasis of Matter (softer signal)
_EMPHASIS_PATTERNS = [
    re.compile(r"(?i)emphasis\s+of\s+matter[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL),
    re.compile(r"(?i)material\s+uncertainty[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL),
    re.compile(r"(?i)going[\s-]+concern[\s\S]{0,300}?(?=\n\n|\Z)", re.DOTALL),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ComplianceMatch:
    pattern_name: str
    snippet: str        # excerpt ±200 chars around the match
    start_char: int
    end_char: int


@dataclass
class ComplianceScanResult:
    # Primary boolean flags (wired into Rule Engine)
    caro_default_found: bool = False
    adverse_opinion_found: bool = False
    emphasis_of_matter_found: bool = False

    # Detailed matches for full traceability
    caro_matches: List[ComplianceMatch] = field(default_factory=list)
    qualification_matches: List[ComplianceMatch] = field(default_factory=list)
    emphasis_matches: List[ComplianceMatch] = field(default_factory=list)

    # Penalty signals (used by Rule Engine)
    triggered_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            # ── Boolean flags ──────────────────────────────────────────────
            "caro_default_found": self.caro_default_found,
            "adverse_opinion_found": self.adverse_opinion_found,
            "emphasis_of_matter_found": self.emphasis_of_matter_found,

            # ── Triggered penalty rules ────────────────────────────────────
            "triggered_rules": self.triggered_rules,

            # ── CARO 2020 matches ──────────────────────────────────────────
            "caro_findings": [
                {"pattern": m.pattern_name, "snippet": m.snippet}
                for m in self.caro_matches
            ],

            # ── Auditor qualification matches ──────────────────────────────
            "auditor_qualification_findings": [
                {"pattern": m.pattern_name, "snippet": m.snippet}
                for m in self.qualification_matches
            ],

            # ── Emphasis of matter matches ─────────────────────────────────
            "emphasis_findings": [
                {"pattern": m.pattern_name, "snippet": m.snippet}
                for m in self.emphasis_matches
            ],

            # ── Counts ─────────────────────────────────────────────────────
            "total_caro_matches": len(self.caro_matches),
            "total_qualification_matches": len(self.qualification_matches),
        }


# ---------------------------------------------------------------------------
# Scanner class
# ---------------------------------------------------------------------------
class ComplianceScanner:
    """
    Deterministic regex-based scanner for credit risk signals in auditor text.
    Zero LLM calls. Every match is traceable to a character position.
    """

    MAX_SNIPPET_LEN = 400

    def scan(self, auditor_text: str, annexure_text: str = "") -> ComplianceScanResult:
        """
        Scan the auditor's report (and optional annexure) for compliance signals.

        Args:
            auditor_text:  Raw text of the Independent Auditor's Report section
            annexure_text: Raw text of the Annexure / CARO report (if separately extracted)

        Returns:
            ComplianceScanResult with boolean flags and detailed match excerpts
        """
        # Combine into a single searchable string, preserving section separation
        full_text = auditor_text
        if annexure_text.strip():
            full_text = full_text + "\n\n=== ANNEXURE ===\n\n" + annexure_text

        result = ComplianceScanResult()

        # ── 1. CARO 2020 / Clause (vii) / statutory defaults ────────────────
        for pattern in _CARO_PATTERNS:
            for match in pattern.finditer(full_text):
                snippet = self._extract_snippet(full_text, match.start(), match.end())
                result.caro_matches.append(
                    ComplianceMatch(
                        pattern_name=f"CARO / statutory-dues",
                        snippet=snippet,
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )

        # Deduplicate overlapping matches (keep the one with larger span)
        result.caro_matches = self._deduplicate(result.caro_matches)
        result.caro_default_found = len(result.caro_matches) > 0

        # ── 2. Auditor qualifications ─────────────────────────────────────────
        qualification_labels = [
            "Except for",
            "Adverse opinion",
            "Qualified opinion",
            "Disclaimer of opinion",
        ]
        for pattern, label in zip(_QUALIFICATION_PATTERNS, qualification_labels):
            for match in pattern.finditer(full_text):
                snippet = self._extract_snippet(full_text, match.start(), match.end())
                result.qualification_matches.append(
                    ComplianceMatch(
                        pattern_name=label,
                        snippet=snippet,
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )

        result.qualification_matches = self._deduplicate(result.qualification_matches)
        result.adverse_opinion_found = len(result.qualification_matches) > 0

        # ── 3. Emphasis of Matter / Going Concern ────────────────────────────
        emphasis_labels = [
            "Emphasis of Matter",
            "Material Uncertainty",
            "Going Concern",
        ]
        for pattern, label in zip(_EMPHASIS_PATTERNS, emphasis_labels):
            for match in pattern.finditer(full_text):
                snippet = self._extract_snippet(full_text, match.start(), match.end())
                result.emphasis_matches.append(
                    ComplianceMatch(
                        pattern_name=label,
                        snippet=snippet,
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )

        result.emphasis_matches = self._deduplicate(result.emphasis_matches)
        result.emphasis_of_matter_found = len(result.emphasis_matches) > 0

        # ── 4. Map to Rule Engine penalties ──────────────────────────────────
        if result.caro_default_found:
            result.triggered_rules.append("P-03")   # Statutory Default → +150 bps / -20% limit
            logger.warning("P-03 TRIGGERED: CARO 2020 statutory default found in auditor text")

        if result.adverse_opinion_found:
            result.triggered_rules.append("P-03")   # Qualified/Adverse → also P-03
            logger.warning("P-03 TRIGGERED: Auditor qualification found in report")

        if result.emphasis_of_matter_found:
            result.triggered_rules.append("P-04")   # Manual review flag
            logger.info("P-04 flagged: Emphasis of Matter / Going Concern found")

        # Deduplicate rule IDs
        result.triggered_rules = list(dict.fromkeys(result.triggered_rules))

        logger.info(
            f"Compliance scan complete — "
            f"CARO:{result.caro_default_found} | "
            f"AuditQual:{result.adverse_opinion_found} | "
            f"Emphasis:{result.emphasis_of_matter_found} | "
            f"Rules:{result.triggered_rules}"
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _extract_snippet(self, text: str, start: int, end: int) -> str:
        """Return up to MAX_SNIPPET_LEN chars centred around the match."""
        padding = max(0, (self.MAX_SNIPPET_LEN - (end - start)) // 2)
        s = max(0, start - padding)
        e = min(len(text), end + padding)
        snippet = text[s:e].strip()
        # Clean up excessive whitespace for readability
        snippet = re.sub(r"\n{3,}", "\n\n", snippet)
        snippet = re.sub(r" {3,}", " ", snippet)
        return snippet

    @staticmethod
    def _deduplicate(matches: List[ComplianceMatch]) -> List[ComplianceMatch]:
        """Remove matches whose spans overlap with a prior (larger) match."""
        if len(matches) <= 1:
            return matches
        # Sort by start position
        sorted_m = sorted(matches, key=lambda m: m.start_char)
        deduped = [sorted_m[0]]
        for m in sorted_m[1:]:
            prev = deduped[-1]
            # Skip if this match starts inside the previous match
            if m.start_char < prev.end_char:
                continue
            deduped.append(m)
        return deduped
