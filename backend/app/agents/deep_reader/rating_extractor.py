"""
Rating Agency Extractor
========================
Scans annual report text for credit ratings from major Indian agencies
(CRISIL, ICRA, CARE, India Ratings, Brickwork, Acuité).
Extracts the latest rating grade, outlook, and detects downgrades.

Zero-LLM — pure regex + keyword matching.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List

logger = logging.getLogger(f"pramaan.{__name__}")

# Rating agencies recognized
AGENCIES = ["CRISIL", "ICRA", "CARE", "India Ratings", "Brickwork", "Acuité", "Acuite"]

# Rating grades in descending creditworthiness
RATING_HIERARCHY = [
    "AAA", "AA+", "AA", "AA-",
    "A+", "A", "A-",
    "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-",
    "B+", "B", "B-",
    "C", "D",
]

# Investment grade threshold
INVESTMENT_GRADE = {"AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"}


@dataclass
class RatingResult:
    ratings_found: List[dict] = field(default_factory=list)
    latest_rating: Optional[str] = None
    latest_agency: Optional[str] = None
    latest_outlook: Optional[str] = None
    is_investment_grade: Optional[bool] = None
    downgrade_detected: bool = False
    downgrade_details: Optional[str] = None
    triggered_rules: List[str] = field(default_factory=list)


class RatingExtractor:
    """Extract credit ratings from annual report text."""

    # Pattern: AGENCY followed by rating grade
    RATING_PATTERN = re.compile(
        r'(CRISIL|ICRA|CARE|India\s+Ratings?|Brickwork|Acuit[eé])\s+'
        r'([A-D]{1,3}[+-]?(?:\s*\([A-Za-z]+\))?)',
        re.IGNORECASE
    )

    # Outlook detection
    OUTLOOK_PATTERN = re.compile(
        r'(?:outlook|watch)\s*[:\s]*\s*(stable|negative|positive|developing|watch)',
        re.IGNORECASE
    )

    # Downgrade detection
    DOWNGRADE_PATTERNS = [
        re.compile(r'(downgrad|revis\w+\s+downward)', re.IGNORECASE),
        re.compile(r'rat(?:ing|ed)\s+(?:has been|was)\s+(?:downgrad|lower|revis)', re.IGNORECASE),
        re.compile(r'from\s+([A-D]{1,3}[+-]?)\s+to\s+([A-D]{1,3}[+-]?)', re.IGNORECASE),
    ]

    def extract(self, full_text: str) -> RatingResult:
        """
        Scan full_text for credit ratings.

        Returns RatingResult with found ratings, outlook, and downgrade flags.
        """
        result = RatingResult()

        if not full_text or len(full_text) < 100:
            return result

        # Find all rating mentions
        for m in self.RATING_PATTERN.finditer(full_text):
            agency = m.group(1).strip()
            grade_raw = m.group(2).strip()

            # Clean up grade — strip parenthetical like "(Stable)"
            grade = re.sub(r'\s*\([^)]*\)', '', grade_raw).strip().upper()

            if grade not in RATING_HIERARCHY:
                continue

            # Get surrounding context for outlook
            ctx_start = max(0, m.start() - 50)
            ctx_end = min(len(full_text), m.end() + 100)
            context = full_text[ctx_start:ctx_end]

            outlook_match = self.OUTLOOK_PATTERN.search(context)
            outlook = outlook_match.group(1).title() if outlook_match else None

            rating_entry = {
                "agency": agency,
                "grade": grade,
                "outlook": outlook,
                "is_investment_grade": grade in INVESTMENT_GRADE,
                "snippet": full_text[max(0, m.start()-20):m.end()+50].strip(),
            }
            result.ratings_found.append(rating_entry)

            logger.info(f"RatingExtractor: {agency} {grade} (Outlook: {outlook})")

        # Use the last found rating as the "latest"
        if result.ratings_found:
            latest = result.ratings_found[-1]
            result.latest_agency = latest["agency"]
            result.latest_rating = latest["grade"]
            result.latest_outlook = latest["outlook"]
            result.is_investment_grade = latest["is_investment_grade"]

        # Check for downgrades
        for pattern in self.DOWNGRADE_PATTERNS:
            m = pattern.search(full_text)
            if m:
                result.downgrade_detected = True
                ctx_start = max(0, m.start() - 30)
                ctx_end = min(len(full_text), m.end() + 80)
                result.downgrade_details = full_text[ctx_start:ctx_end].strip()
                logger.warning(f"RatingExtractor: DOWNGRADE detected — '{result.downgrade_details}'")
                break

        # Trigger rules
        if result.latest_rating and not result.is_investment_grade:
            result.triggered_rules.append("P-27")
            logger.warning(
                f"RatingExtractor: P-27 TRIGGERED — Sub-investment grade "
                f"({result.latest_agency} {result.latest_rating})"
            )

        if result.downgrade_detected:
            if "P-27" not in result.triggered_rules:
                result.triggered_rules.append("P-27")

        return result
