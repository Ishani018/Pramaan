"""
Module to detect if a PDF is a text PDF, or simply a scanned image wrapped in a PDF wrapper.
"""
import logging
from pathlib import Path
import pdfplumber

logger = logging.getLogger(__name__)

def detect_pdf_type(pdf_path: Path, sample_pages: int = 10, min_avg_chars_per_page: int = 100) -> str:
    """
    Detects if a PDF is text-based or scanned by sampling the first few pages.
    """
    try:
        total_chars = 0
        pages_to_check = 0
        
        with pdfplumber.open(pdf_path) as pdf:
            pages_to_check = min(sample_pages, len(pdf.pages))
            if pages_to_check == 0:
                return "scanned"
                
            for i in range(pages_to_check):
                text = pdf.pages[i].extract_text() or ""
                total_chars += len(text)
                
        avg_chars = total_chars / pages_to_check
        logger.info(f"detect_pdf_type: Avg chars/page over first {pages_to_check} pages: {avg_chars:.1f}")
        
        # If the average characters per page is greater than the threshold, it is likely text-based.
        # Images or scanned documents without OCR typically yield very few or zero text characters.
        if avg_chars > min_avg_chars_per_page:
            return "text"
        else:
            return "scanned"
            
    except Exception as e:
        logger.error(f"Error detecting PDF type for {pdf_path.name}: {e}")
        # Default to scanned if we can't open properly, expecting OCR fallback to handle it.
        return "scanned"
