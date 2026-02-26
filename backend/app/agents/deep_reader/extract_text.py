"""
Module for extracting text from PDFs (both text-based and scanned).
Features Advanced Column and Table Layout support.
"""
import logging
from pathlib import Path
from typing import List, Optional
import io

import pdfplumber
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance
import pytesseract

logger = logging.getLogger(__name__)

class PageText:
    def __init__(self, page_number: int, text: str, method: str):
        self.page_number = page_number
        self.text = text
        self.method = method
        self.char_count = len(text)

def extract_text_with_table_support(page) -> str:
    """Extract text from a page using pdfplumber's native table extraction."""
    try:
        tables = page.find_tables()
        if not tables:
            return page.extract_text() or ""
        
        table_boxes = [{'x0': t.bbox[0], 'y0': t.bbox[1], 'x1': t.bbox[2], 'y1': t.bbox[3]} for t in tables]
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        non_table_words = []
        
        for word in words:
            word_center_x = (word['x0'] + word['x1']) / 2
            word_center_y = (word['top'] + word['bottom']) / 2
            is_in_table = any(b['x0'] <= word_center_x <= b['x1'] and b['y0'] <= word_center_y <= b['y1'] for b in table_boxes)
            if not is_in_table:
                non_table_words.append(word)
        
        non_table_text = ""
        if non_table_words:
            non_table_words.sort(key=lambda w: (round(w['top']), w['x0']))
            current_line = []
            current_top = non_table_words[0]['top'] if non_table_words else 0
            
            for word in non_table_words:
                word_text = word['text'].strip()
                if not word_text: continue
                if abs(word['top'] - current_top) <= 5:
                    current_line.append(word_text)
                else:
                    if current_line: non_table_text += ' '.join(current_line) + '\n'
                    current_line = [word_text]
                    current_top = word['top']
            if current_line: non_table_text += ' '.join(current_line) + '\n'
        
        table_texts = []
        for table in tables:
            try:
                extracted_table = table.extract()
                if extracted_table:
                    table_rows = [' | '.join([str(cell) if cell else '' for cell in row]) for row in extracted_table if row]
                    if table_rows: table_texts.append('\n'.join(table_rows))
            except Exception: continue
        
        result_parts = []
        if non_table_text.strip(): result_parts.append(non_table_text.strip())
        for table_text in table_texts:
            if table_text.strip(): result_parts.append("\n[TABLE]\n" + table_text.strip() + "\n[/TABLE]")
        
        return '\n\n'.join(result_parts) if result_parts else ""
    except Exception as e:
        return page.extract_text() or ""


def extract_text_from_text_pdf(pdf_path: Path, pages_to_extract: List[int] = None) -> tuple[List[PageText], dict]:
    """Extract text from a text-based PDF using pdfplumber."""
    logger.info(f"Extracting text from text-based PDF: {pdf_path.name}")
    pages = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                if pages_to_extract and page_num not in pages_to_extract:
                    continue
                    
                try:
                    text = extract_text_with_table_support(page)
                    if not text or len(text.strip()) < 50:
                        text = page.extract_text() or ""
                    
                    pages.append(PageText(page_number=page_num, text=text, method='direct'))
                except Exception as e:
                    pages.append(PageText(page_number=page_num, text="", method='direct'))
                    
    except Exception as e:
        logger.error(f"Error opening PDF with pdfplumber: {e}")
        return extract_text_with_pymupdf(pdf_path, pages_to_extract)
    
    return pages, _generate_stats(pages)


def extract_text_with_pymupdf(pdf_path: Path, pages_to_extract: List[int] = None) -> tuple[List[PageText], dict]:
    """Extract text using PyMuPDF (Fallback)."""
    pages = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            real_page_num = page_num + 1
            if pages_to_extract and real_page_num not in pages_to_extract:
                continue
            try:
                page = doc[page_num]
                text = page.get_text("text", sort=True)
                pages.append(PageText(page_number=real_page_num, text=text, method='direct'))
            except Exception:
                pages.append(PageText(page_number=real_page_num, text="", method='direct'))
        doc.close()
    except Exception as e:
        logger.error(f"Error with PyMuPDF fallback: {e}")
        
    return pages, _generate_stats(pages)


def extract_text_from_scanned_pdf(pdf_path: Path, pages_to_extract: List[int] = None) -> tuple[List[PageText], dict]:
    """Extract text from a scanned PDF using OCR (Tesseract)."""
    pages = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            real_page_num = page_num + 1
            if pages_to_extract and real_page_num not in pages_to_extract:
                continue
            try:
                page = doc[page_num]
                pix = page.get_pixmap(dpi=150) # Hardcoded optimal DPI
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data)).convert('L')
                
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.5)
                
                text = pytesseract.image_to_string(image)
                pages.append(PageText(page_number=real_page_num, text=text, method='ocr'))
            except Exception as e:
                pages.append(PageText(page_number=real_page_num, text="", method='ocr'))
        doc.close()
    except Exception as e:
        logger.error(f"Error during OCR extraction: {e}")
        
    return pages, _generate_stats(pages)


def _generate_stats(pages: List[PageText]) -> dict:
    char_counts = [len(p.text) for p in pages]
    pages_with_content = sum(1 for c in char_counts if c > 50)
    return {
        "pages_extracted": len(pages),
        "pages_with_content": pages_with_content,
        "total_characters": sum(char_counts),
        "extraction_coverage": (pages_with_content / len(pages) * 100) if pages else 0,
    }

def extract_text(pdf_path: Path, pdf_type: str, pages_to_extract: List[int] = None) -> tuple[List[PageText], dict]:
    if pdf_type == "scanned":
        return extract_text_from_scanned_pdf(pdf_path, pages_to_extract)
    else:
        return extract_text_from_text_pdf(pdf_path, pages_to_extract)

def get_full_text(pages: List[PageText]) -> str:
    return "\n\n".join([f"--- Page {p.page_number} ---\n{p.text}" for p in pages])
