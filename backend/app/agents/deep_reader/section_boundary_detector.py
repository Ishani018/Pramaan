"""
Section boundary detector - analyzes PDF layout to identify Auditor Report boundaries.
Optimized for performance using PyMuPDF (fitz).
"""
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import fitz # PyMuPDF

logger = logging.getLogger(__name__)

# ── Configuration for Pramaan ────────────────────────────────────────────────
SECTION_CONFIGS = [
    {
        "id": "auditors_report",
        "keywords": [
            "independent auditor's report", 
            "independent auditors' report", 
            "independent auditor report"
        ],
        "end_keywords": [
            "annexure to the independent auditor's report",
            "annexure to independent auditor's report",
            "annexure a", 
            "annexure b",
            "balance sheet", 
            "statement of profit and loss",
            "financial statements"
        ]
    },
    {
        "id": "auditors_annexure",
        "keywords": [
            "annexure to the independent auditor's report", 
            "annexure to independent auditor's report",
            "annexure a",
            "annexure b"
        ],
        "end_keywords": [
            "balance sheet", 
            "statement of profit and loss",
            "consolidated financial statements",
            "cash flow statement"
        ]
    }
]

@dataclass
class TextBlock:
    text: str
    page_number: int
    font_size: float
    y_position: float
    x_position: float
    bbox: tuple
    
    @property
    def normalized_text(self) -> str:
        return re.sub(r'\s+', ' ', self.text.lower().strip())
        
    @property
    def line_length(self) -> int:
        return len(self.text.strip())

@dataclass
class SectionBoundary:
    start_page: int
    end_page: int
    confidence: float
    start_heading: str


class SectionBoundaryDetector:
    """
    Detects section boundaries from PDF layout metadata.
    Uses font size, position, and keyword matching.
    """
    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.text_blocks: List[TextBlock] = []
        
    def extract_layout_metadata(self, max_pages: int = 200) -> List[TextBlock]:
        logger.info(f"Extracting layout metadata from {self.pdf_path.name}")
        blocks = []
        try:
            doc = fitz.open(str(self.pdf_path))
            pages_to_scan = min(len(doc), max_pages)
            
            for page_num in range(pages_to_scan):
                page = doc[page_num]
                blocks_dict = page.get_text("dict")
                
                for block in blocks_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        if not spans:
                            continue
                        text = " ".join(s["text"] for s in spans).strip()
                        if not text:
                            continue
                        font_size = max(s.get("size", 10) for s in spans)
                        bbox = line.get("bbox", (0, 0, 0, 0))
                        blocks.append(TextBlock(
                            text=text,
                            page_number=page_num + 1,
                            font_size=font_size,
                            y_position=bbox[1],
                            x_position=bbox[0],
                            bbox=bbox
                        ))
            doc.close()
        except Exception as e:
            logger.error(f"Error extracting layout metadata: {e}", exc_info=True)
        
        self.text_blocks = blocks
        return blocks
    
    def detect_section(self, section_config: dict, max_pages: int = 200) -> Optional[SectionBoundary]:
        """Find boundary for a specific section configuration."""
        if not self.text_blocks:
            self.extract_layout_metadata(max_pages)
            
        keywords = section_config.get("keywords", [])
        end_keywords = section_config.get("end_keywords", [])
        candidates = []
        
        for block in self.text_blocks:
            if not self._is_potential_heading(block):
                continue
                
            normalized = block.normalized_text
            for keyword in keywords:
                if keyword in normalized:
                    confidence = self._calculate_confidence(block, keyword, normalized)
                    candidates.append((block, confidence, keyword))
                    break
                    
        if not candidates:
            # Fallback: Plain keyword search without heading constraints
            if section_config.get("id") == "auditors_report":
                for block in self.text_blocks:
                    if "independent auditor" in block.normalized_text:
                        end_page = self._find_section_end(block.page_number, end_keywords)
                        return SectionBoundary(
                            start_page=block.page_number,
                            end_page=end_page,
                            confidence=0.5,
                            start_heading=block.text
                        )
            return None
            
        best_block, best_confidence, _ = max(candidates, key=lambda x: x[1])
        end_page = self._find_section_end(best_block.page_number, end_keywords)
        
        return SectionBoundary(
            start_page=best_block.page_number,
            end_page=end_page,
            confidence=best_confidence,
            start_heading=best_block.text
        )

    def _is_potential_heading(self, block: TextBlock) -> bool:
        if block.line_length > 150: return False # Headings aren't paragraphs
        
        # Heading heuristic: Font size should be larger than or equal to median font
        page_blocks = [b for b in self.text_blocks if b.page_number == block.page_number]
        if page_blocks:
            page_fonts = [b.font_size for b in page_blocks]
            median_font = sorted(page_fonts)[len(page_fonts) // 2]
            if block.font_size < median_font * 0.95: 
                return False
        return True

    def _calculate_confidence(self, block: TextBlock, keyword: str, normalized_text: str) -> float:
        confidence = 0.5
        if normalized_text.strip() == keyword: confidence += 0.3
        elif normalized_text.startswith(keyword) or normalized_text.endswith(keyword): confidence += 0.2
        else: confidence += 0.1
        
        # Position heuristic: Headings usually appear in the top half
        if block.y_position < 350: confidence += 0.1
        if block.line_length < 50: confidence += 0.05
        return min(confidence, 1.0)

    def _find_section_end(self, start_page: int, end_keywords: List[str]) -> int:
        # Scan subsequent blocks to find the next major heading
        subsequent_blocks = [b for b in self.text_blocks if b.page_number > start_page]
        for block in subsequent_blocks:
            normalized = block.normalized_text
            for end_keyword in end_keywords:
                if end_keyword in normalized and self._is_potential_heading(block):
                    return block.page_number - 1 
                    
        return start_page + 10 # Safety fallback limit
