"""
FinancialExtractor
==================
Regex-based extraction of key financial figures from annual report text.
Zero-LLM implementation for consistent, deterministic scraping.
"""

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(f"pramaan.{__name__}")

def detect_unit_and_normalize(value: float, context: str) -> tuple[float, str]:
    ctx = context.lower()
    if any(x in ctx for x in ['lakh crore', 'lakh cr']):
        return round(value * 100000, 2), 'Lakh Cr'
    if re.search(r'\b(bn|billion)\b', ctx):
        return round(value * 100, 2), 'Bn→Cr'
    if re.search(r'\b(crore|cr)\b', ctx):
        return round(value, 2), 'Cr'
    if re.search(r'\b(mn|million)\b', ctx):
        return round(value / 100, 2), 'Mn→Cr'
    return round(value, 2), 'unknown'

FIELD_PATTERNS = {
    "Revenue": {
        "patterns": [
            # Plain table: "Revenue from operations  1,223.16"
            r'revenue\s+from\s+operations\s+\d*\s*([\d,]{4,}\.?\d{2})',
            # Narrative: "Revenue stood at ₹ 435.7 billion"
            r'revenue\s+stood\s+at\s+[`₹$]?\s*([\d,]+\.?\d*)\s*(bn|billion|cr|crore|mn|million)',
            # Narrative: "total revenue of ₹ X Cr"  
            r'total\s+revenue\s+(?:of|was|is|:)\s*[`₹$]?\s*([\d,]+\.?\d*)\s*(bn|billion|cr|crore|mn|million)',
            # Income statement table line — 5+ digit number only
            r'revenue\s+from\s+operations\s+(?:\d{1,3}\s+)?([\d,]{5,}\.?\d*)',
        ],
        "exclude_patterns": [
            r'decreased\s+by',
            r'increased\s+by',
            r'(?:decreased|increased|decline|growth)\s+(?:by\s+)?[`₹]?\s*[\d,]+',
            r'(\d+\.?\d*)\s*%',
        ]
    },
    "EBITDA": {
        "patterns": [
            r'(?:cash\s+)?ebitda[\s\S]{0,80}?([\d,]+\.?\d*)\s*(?:mn|cr|bn|billion|crore)',
            r'(?:cash\s+)?ebitda\s+(?:stood\s+at\s+)?[`₹]?\s*([\d,]+\.?\d*)',
            r'operating\s+(?:profit|ebitda)[\s\S]{0,60}?([\d,]+\.?\d*)\s*(?:mn|cr|bn)',
        ],
        "exclude_patterns": [
            r'ebitda\s+margin[\s\S]{0,30}?(\d+\.?\d*)\s*%',
        ]
    },
    "PAT": {
        "patterns": [
            # Force-prefer "loss for the year amounting to" — highest priority
            r'(?:loss|profit)\s+for\s+the\s+year\s+amounting\s+to\s+[`₹]?\s*(\([\d,]+\.?\d*\))',
            # Income statement: profit/(loss) for the year
            # Must have 4+ digit number — not "49"
            r'(?:profit|loss)\s*[/\(]?\s*(?:loss)?\s*\)?\s+for\s+the\s+(?:year|period)[\s\S]{0,80}?(\([\d,]{4,}\.?\d*\)|[\d,]{4,}\.?\d*)',
            # Net loss/profit after tax with unit
            r'net\s+(?:profit|loss)\s+after\s+tax[\s\S]{0,60}?[`₹]?\s*(\([\d,]{4,}\.?\d*\)|[\d,]{4,}\.?\d*)\s*(?:mn|cr|bn)',
        ],
        "exclude_patterns": [
            r'(\d+)\s+percent',
            r'(\d+\.?\d*)\s*(?:%|per\s*cent)',
        ]
    },
    "Total Debt": {
        "patterns": [
            r'total\s+(?:borrowings?|debt)[\s\S]{0,80}?[`₹]?\s*([\d,]+\.?\d*)\s*(?:mn|cr|bn|crore)',
            r'(?:long.term\s+borrowings?[\s\S]{0,30}?short.term\s+borrowings?|total\s+debt)[\s\S]{0,60}?[`₹]?\s*([\d,]+\.?\d*)',
            r'total\s+financial\s+liabilities[\s\S]{0,60}?([\d,]+\.?\d*)',
        ],
        "exclude_patterns": []
    },
    "Net Worth": {
        "patterns": [
            # "total equity stood at ₹ (703,202) Mn"
            # Handles bracket notation for negative equity
            r'total\s+equity[\s\S]{0,60}?[`₹]?\s*(\([\d,]{4,}\.?\d*\)|[\d,]{4,}\.?\d*)\s*(?:mn|cr|bn|crore|million)?',
            # shareholders funds
            r'shareholders[\'s]*\s+(?:fund|equity)[\s\S]{0,60}?[`₹]?\s*(\([\d,]+\.?\d*\)|[\d,]{4,}\.?\d*)',
            # net worth with 4+ digits
            r'net\s+worth[\s\S]{0,60}?[`₹]?\s*(\([\d,]{4,}\.?\d*\)|[\d,]{4,}\.?\d*)',
        ],
        "exclude_patterns": [
            r'(\d+\.?\d*)\s*%',
            r'increased\s+by\s+\d+',
        ]
    }
}

