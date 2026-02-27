"""
Section boundary detector - analyzes PDF layout to identify Auditor Report boundaries.
Adapted from BRSR layout-aware extraction logic.
"""
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import fitz

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
        
    def extract_layout_metadata(self, max_pages: int = 150) -> List[TextBlock]:
        """Extract text blocks with layout metadata from PDF using PyMuPDF (fitz)."""
        logger.info(f"Extracting layout metadata from {self.pdf_path.name}")
        blocks = []
        found_sections = set()
        
        try:
            doc = fitz.open(self.pdf_path)
            pages_to_scan = min(len(doc), max_pages)
            
            for page_num in range(pages_to_scan):
                real_page_num = page_num + 1
                page = doc[page_num]
                page_dict = page.get_text("dict")
                
                for b in page_dict.get("blocks", []):
                    if b.get("type") == 0:  # Text block
                        for line in b.get("lines", []):
                            spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                            if not spans:
                                continue
                                
                            combined_text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
                            if not combined_text:
                                continue
                            
                            min_x0 = min(s.get("bbox")[0] for s in spans)
                            min_y0 = min(s.get("bbox")[1] for s in spans)
                            max_x1 = max(s.get("bbox")[2] for s in spans)
                            max_y1 = max(s.get("bbox")[3] for s in spans)
                            max_font_size = max(s.get("size", 10) for s in spans)
                            
                            block = TextBlock(
                                text=combined_text,
                                page_number=real_page_num,
                                font_size=max_font_size,
                                y_position=min_y0,
                                x_position=min_x0,
                                bbox=(min_x0, min_y0, max_x1, max_y1)
                            )
                            blocks.append(block)
                            
                            idx_text = block.normalized_text
                            if "independent auditor" in idx_text:
                                found_sections.add("auditor_report")
                            if "annexure to the independent auditor" in idx_text or "annexure to independent auditor" in idx_text:
                                found_sections.add("auditor_annexure")
                
                if len(found_sections) >= 2:
                    logger.info(f"Both sections found at page {real_page_num}, stopping early")
                    break
                    
                if real_page_num >= 150:
                    logger.info(f"Hard stop reached at page {real_page_num}")
                    break
                    
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
        
        # O(1) lookup: Cache median fonts per page to avoid O(N^2) list iteration
        if not hasattr(self, '_page_median_fonts'):
            self._page_median_fonts = {}
            page_fonts_temp = {}
            
            # Group fonts by page once
            for b in self.text_blocks:
                page_fonts_temp.setdefault(b.page_number, []).append(b.font_size)
                
            # Calculate the median for each page
            for page_num, fonts in page_fonts_temp.items():
                self._page_median_fonts[page_num] = sorted(fonts)[len(fonts) // 2] if fonts else 10
                
        median_font = self._page_median_fonts.get(block.page_number, 10)
        
        if block.font_size < median_font * 0.95: # More permissive font check
            return False
        return True

    def _calculate_confidence(self, block: TextBlock, keyword: str, normalized_text: str) -> float:
        confidence = 0.5
        if normalized_text.strip() == keyword: confidence += 0.3
        elif normalized_text.startswith(keyword) or normalized_text.endswith(keyword): confidence += 0.2
        else: confidence += 0.1
        
        if block.y_position < 150: confidence += 0.1
        if block.line_length < 50: confidence += 0.05
        return min(confidence, 1.0)

    def _find_section_end(self, start_page: int, end_keywords: List[str]) -> int:
        subsequent_blocks = [b for b in self.text_blocks if b.page_number > start_page]
        for block in subsequent_blocks:
            normalized = block.normalized_text
            for end_keyword in end_keywords:
                if end_keyword in normalized and self._is_potential_heading(block):
                    # We found the next section heading, meaning current section ended
                    return block.page_number - 1 
                    
        return start_page + 10 # Fallback safety limit if no end found
