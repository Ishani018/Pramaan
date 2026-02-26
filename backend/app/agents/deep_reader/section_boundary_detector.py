"""
Deep Reader Agent – Section Boundary Detector
=============================================
Extracted and adapted from:
  github.com/ishani018/brsr-report-extraction  →  pipeline/section_boundary_detector.py

Analyses PDF layout metadata (font size, y-position, keyword matching) to locate the
following major financial sections without any LLM calls:
  • MD&A (Management Discussion & Analysis)
  • Independent Auditor's Report
  • Notes to Financial Statements
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber
import io

try:
    import fitz
except (ImportError, OSError):
    fitz = None

try:
    import pytesseract
    from PIL import Image
except (ImportError, OSError):
    pytesseract = None
    Image = None

from app.agents.deep_reader.detect_pdf_type import detect_pdf_type

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section configs: (section_id, start_keywords, end_keywords, max_pages)
# ---------------------------------------------------------------------------
SECTION_CONFIGS = [
    {
        "id": "mdna",
        "label": "Management Discussion & Analysis",
        "start_keywords": [
            "management discussion",
            "management's discussion",
            "management discussion and analysis",
            "md&a",
            "mda",
            "management review",
            "directors discussion",
            "director's discussion",
            "discussion and analysis",
        ],
        "end_keywords": [
            "standalone financial statements",
            "consolidated financial statements",
            "independent auditor",
            "auditors report",
            "balance sheet",
            "statement of profit",
            "cash flow statement",
            "notes to financial",
            "corporate governance report",
        ],
        "max_pages": 30,
    },
    {
        "id": "auditors_report",
        "label": "Independent Auditor's Report",
        "start_keywords": [
            "independent auditor",
            "independent auditors",
            "auditor's report",
            "auditors report",
            "report of the auditors",
            "independent statutory auditor",
            "to the members",  # common opener in Indian audit reports
        ],
        "end_keywords": [
            "balance sheet",
            "statement of profit",
            "cash flow statement",
            "notes to financial",
            "notes forming part",
            "notes to accounts",
        ],
        "max_pages": 20,
    },
    {
        "id": "auditors_annexure",
        "label": "Annexure to the Independent Auditor's Report",
        "start_keywords": [
            "annexure to the independent auditor",
            "annexure to independent auditor",
            "annexure to auditor's report",
            "annexure referred to in",
            "report referred to in paragraph",
            "caro report",
            "companies auditor's report order",
            "annexure a",       # common label in Indian annual reports
            "annexure b",
            "annexure – a",
        ],
        "end_keywords": [
            "balance sheet",
            "statement of profit",
            "cash flow statement",
            "notes to financial",
            "notes forming part",
            "standalone financial",
            "consolidated financial",
        ],
        "max_pages": 15,
    },
]


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class TextBlock:
    """Single line / word-group extracted from a PDF page."""
    text: str
    page_number: int
    font_size: float
    y_position: float
    x_position: float
    bbox: Tuple[float, float, float, float]

    @property
    def normalized_text(self) -> str:
        return re.sub(r"\s+", " ", self.text.lower()).strip()

    @property
    def line_length(self) -> int:
        return len(self.text)


@dataclass
class SectionBoundary:
    """Start/end page range for a detected section."""
    section_type: str
    start_page: int
    end_page: int
    confidence: float
    start_heading: str
    detection_method: str = "layout_and_keywords"


# ---------------------------------------------------------------------------
# Main Detector Class
# ---------------------------------------------------------------------------
class SectionBoundaryDetector:
    """
    Detects section boundaries from PDF layout metadata.
    Uses font size, y-position, and keyword matching — fully deterministic.
    """

    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)
        self.text_blocks: List[TextBlock] = []
        self.pdf_type = detect_pdf_type(self.pdf_path)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def extract_layout_metadata(self, max_pages: int = 200) -> List[TextBlock]:
        """Extract text blocks with layout metadata from early PDF pages."""
        logger.info(f"Extracting layout metadata from {self.pdf_path.name} (max {max_pages} pages)")
        blocks: List[TextBlock] = []
        page_num = 0

        try:
            if self.pdf_type == "scanned":
                logger.info("PDF detected as scanned, falling back to OCR layout extraction")
                blocks = self._extract_layout_metadata_ocr(max_pages)
            else:
                with pdfplumber.open(self.pdf_path) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        if page_num > max_pages:
                            logger.info(f"Reached MAX_PAGES limit ({max_pages}). Stopping pdfplumber layout scan early.")
                            break
                        words = page.extract_words(
                            x_tolerance=3,
                            y_tolerance=3,
                            keep_blank_chars=False,
                        )
                        if not words:
                            continue

                        font_sizes = [w.get("height", 10) for w in words]
                        median_font = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 10

                        for line in self._group_words_into_lines(words):
                            text = " ".join(w["text"] for w in line)
                            if not text.strip():
                                continue

                            first_word = line[0]
                            blocks.append(
                                TextBlock(
                                    text=text,
                                    page_number=page_num,
                                    font_size=first_word.get("height", median_font),
                                    y_position=first_word["top"],
                                    x_position=first_word["x0"],
                                    bbox=(
                                        min(w["x0"] for w in line),
                                        min(w["top"] for w in line),
                                        max(w["x1"] for w in line),
                                        max(w["bottom"] for w in line),
                                    ),
                                )
                            )
        except Exception as exc:
            logger.error(f"Error extracting layout metadata: {exc}", exc_info=True)
            if not blocks:
                logger.info("Attempting PyMuPDF fallback layout extraction")
                blocks = self._extract_layout_metadata_pymupdf(max_pages)

        logger.info(f"Extracted {len(blocks)} text blocks from (up to) {max_pages} pages")
        self.text_blocks = blocks
        return blocks

    def detect_mdna_boundary(self) -> Optional[SectionBoundary]:
        """
        Backwards-compatible: locate just the MD&A section.
        Calls the generic detect_section() internally.
        """
        cfg = next(c for c in SECTION_CONFIGS if c["id"] == "mdna")
        return self.detect_section(cfg)

    def detect_all_sections(self) -> Dict[str, Optional[SectionBoundary]]:
        """
        Detect all configured financial sections in one pass.
        Returns a dict keyed by section_id, e.g.:
          { "mdna": SectionBoundary, "auditors_report": SectionBoundary, ... }
        """
        if not self.text_blocks:
            self.extract_layout_metadata()

        results: Dict[str, Optional[SectionBoundary]] = {}
        for cfg in SECTION_CONFIGS:
            boundary = self.detect_section(cfg)
            results[cfg["id"]] = boundary
            if boundary:
                logger.info(
                    f"[{cfg['id']}] found pages {boundary.start_page}–{boundary.end_page} "
                    f"conf={boundary.confidence:.2f}"
                )
            else:
                logger.info(f"[{cfg['id']}] not found")
        return results

    def detect_section(self, cfg: dict) -> Optional[SectionBoundary]:
        """
        Generic section detector driven by a config dict.
        cfg keys: id, label, start_keywords, end_keywords, max_pages
        """
        max_limit = cfg.get("max_pages", 200)
        
        if not self.text_blocks:
            self.extract_layout_metadata(max_pages=max_limit)
        if not self.text_blocks:
            logger.warning("No text blocks — PDF may be image-only")
            return None

        start_block, start_conf = self._find_heading(cfg["start_keywords"])
        if start_block is None:
            return None

        start_page = start_block.page_number
        end_page = self._find_section_end_custom(
            start_page, cfg["end_keywords"], cfg["max_pages"]
        )

        return SectionBoundary(
            section_type=cfg["id"],
            start_page=start_page,
            end_page=end_page,
            confidence=start_conf,
            start_heading=start_block.text,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _extract_layout_metadata_pymupdf(self, max_pages: int = 200) -> List[TextBlock]:
        """Fallback extractor using PyMuPDF (fitz) for difficult PDFs."""
        blocks: List[TextBlock] = []
        if fitz is None:
            logger.warning("PyMuPDF (fitz) is not installed properly. Skipping PyMuPDF fallback.")
            return blocks
            
        try:
            doc = fitz.open(self.pdf_path)
            for page_num, page in enumerate(doc, start=1):
                if page_num > max_pages:
                    logger.info(f"Reached MAX_PAGES limit ({max_pages}). Stopping PyMuPDF scan early.")
                    break
                page_dict = page.get_text("dict")
                for block in page_dict.get("blocks", []):
                    if block.get("type") == 0:  # Text block
                        for line in block.get("lines", []):
                            line_text = ""
                            line_fonts = []
                            line_bbox = line["bbox"]
                            for span in line.get("spans", []):
                                line_text += span["text"] + " "
                                line_fonts.append(span["size"])
                            
                            line_text = line_text.strip()
                            if not line_text:
                                continue
                                
                            median_font = sorted(line_fonts)[len(line_fonts) // 2] if line_fonts else 10
                            
                            blocks.append(
                                TextBlock(
                                    text=line_text,
                                    page_number=page_num,
                                    font_size=median_font,
                                    y_position=line_bbox[1], # top
                                    x_position=line_bbox[0], # x0
                                    bbox=line_bbox
                                )
                            )
        except Exception as e:
            logger.error(f"PyMuPDF layout extraction failed: {e}")
        return blocks
        
    def _extract_layout_metadata_ocr(self, max_pages: int = 200) -> List[TextBlock]:
        """Fallback extractor using Tesseract OCR for scanned PDFs."""
        blocks: List[TextBlock] = []
        if fitz is None or pytesseract is None or Image is None:
            logger.warning("OCR dependencies (fitz, pytesseract, Pillow) are not installed properly. Skipping OCR fallback.")
            return blocks
            
        try:
            doc = fitz.open(self.pdf_path)
            for page_num, page in enumerate(doc, start=1):
                if page_num > max_pages:
                    logger.info(f"Reached MAX_PAGES limit ({max_pages}). Stopping OCR scan early.")
                    break
                
                pix = page.get_pixmap(dpi=150) # Use lower DPI for layout analysis to save memory
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))
                
                # Use image_to_data for bounding box info
                ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                
                # Group OCR words into lines
                current_line = []
                current_y = -1
                current_block_num = -1
                current_par_num = -1
                current_line_num = -1
                
                for i in range(len(ocr_data['text'])):
                    text = ocr_data['text'][i].strip()
                    if not text:
                        continue
                        
                    # Group by block, paragraph, and line number
                    block_num = ocr_data['block_num'][i]
                    par_num = ocr_data['par_num'][i]
                    line_num = ocr_data['line_num'][i]
                    
                    if (block_num != current_block_num or 
                        par_num != current_par_num or 
                        line_num != current_line_num):
                        # New line
                        if current_line:
                            blocks.append(self._create_ocr_block(current_line, page_num))
                        current_line = []
                        current_block_num = block_num
                        current_par_num = par_num
                        current_line_num = line_num
                        
                    current_line.append({
                        'text': text,
                        'left': ocr_data['left'][i],
                        'top': ocr_data['top'][i],
                        'width': ocr_data['width'][i],
                        'height': ocr_data['height'][i]
                    })
                
                if current_line:
                    blocks.append(self._create_ocr_block(current_line, page_num))
                    
        except Exception as e:
            logger.error(f"OCR layout extraction failed: {e}")
            
        return blocks
        
    def _create_ocr_block(self, line_words: List[dict], page_num: int) -> TextBlock:
        """Helper to create a TextBlock from OCR line words."""
        text = " ".join(w['text'] for w in line_words)
        
        # Calculate bounding box
        x0 = min(w['left'] for w in line_words)
        y0 = min(w['top'] for w in line_words)
        x1 = max(w['left'] + w['width'] for w in line_words)
        y1 = max(w['top'] + w['height'] for w in line_words)
        
        # Estimate font size (typically ~70-80% of line height)
        heights = [w['height'] for w in line_words]
        median_height = sorted(heights)[len(heights) // 2]
        estimated_font_size = median_height * 0.75
        
        return TextBlock(
            text=text,
            page_number=page_num,
            font_size=estimated_font_size,
            y_position=y0,
            x_position=x0,
            bbox=(x0, y0, x1, y1)
        )

    def _group_words_into_lines(self, words: List[dict]) -> List[List[dict]]:
        """Group word dicts into lines by y-position proximity."""
        if not words:
            return []

        sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
        lines: List[List[dict]] = []
        current_line = [sorted_words[0]]
        current_y = sorted_words[0]["top"]

        for word in sorted_words[1:]:
            if abs(word["top"] - current_y) <= 3:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
                current_y = word["top"]

        if current_line:
            lines.append(current_line)

        return lines

    def _find_heading(
        self, keywords: List[str]
    ) -> Tuple[Optional[TextBlock], float]:
        """Scan text blocks for the best-matching keyword heading."""
        candidates: List[Tuple[TextBlock, float, str]] = []

        for block in self.text_blocks:
            if not self._is_potential_heading(block):
                continue

            normalized = block.normalized_text
            for kw in keywords:
                if kw in normalized:
                    conf = self._calculate_confidence(block, kw, normalized)
                    candidates.append((block, conf, kw))
                    break  # one match per block

        if not candidates:
            return None, 0.0

        best_block, best_conf, _ = max(candidates, key=lambda x: x[1])
        return best_block, best_conf

    def _is_potential_heading(self, block: TextBlock) -> bool:
        """Heuristic: short line, near top of page, relatively large font."""
        if block.line_length > 120:
            return False
        if block.y_position > 350:
            return False

        # Font must be >= median for that page
        page_blocks = [b for b in self.text_blocks if b.page_number == block.page_number]
        if page_blocks:
            fonts = [b.font_size for b in page_blocks]
            median = sorted(fonts)[len(fonts) // 2]
            if block.font_size < median * 1.05:
                return False

        return True

    def _calculate_confidence(
        self, block: TextBlock, keyword: str, normalized: str
    ) -> float:
        """Score match quality (0–1) based on font size, position, and match exactness."""
        conf = 0.5

        # Exact match boost
        if normalized.strip() == keyword:
            conf += 0.3

        # Font size prominence
        page_blocks = [b for b in self.text_blocks if b.page_number == block.page_number]
        if page_blocks:
            fonts = [b.font_size for b in page_blocks]
            max_font = max(fonts)
            if max_font > 0:
                conf += 0.2 * (block.font_size / max_font)

        # Prefer headings near the top of the page
        if block.y_position < 150:
            conf += 0.1

        return min(conf, 1.0)

    def _find_section_end(self, start_page: int) -> int:
        """Backwards-compat: uses mdna end keywords."""
        cfg = next(c for c in SECTION_CONFIGS if c["id"] == "mdna")
        return self._find_section_end_custom(start_page, cfg["end_keywords"], cfg["max_pages"])

    def _find_section_end_custom(
        self, start_page: int, end_keywords: List[str], max_pages: int
    ) -> int:
        """
        Scan for any end-keyword heading after start_page.
        Falls back to start_page + max_pages if none found.
        """
        for block in self.text_blocks:
            if block.page_number <= start_page:
                continue
            if block.page_number > start_page + max_pages:
                break  # past the cap
            if not self._is_potential_heading(block):
                continue

            normalized = block.normalized_text
            for kw in end_keywords:
                if kw in normalized:
                    return block.page_number - 1

        return start_page + max_pages
