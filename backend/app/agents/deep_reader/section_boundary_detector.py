"""
Section boundary detector - analyzes PDF layout to identify Auditor Report boundaries.
Adapted from BRSR layout-aware extraction logic.
"""
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import pdfplumber

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
        """Extract text blocks with layout metadata from PDF."""
        logger.info(f"Extracting layout metadata from {self.pdf_path.name}")
        blocks = []
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                # Only scan up to max_pages to save time
                pages_to_scan = pdf.pages[:max_pages]
                
                for page_num, page in enumerate(pages_to_scan, start=1):
                    words = page.extract_words(x_tolerance=3, y_tolerance=3, keep_blank_chars=False)
                    if not words:
                        continue
                    
                    font_sizes = [w.get('height', 10) for w in words]
                    page_median_font = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 10
                    lines = self._group_words_into_lines(words)
                    
                    for line in lines:
                        text = ' '.join([w['text'] for w in line])
                        if not text.strip():
                            continue
                        
                        first_word = line[0]
                        block = TextBlock(
                            text=text,
                            page_number=page_num,
                            font_size=first_word.get('height', page_median_font),
                            y_position=first_word['top'],
                            x_position=first_word['x0'],
                            bbox=(min(w['x0'] for w in line), min(w['top'] for w in line), 
                                  max(w['x1'] for w in line), max(w['bottom'] for w in line))
                        )
                        blocks.append(block)
                        
        except Exception as e:
            logger.error(f"Error extracting layout metadata: {e}", exc_info=True)
            
        self.text_blocks = blocks
        return blocks
    
    def _group_words_into_lines(self, words: List[dict]) -> List[List[dict]]:
        if not words: return []
        sorted_words = sorted(words, key=lambda w: (w['top'], w['x0']))
        lines, current_line = [], [sorted_words[0]]
        current_y = sorted_words[0]['top']
        
        for word in sorted_words[1:]:
            if abs(word['top'] - current_y) <= 3:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
                current_y = word['top']
        if current_line: lines.append(current_line)
        return lines

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
        if block.y_position > 400: return False  # Usually in the top half of page
        
        page_blocks = [b for b in self.text_blocks if b.page_number == block.page_number]
        if page_blocks:
            page_fonts = [b.font_size for b in page_blocks]
            median_font = sorted(page_fonts)[len(page_fonts) // 2]
            if block.font_size < median_font * 1.05: # Must be slightly larger than body text
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
