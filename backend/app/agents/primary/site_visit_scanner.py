from dataclasses import dataclass, field
from typing import List
import re, logging

logger = logging.getLogger(f"pramaan.{__name__}")

@dataclass
class SiteVisitScanResult:
    triggered_rules: List[str] = field(default_factory=list)
    findings: List[dict] = field(default_factory=list)
    notes_provided: bool = False
    capacity_utilisation_pct: int = None

class SiteVisitScanner:
    def scan(self, notes: str) -> SiteVisitScanResult:
        result = SiteVisitScanResult()
        if not notes or not notes.strip():
            return result
        
        result.notes_provided = True
        notes_lower = notes.lower()
        
        # Capacity utilisation
        match = re.search(r'(\d+)\s*%\s*capac', notes, re.IGNORECASE)
        if match:
            pct = int(match.group(1))
            result.capacity_utilisation_pct = pct
            if pct < 60:
                result.triggered_rules.append("P-07")
                result.findings.append({
                    "signal": f"Plant operating at {pct}% capacity",
                    "threshold": "Below 60% is high risk",
                    "severity": "HIGH" if pct < 40 else "MEDIUM"
                })
        
        # Management red flags
        red_flags = {
            "management evasive": "Management was evasive during interview",
            "books not available": "Books of accounts unavailable for inspection",
            "factory closed": "Factory found non-operational",
            "workers absent": "Significant worker absenteeism observed",
            "post-dated cheques": "Post-dated cheques issued — liquidity concern",
            "director unavailable": "Promoter/Director unavailable for meeting",
            "attached by bank": "Assets attached by lending bank",
            "stock not found": "Inventory levels inconsistent with records",
            "machinery idle": "Machinery found idle — capacity concern",
            "no orders": "No confirmed order book visible"
        }
        
        for phrase, description in red_flags.items():
            if phrase in notes_lower:
                result.triggered_rules.append("P-07")
                result.findings.append({
                    "signal": description,
                    "severity": "HIGH"
                })
        
        result.triggered_rules = list(set(result.triggered_rules))
        logger.info(f"SiteVisitScanner: {len(result.findings)} signals, rules={result.triggered_rules}")
        return result