class FinancialExtractor:
    """
    Extracts high-level financials and metadata purely via deterministic regex.
    """
    def __init__(self):
        # Auditor firm name usually follows "For " right before the partner signature
        self.auditor_pattern = r'(?i)for\s+([a-zA-Z\s&,\.\-]{5,80}?(?:chartered\s+accountants|associates|llp|&\s+co\.?))'

    def extract(self, text: str, year: str) -> Dict[str, Optional[Dict[str, Any]]]:
        full_text = text
        results = {}
        
        fin_section = self._get_financial_section(full_text)
        
        for field, config in FIELD_PATTERNS.items():
            best = None
            best_raw = None
            best_confidence = 0
            best_snippet = ""
            best_unit = "unknown"
            
            for pat_idx, pattern in enumerate(config["patterns"]):
                matches = re.finditer(pattern, fin_section, re.IGNORECASE)
                
                for m in matches:
                    raw_val_str = m.group(1).replace(',', '').replace('(', '-').replace(')', '')
                    try:
                        raw_val = float(raw_val_str)
                    except ValueError:
                        continue
                    
                    if abs(raw_val) < 10:
                        continue
                    
                    context_window = fin_section[max(0, m.start()-100):m.end()+100]
                    excluded = False
                    for excl in config.get("exclude_patterns", []):
                        if re.search(excl, context_window, re.IGNORECASE):
                            excl_match = re.search(excl, m.group(0), re.IGNORECASE)
                            if excl_match:
                                excluded = True
                                break
                    
                    if excluded:
                        continue
                    
                    normalized, unit = detect_unit_and_normalize(raw_val, context_window)
                    
                    confidence = 0
                    if unit != 'unknown': confidence += 40
                    if re.search(r'[`₹\$]', context_window): confidence += 20
                    if 10 <= abs(normalized) <= 10000000: confidence += 20
                    if re.search(r'page|p\.\d+|\d{1,3}\s*$', context_window, re.IGNORECASE): confidence += 10
                    # Priority bonus: first pattern = highest priority
                    if pat_idx == 0: confidence += 50
                    # Prefer larger absolute values (more likely to be real totals)
                    if abs(raw_val) > 10000: confidence += 15
                    
                    if confidence > best_confidence:
                        best = normalized
                        best_raw = raw_val
                        best_confidence = confidence
                        # Snippet must come from fin_section, not full_text
                        snippet_start = max(0, m.start()-80)
                        best_snippet = "..." + fin_section[snippet_start:m.end()+80] + "..."
                        best_unit = unit
            
            if best is not None:
                if best_confidence >= 70: conf_label = "HIGH"
                elif best_confidence >= 40: conf_label = "MEDIUM"
                else: conf_label = "LOW"
                
                results[field] = {
                    "label": field,
                    "value": best,
                    "raw_value": best_raw,
                    "unit": best_unit,
                    "unit_normalized": "Cr",
                    "confidence": conf_label,
                    "confidence_score": best_confidence,
                    "snippet": best_snippet,
                    "year": year
                }
                logger.info(f"FinancialExtractor: {field}={best} Cr [{conf_label} conf={best_confidence}] unit={best_unit}")
        
        # Auditor Extraction — search only the last 20% of text
        # (real auditor signature is near the end of the auditor's report)
        tail_start = int(len(text) * 0.8)
        tail_text = text[tail_start:]
        norm_text = re.sub(r'\s+', ' ', tail_text)
        aud_match = re.search(self.auditor_pattern, norm_text)
        if aud_match:
            firm_name = aud_match.group(1).strip()
            firm_name = re.sub(r'(?i)(?:firm|registration).*$', '', firm_name).strip(' ,.')
            if len(firm_name) < 100:
                start_idx = max(0, aud_match.start() - 30)
                end_idx = min(len(norm_text), aud_match.end() + 30)
                surrounding = norm_text[start_idx:end_idx].strip()
                results["Auditor Name"] = {
                    "label": "Auditor Name",
                    "value": firm_name,
                    "unit": "string",
                    "snippet": f"...{surrounding}...",
                    "year": year
                }
        return results

    def _get_financial_section(self, full_text: str) -> str:
        text_lower = full_text.lower()
        markers = [
            "statement of profit and loss",
            "profit and loss account",
            "income statement",
        ]
        for marker in markers:
            idx = text_lower.find(marker)
            if idx == -1:
                continue
            # Keep searching until we find an occurrence NOT followed by
            # page-number-like content (i.e. the actual statement, not TOC)
            search_from = idx
            while True:
                candidate = text_lower.find(marker, search_from)
                if candidate == -1:
                    break
                # Check the 200 chars after this match
                snippet = text_lower[candidate:candidate + 200]
                # TOC entries have digits immediately after (page refs)
                # Real P&L pages have column headers like 'note', 'particulars', 'amount'
                if any(x in snippet for x in ['particulars', 'note no', 'for the year', 'rupees', '₹']):
                    logger.info(f"FinancialExtractor: P&L at idx={candidate} via '{marker}'")
                    return full_text[candidate:candidate + 20000]
                search_from = candidate + 500
        
        logger.warning("FinancialExtractor: P&L section NOT FOUND — falling back to full text")
        return full_text
