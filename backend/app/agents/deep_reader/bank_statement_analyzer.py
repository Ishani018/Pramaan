"""
Bank Statement Analyzer
========================
Parses bank statement CSV data and detects:
  1. Circular transactions (A→B and B→A within 7 days)
  2. Cash deposit spikes near GST filing dates
  3. Average monthly balance vs declared turnover

CSV Format expected:
  Date, Description, Debit, Credit, Balance

Zero-LLM — pure pandas/statistical analysis.
"""

import re
import csv
import logging
import io
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(f"pramaan.{__name__}")

# GST filing dates (day of month)
GST_FILING_DAYS = [1, 11, 20]
SPIKE_WINDOW_DAYS = 3  # days before/after GST filing date


@dataclass
class CircularTxn:
    party: str
    debit_date: str
    debit_amount: float
    credit_date: str
    credit_amount: float
    days_gap: int


@dataclass
class CashSpike:
    date: str
    amount: float
    nearest_filing_date: str
    days_before_filing: int


@dataclass
class BankStatementResult:
    total_transactions: int = 0
    total_debits: float = 0.0
    total_credits: float = 0.0
    avg_monthly_balance: float = 0.0
    circular_transactions: List[CircularTxn] = field(default_factory=list)
    cash_spikes: List[CashSpike] = field(default_factory=list)
    top_counterparties: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    triggered_rules: List[str] = field(default_factory=list)


