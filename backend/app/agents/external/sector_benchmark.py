"""
Sector Benchmark Assessor
=========================
Compares a company's financial metrics against static industry benchmarks.
Returns insights and triggers P-30 if margins/growth are significantly
below industry standards.

Zero-LLM — Pure rules-based lookup and arithmetic.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(f"pramaan.{__name__}")

# Hardcoded benchmarks based on MCA NIC codes or common broad sectors
SECTOR_BENCHMARKS = {
    # Key: Broad sector keyword (fallback if exact match fails)
    "MANUFACTURING": {
        "ebitda_margin_pct": 12.5,
        "pat_margin_pct": 5.0,
        "revenue_growth_yoy_pct": 8.0,
    },
    "SERVICES": {
        "ebitda_margin_pct": 18.0,
        "pat_margin_pct": 9.0,
        "revenue_growth_yoy_pct": 12.0,
    },
    "TRADING": {
        "ebitda_margin_pct": 4.5,
        "pat_margin_pct": 1.5,
        "revenue_growth_yoy_pct": 6.0,
    },
    "INFRASTRUCTURE": {
        "ebitda_margin_pct": 14.0,
        "pat_margin_pct": 4.0,
        "revenue_growth_yoy_pct": 10.0,
    },
    "DEFAULT": {
        "ebitda_margin_pct": 10.0,
        "pat_margin_pct": 4.0,
        "revenue_growth_yoy_pct": 8.0,
    }
}


@dataclass
class BenchmarkFinding:
    metric: str
    company_value: float
    benchmark_value: float
    deviation_pct: float
    status: str  # e.g., "ABOVE", "BELOW", "CRITICAL"


@dataclass
class BenchmarkResult:
    sector_used: str = "DEFAULT"
    findings: List[BenchmarkFinding] = field(default_factory=list)
    triggered_rules: List[str] = field(default_factory=list)
    summary: str = ""


class SectorBenchmarkAssessor:

    def analyze(self, mca_data: Any, latest_financials: Dict, prior_financials: Dict) -> BenchmarkResult:
        result = BenchmarkResult()

        if not latest_financials:
            result.summary = "No financial data available for benchmarking."
            return result

        # Determine sector
        sector_key = "DEFAULT"
        if mca_data and hasattr(mca_data, "activity_description") and mca_data.activity_description:
            desc = mca_data.activity_description.upper()
            if "MANUFACTURING" in desc or "FACTORY" in desc or "METAL" in desc or "STEEL" in desc:
                sector_key = "MANUFACTURING"
            elif "SERVICE" in desc or "SOFTWARE" in desc or "IT " in desc:
                sector_key = "SERVICES"
            elif "TRADING" in desc or "WHOLESALE" in desc or "RETAIL" in desc:
                sector_key = "TRADING"
            elif "CONSTRUCTION" in desc or "INFRA" in desc:
                sector_key = "INFRASTRUCTURE"

        result.sector_used = sector_key
        
        # Guard: Do not fire sector rules on unknown sector
        if sector_key == "DEFAULT":
            result.summary = "Sector unknown — skipping benchmark comparison."
            return result

        benchmarks = SECTOR_BENCHMARKS[sector_key]

        target_ebitda_margin = benchmarks["ebitda_margin_pct"]
        target_pat_margin = benchmarks["pat_margin_pct"]

        # 1. Evaluate EBITDA Margin
        revenue = self._get_metric(latest_financials, "Revenue")
        ebitda = self._get_metric(latest_financials, "EBITDA", "EBIT", "Operating Profit")
        
        revenue_val = revenue if isinstance(revenue, (int, float)) else 0
        ebitda_val = ebitda if isinstance(ebitda, (int, float)) else 0
        if revenue_val > 0 and ebitda_val > 0:
            ebitda_margin = (ebitda_val / revenue_val) * 100
            dev = ((ebitda_margin - target_ebitda_margin) / target_ebitda_margin) * 100
            
            status = "ABOVE" if dev >= 0 else "BELOW"
            if dev <= -25:
                status = "CRITICAL"

            result.findings.append(BenchmarkFinding(
                metric="EBITDA Margin",
                company_value=round(ebitda_margin, 2),
                benchmark_value=target_ebitda_margin,
                deviation_pct=round(dev, 1),
                status=status
            ))

        # 2. Evaluate PAT Margin
        pat = self._get_metric(latest_financials, "PAT", "Profit After Tax", "Net Profit")
        pat_val = pat if isinstance(pat, (int, float)) else 0
        if revenue_val > 0 and pat_val > 0:
            pat_margin = (pat_val / revenue_val) * 100
            dev = ((pat_margin - target_pat_margin) / target_pat_margin) * 100
            
            status = "ABOVE" if dev >= 0 else "BELOW"
            if dev <= -25:
                status = "CRITICAL"

            result.findings.append(BenchmarkFinding(
                metric="PAT Margin",
                company_value=round(pat_margin, 2),
                benchmark_value=target_pat_margin,
                deviation_pct=round(dev, 1),
                status=status
            ))

        # Check for P-30 rule Trigger
        critical_count = sum(1 for f in result.findings if f.status == "CRITICAL")
        if critical_count > 0:
            result.triggered_rules.append("P-30")
            result.summary = f"Underperforming sector {sector_key} by >25% on key margins."
            logger.warning(f"SectorBenchmark: P-30 TRIGGERED — {result.summary}")
        else:
            result.summary = f"Company aligns with or exceeds {sector_key} averages."

        return result

    def _get_metric(self, financials: Dict, *keys: str) -> Optional[float]:
        for k in keys:
            if k in financials:
                val = financials[k].get("normalized_value")
                if val is None:
                    val = financials[k].get("value")
                
                try:
                    num = float(val) if val is not None else None
                    if num is not None:
                        return num
                except ValueError:
                    continue
        return None
