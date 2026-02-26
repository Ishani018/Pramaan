"""
FinancialExtractor
==================
Regex-based extraction of key financial figures from annual report text.
Zero-LLM implementation for consistent, deterministic scraping.
"""

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class FinancialExtractor:
    """
    Extracts high-level financials and metadata purely via deterministic regex.
    """
    def __init__(self):
        # Numeric extraction helper:
        # Group 1 captures the first number (current year)
        # Group 2 optionally captures a second number immediately following (previous year)
        num_core = r'-?\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?'
        self.num_pattern = rf'({num_core})(?:[\s\n]+({num_core}))?'
        
        # Look for words like Crore, Cr, Millions, etc to capture the unit
        self.unit_pattern = r'(?i)\b(crores?|cr\.?|millions?|lakhs?|inr|rs\.?|₹)\b'
        
        self.patterns = {
            "Revenue": [
                r'(?i)revenue\s+from\s+operations.*?[:\s]+(?:rs\.?|inr|₹)?\s*' + self.num_pattern,
                r'(?i)total\s+income.*?[:\s]+(?:rs\.?|inr|₹)?\s*' + self.num_pattern
            ],
            "EBITDA": [
                r'(?i)(?:ebitda|operating\s+profit).*?[:\s]+(?:rs\.?|inr|₹)?\s*' + self.num_pattern
            ],
            "PAT": [
                r'(?i)(?:pat|profit\s+after\s+tax|net\s+profit\s+for\s+the\s+period/year|net\s+profit).*?[:\s]+(?:rs\.?|inr|₹)?\s*' + self.num_pattern
            ],
            "Total Debt": [
                r'(?i)(?:total\s+debt|borrowings|total\s+borrowings).*?[:\s]+(?:rs\.?|inr|₹)?\s*' + self.num_pattern
            ],
            "Net Worth": [
                r'(?i)(?:net\s+worth|total\s+equity|shareholders?\s+funds?).*?[:\s]+(?:rs\.?|inr|₹)?\s*' + self.num_pattern
            ]
        }
        
        # Auditor firm name usually follows "For " right before the partner signature
        self.auditor_pattern = r'(?i)for\s+([a-zA-Z\s&,\.]+chartered\s+accountants|[a-zA-Z\s&,\.]+associates|m/s[\s\.][a-zA-Z\s&,\.]+)'

    def extract(self, text: str, year: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Scan the text for each figure and return a structured dictionary.
        Returns None for keys that couldn't be found.
        """
        results = {
            "Revenue": None,
            "EBITDA": None,
            "PAT": None,
            "Total Debt": None,
            "Net Worth": None,
            "Auditor Name": None
        }

        # Normalize text to collapse excessive whitespace for regex matching
        norm_text = re.sub(r'\s+', ' ', text)

        for label, regex_list in self.patterns.items():
            for regex in regex_list:
                match = re.search(regex, norm_text)
                if match:
                    raw_val = match.group(1).replace(',', '').replace(' ', '')
                    raw_prev_val = match.group(2).replace(',', '').replace(' ', '') if match.group(2) else None
                    
                    try:
                        val = float(raw_val)
                        prev_val = float(raw_prev_val) if raw_prev_val else None
                    except ValueError:
                        continue # Failed to parse as float, try next pattern or move on
                    
                    # Try to look around the match to find the unit
                    start_idx = max(0, match.start() - 50)
                    end_idx = min(len(norm_text), match.end() + 50)
                    surrounding = norm_text[start_idx:end_idx].strip()
                    
                    unit = "unknown"
                    unit_match = re.search(self.unit_pattern, surrounding)
                    if unit_match:
                        unit = unit_match.group(1).lower().replace('.', '')
                        if unit in ['cr', 'crores', 'crore']:
                            unit = 'crore'
                        elif unit in ['lakh', 'lakhs']:
                            unit = 'lakh'
                        elif unit in ['million', 'millions']:
                            unit = 'million'
                            
                    res_dict = {
                        "label": label,
                        "value": val,
                        "unit": unit,
                        "snippet": f"...{surrounding}...",
                        "year": year
                    }
                    if prev_val is not None:
                        res_dict["previous_value"] = prev_val
                        
                    results[label] = res_dict
                    break # Found it, stop trying fallback patterns for this label

        # Extract auditor
        aud_match = re.search(self.auditor_pattern, norm_text)
        if aud_match:
            firm_name = aud_match.group(1).strip()
            # Clean up trailing garbage if regex over-captured
            firm_name = re.sub(r'(?i)(?:firm|registration).*$', '', firm_name).strip(' ,.')
            # Limit length just in case
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