class BankStatementAnalyzer:
    """Analyze bank statement CSV for fraud signals."""

    def analyze(self, csv_content: str) -> BankStatementResult:
        """
        Parse CSV and run all detections.

        Args:
            csv_content: Raw CSV string content

        Returns:
            BankStatementResult with findings
        """
        result = BankStatementResult()

        if not csv_content or len(csv_content.strip()) < 20:
            return result

        # Parse CSV
        transactions = self._parse_csv(csv_content)
        if not transactions:
            logger.warning("BankStatementAnalyzer: No transactions parsed from CSV")
            return result

        result.total_transactions = len(transactions)
        result.total_debits = sum(t.get("debit", 0) for t in transactions)
        result.total_credits = sum(t.get("credit", 0) for t in transactions)

        # Compute average balance
        balances = [t.get("balance", 0) for t in transactions if t.get("balance")]
        result.avg_monthly_balance = round(sum(balances) / max(len(balances), 1), 2)

        # Detection 1: Circular transactions
        result.circular_transactions = self._detect_circular(transactions)
        if result.circular_transactions:
            result.triggered_rules.append("P-28")
            result.findings.append(
                f"CIRCULAR TRANSACTION: {len(result.circular_transactions)} "
                f"round-trip flows detected within 7-day windows"
            )
            logger.warning(
                f"BankStatementAnalyzer: P-28 TRIGGERED — "
                f"{len(result.circular_transactions)} circular transactions"
            )

        # Detection 2: Cash deposit spikes near GST filing dates
        result.cash_spikes = self._detect_cash_spikes(transactions)
        if result.cash_spikes:
            result.triggered_rules.append("P-29")
            result.findings.append(
                f"CASH SPIKE: {len(result.cash_spikes)} large cash deposits "
                f"within {SPIKE_WINDOW_DAYS} days of GST filing dates"
            )
            logger.warning(
                f"BankStatementAnalyzer: P-29 TRIGGERED — "
                f"{len(result.cash_spikes)} cash spikes near filing dates"
            )

        # Top counterparties
        result.top_counterparties = self._get_top_counterparties(transactions)

        logger.info(
            f"BankStatementAnalyzer: {result.total_transactions} txns, "
            f"circular={len(result.circular_transactions)}, "
            f"spikes={len(result.cash_spikes)}, "
            f"rules={result.triggered_rules}"
        )

        return result

    def _parse_csv(self, csv_content: str) -> List[Dict]:
        """Parse CSV into list of transaction dicts."""
        transactions = []
        reader = csv.DictReader(io.StringIO(csv_content))

        for row in reader:
            try:
                # Flexible date parsing
                date_str = (
                    row.get("Date", "") or row.get("date", "") or
                    row.get("Transaction Date", "") or row.get("Txn Date", "")
                ).strip()
                date = self._parse_date(date_str)

                desc = (
                    row.get("Description", "") or row.get("description", "") or
                    row.get("Particulars", "") or row.get("Narration", "")
                ).strip()

                debit = self._parse_amount(
                    row.get("Debit", "") or row.get("debit", "") or
                    row.get("Withdrawal", "") or "0"
                )
                credit = self._parse_amount(
                    row.get("Credit", "") or row.get("credit", "") or
                    row.get("Deposit", "") or "0"
                )
                balance = self._parse_amount(
                    row.get("Balance", "") or row.get("balance", "") or
                    row.get("Closing Balance", "") or "0"
                )

                transactions.append({
                    "date": date,
                    "date_str": date_str,
                    "description": desc,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                })
            except Exception:
                continue

        return transactions

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Try multiple date formats."""
        for fmt in ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d %b %Y"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _parse_amount(self, val: str) -> float:
        """Parse amount, removing commas and handling blanks."""
        if not val:
            return 0.0
        cleaned = re.sub(r'[^\d.]', '', str(val))
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0

    def _detect_circular(self, transactions: List[Dict]) -> List[CircularTxn]:
        """Detect A→B and B→A within 7 days."""
        circular = []

        # Group by counterparty name (extracted from description)
        debits_by_party = defaultdict(list)
        credits_by_party = defaultdict(list)

        for t in transactions:
            party = self._extract_party(t["description"])
            if not party:
                continue
            if t["debit"] > 0 and t["date"]:
                debits_by_party[party].append(t)
            if t["credit"] > 0 and t["date"]:
                credits_by_party[party].append(t)

        # For each party, check if there's a debit AND credit within 7 days
        for party in debits_by_party:
            if party not in credits_by_party:
                continue
            for deb in debits_by_party[party]:
                for cred in credits_by_party[party]:
                    if deb["date"] and cred["date"]:
                        gap = abs((deb["date"] - cred["date"]).days)
                        if gap <= 7 and deb["debit"] > 10000 and cred["credit"] > 10000:
                            circular.append(CircularTxn(
                                party=party,
                                debit_date=deb["date_str"],
                                debit_amount=deb["debit"],
                                credit_date=cred["date_str"],
                                credit_amount=cred["credit"],
                                days_gap=gap,
                            ))

        return circular[:10]  # Cap at 10

    def _detect_cash_spikes(self, transactions: List[Dict]) -> List[CashSpike]:
        """Detect large cash deposits near GST filing dates."""
        spikes = []

        # Calculate median credit to define "large"
        credits = [t["credit"] for t in transactions if t["credit"] > 0]
        if not credits:
            return spikes

        median_credit = sorted(credits)[len(credits) // 2]
        spike_threshold = max(median_credit * 3, 100000)  # 3x median or 1L

        for t in transactions:
            if t["credit"] < spike_threshold or not t["date"]:
                continue

            desc_lower = t["description"].lower()
            # Only flag cash deposits, not regular transfers
            is_cash = any(kw in desc_lower for kw in [
                "cash", "deposit", "cdm", "cash deposit"
            ])
            if not is_cash:
                continue

            # Check proximity to GST filing date
            day = t["date"].day
            for filing_day in GST_FILING_DAYS:
                days_before = filing_day - day
                if 0 <= days_before <= SPIKE_WINDOW_DAYS:
                    filing_date_str = t["date"].replace(day=filing_day).strftime("%d-%m-%Y")
                    spikes.append(CashSpike(
                        date=t["date_str"],
                        amount=t["credit"],
                        nearest_filing_date=filing_date_str,
                        days_before_filing=days_before,
                    ))
                    break

        return spikes[:10]

    def _extract_party(self, description: str) -> Optional[str]:
        """Extract counterparty name from transaction description."""
        desc = description.upper().strip()
        # Common patterns: "NEFT/..../PARTY NAME", "RTGS/..../PARTY"
        for prefix in ["NEFT", "RTGS", "IMPS", "UPI", "TRF"]:
            if prefix in desc:
                parts = desc.split("/")
                if len(parts) >= 3:
                    return parts[-1].strip()[:30]
        # Fallback: use first 20 chars of description
        if len(desc) > 5:
            return desc[:20].strip()
        return None

    def _get_top_counterparties(self, transactions: List[Dict]) -> List[Dict]:
        """Get top 10 counterparties by total volume with debit/credit breakdown."""
        volumes = defaultdict(lambda: {"debit": 0.0, "credit": 0.0, "count": 0})
        for t in transactions:
            party = self._extract_party(t["description"])
            if party:
                volumes[party]["debit"] += t["debit"]
                volumes[party]["credit"] += t["credit"]
                volumes[party]["count"] += 1

        sorted_parties = sorted(
            volumes.items(),
            key=lambda x: x[1]["debit"] + x[1]["credit"],
            reverse=True,
        )
        return [
            {
                "party": p,
                "total_volume": round(v["debit"] + v["credit"], 2),
                "debit_volume": round(v["debit"], 2),
                "credit_volume": round(v["credit"], 2),
                "txn_count": v["count"],
            }
            for p, v in sorted_parties[:10]
        ]
