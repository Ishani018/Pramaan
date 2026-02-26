"""
Deep Reader Agent – Section Hierarchy Builder
=============================================
Extracted and adapted from:
  github.com/ishani018/brsr-report-extraction  →  pipeline/section_hierarchy_builder.py

Parses flat MD&A text into a hierarchical dict using deterministic heuristics
(all-caps, title-case, keyword lists, line length).  No LLM required.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class Heading:
    text: str
    level: int
    line_index: int
    confidence: float


@dataclass
class ContentBlock:
    heading: str
    level: int
    content: List[str]
    subsections: List["ContentBlock"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heading": self.heading,
            "level": self.level,
            "content": self.content,
            "subsections": [s.to_dict() for s in self.subsections],
        }


# ---------------------------------------------------------------------------
# Builder Class
# ---------------------------------------------------------------------------
class SectionHierarchyBuilder:
    """
    Builds a hierarchical JSON-like structure from flat section text.
    Uses deterministic heuristics — uppercase, title-case, keyword match, line length.
    """

    MDNA_KEYWORDS = [
        "overview", "business overview", "industry overview",
        "financial performance", "financial review", "results of operations",
        "operating results", "segment analysis", "business segments",
        "revenue", "expenses", "profitability", "cash flow",
        "liquidity", "capital resources", "working capital",
        "risk", "risk factors", "risk management",
        "outlook", "future outlook", "forward looking",
        "strategy", "business strategy", "growth strategy",
        "opportunities", "challenges", "critical accounting",
        # India-specific additions
        "gst", "gstr", "msme", "rbi", "sebi", "cibil", "nbfc",
        "capex", "opex", "ebitda", "pat", "pbt", "roce",
    ]

    def __init__(self, section_type: str = "mdna"):
        self.section_type = section_type
        self.keywords = self.MDNA_KEYWORDS

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def build_hierarchy(self, text: str) -> Dict[str, Any]:
        """
        Parse flat text into a nested hierarchy of headings + content.

        Returns:
            {
              "section_type": "mdna",
              "structure": [ ContentBlock.to_dict(), ... ],
              "total_paragraphs": N,
              "heading_count": M,
            }
        """
        lines = [l.rstrip() for l in text.splitlines()]

        heading_objects: List[Tuple[int, Heading]] = []  # (line_idx, Heading)
        for i, line in enumerate(lines):
            prev = lines[i - 1] if i > 0 else None
            nxt = lines[i + 1] if i < len(lines) - 1 else None
            is_h, conf, level = self.is_likely_heading(line, prev, nxt)
            if is_h:
                heading_objects.append((i, Heading(text=line.strip(), level=level, line_index=i, confidence=conf)))

        structure = self._build_structure(lines, heading_objects)

        return {
            "section_type": self.section_type,
            "structure": [b.to_dict() for b in structure],
            "total_paragraphs": sum(len(b.content) for b in structure),
            "heading_count": len(heading_objects),
        }

    def is_likely_heading(
        self,
        line: str,
        prev_line: Optional[str] = None,
        next_line: Optional[str] = None,
    ) -> Tuple[bool, float, int]:
        """
        Determine if a line is a heading.

        Returns:
            (is_heading, confidence, level)
        """
        line = line.strip()

        if len(line) < 3:
            return False, 0.0, 0

        # Skip obvious page numbers / footers
        if re.match(r"^\d+$", line) or re.match(r"^page\s+\d+", line, re.IGNORECASE):
            return False, 0.0, 0

        confidence = 0.0
        level = 2

        # Heuristic 1: All uppercase (strong → level 1)
        if line.isupper() and len(line.split()) >= 2:
            confidence += 0.4
            level = 1

        # Heuristic 2: Title case (moderate → level 2)
        words = line.split()
        title_words = sum(1 for w in words if w and w[0].isupper())
        if title_words >= len(words) * 0.7 and len(words) >= 2:
            confidence += 0.3
            if level != 1:
                level = 2

        # Heuristic 3: Matches known keywords
        line_lower = line.lower()
        for kw in self.keywords:
            if kw in line_lower:
                confidence += 0.25
                break

        # Heuristic 4: Short line followed by dense paragraph
        if len(words) <= 8 and next_line and len(next_line.strip().split()) > 15:
            confidence += 0.2

        # Heuristic 5: Numbered section (e.g. "1.", "2.1", "A.")
        if re.match(r"^(\d+\.?\d*|[A-Z]\.)\s+\w", line):
            confidence += 0.3
            level = min(level, 2)

        # Penalise headings that are suspiciously long
        if len(words) > 12:
            confidence -= 0.2

        return (confidence >= 0.35), confidence, level

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _build_structure(
        self,
        lines: List[str],
        heading_objects: List[Tuple[int, Heading]],
    ) -> List[ContentBlock]:
        """Assemble heading + content pairs into a flat list of ContentBlocks."""
        if not heading_objects:
            # Treat entire text as a single unnamed block
            return [ContentBlock(heading="(MD&A Text)", level=1, content=[l for l in lines if l.strip()])]

        blocks: List[ContentBlock] = []
        heading_indices = [idx for idx, _ in heading_objects]

        for i, (h_idx, heading) in enumerate(heading_objects):
            # Content lines run until next heading
            end_idx = heading_indices[i + 1] if i + 1 < len(heading_objects) else len(lines)
            content_lines = [
                lines[j].strip()
                for j in range(h_idx + 1, end_idx)
                if lines[j].strip()
            ]
            blocks.append(
                ContentBlock(
                    heading=heading.text,
                    level=heading.level,
                    content=content_lines,
                )
            )

        return blocks
