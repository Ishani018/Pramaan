"""
Poison Dataset — Inject synthetic fraud patterns into clean bank statement JSONs.

Takes a clean AgamiAI/Indian-Bank-Statements JSON and injects fraud patterns
that Pramaan's detection pipeline (P-06, P-28, P-29) can actually catch.

Scenarios:
  circular  — Round-trip flows through 2 shell-like counterparties (P-28 + P-06)
  shell     — High-volume transactions with companies that look like shells on MCA
  routing   — Layered round-number transfers to obscure money trail

Usage:
  python poison_dataset.py --input 00001.json --output 00001_circular.csv --scenario circular --format csv
  python poison_dataset.py --input 00001.json --output 00001_circular.json --scenario circular --format json
"""

import json
import csv
import argparse
from datetime import datetime


# ── Fraud transaction templates ──────────────────────────────────────────────
# Each scenario injects transactions whose descriptions are parseable by
# BankStatementAnalyzer._extract_party() (NEFT dash-delimited format).

CIRCULAR_TXNS = [
    # Round-trip 1: Pay out ₹12.5L to VERTEX, get ₹12.45L back 3 days later
    {"date": "2024-02-05 10:15:00", "value_date": "2024-02-05",
     "description": "NEFT Dr-9988776655-HDFC0001234-VERTEX HOLDINGS PVT LTD",
     "debit": 1250000.00, "credit": None},
    {"date": "2024-02-08 14:30:00", "value_date": "2024-02-08",
     "description": "NEFT Cr-1122334455-HDFC0001234-VERTEX HOLDINGS PVT LTD",
     "debit": None, "credit": 1245000.00},

    # Round-trip 2: Pay out ₹8.7L to VERTEX again, get ₹8.65L back
    {"date": "2024-02-20 09:45:00", "value_date": "2024-02-20",
     "description": "RTGS Dr-CNRBR887766554-HDFC0001234-VERTEX HOLDINGS PVT LTD-/NONE",
     "debit": 870000.00, "credit": None},
    {"date": "2024-02-24 11:00:00", "value_date": "2024-02-24",
     "description": "NEFT Cr-5566778899-HDFC0001234-VERTEX HOLDINGS PVT LTD",
     "debit": None, "credit": 865000.00},

    # Round-trip 3: Same pattern with NOVA CORP — ₹15L out, ₹14.9L back
    {"date": "2024-03-01 10:00:00", "value_date": "2024-03-01",
     "description": "NEFT Dr-2233445566-ICIC0005678-NOVA CORP SOLUTIONS PVT LTD",
     "debit": 1500000.00, "credit": None},
    {"date": "2024-03-04 16:20:00", "value_date": "2024-03-04",
     "description": "RTGS Cr-ICICR556677889-ICIC0005678-NOVA CORP SOLUTIONS PVT LTD--/URGENT/",
     "debit": None, "credit": 1490000.00},

    # Round-trip 4: NOVA again — ₹6L out, ₹5.95L back
    {"date": "2024-03-12 08:30:00", "value_date": "2024-03-12",
     "description": "NEFT Dr-6677889900-ICIC0005678-NOVA CORP SOLUTIONS PVT LTD",
     "debit": 600000.00, "credit": None},
    {"date": "2024-03-15 13:45:00", "value_date": "2024-03-15",
     "description": "NEFT Cr-7788990011-ICIC0005678-NOVA CORP SOLUTIONS PVT LTD",
     "debit": None, "credit": 595000.00},
]

SHELL_TXNS = [
    # Large payments to companies with shell-like names (low capital on MCA)
    {"date": "2024-01-15 10:00:00", "value_date": "2024-01-15",
     "description": "NEFT Dr-1111222233-SBIN0009876-ZENITH TRADING ENTERPRISES PVT LTD",
     "debit": 750000.00, "credit": None},
    {"date": "2024-01-22 11:30:00", "value_date": "2024-01-22",
     "description": "NEFT Dr-2222333344-SBIN0009876-ZENITH TRADING ENTERPRISES PVT LTD",
     "debit": 680000.00, "credit": None},
    {"date": "2024-02-10 09:00:00", "value_date": "2024-02-10",
     "description": "NEFT Dr-3333444455-UTIB0004321-PINNACLE INFRA SOLUTIONS LLP",
     "debit": 920000.00, "credit": None},
    {"date": "2024-02-18 14:00:00", "value_date": "2024-02-18",
     "description": "NEFT Cr-4444555566-UTIB0004321-PINNACLE INFRA SOLUTIONS LLP",
     "debit": None, "credit": 900000.00},
    {"date": "2024-03-05 10:30:00", "value_date": "2024-03-05",
     "description": "RTGS Dr-CNRBR998877665-SBIN0009876-ZENITH TRADING ENTERPRISES PVT LTD-/NONE",
     "debit": 1100000.00, "credit": None},
    {"date": "2024-03-08 15:00:00", "value_date": "2024-03-08",
     "description": "NEFT Cr-5555666677-SBIN0009876-ZENITH TRADING ENTERPRISES PVT LTD",
     "debit": None, "credit": 540000.00},
]

ROUTING_TXNS = [
    # Suspicious round-number transfers layered across multiple parties
    {"date": "2024-02-01 10:00:00", "value_date": "2024-02-01",
     "description": "NEFT Dr-7777888899-HDFC0003333-GLOBAL COMMODITIES TRADING LTD",
     "debit": 1000000.00, "credit": None},
    {"date": "2024-02-03 11:00:00", "value_date": "2024-02-03",
     "description": "NEFT Dr-8888999900-HDFC0003333-GLOBAL COMMODITIES TRADING LTD",
     "debit": 1000000.00, "credit": None},
    {"date": "2024-02-05 12:00:00", "value_date": "2024-02-05",
     "description": "NEFT Cr-9999000011-HDFC0003333-GLOBAL COMMODITIES TRADING LTD",
     "debit": None, "credit": 1950000.00},
    {"date": "2024-02-15 09:00:00", "value_date": "2024-02-15",
     "description": "RTGS Dr-CNRBR112233445-ICIC0007777-APEX VENTURES INDIA PVT LTD-/NONE",
     "debit": 2000000.00, "credit": None},
    {"date": "2024-02-17 14:00:00", "value_date": "2024-02-17",
     "description": "RTGS Cr-ICICR223344556-ICIC0007777-APEX VENTURES INDIA PVT LTD--/URGENT/",
     "debit": None, "credit": 1980000.00},
    {"date": "2024-03-01 10:00:00", "value_date": "2024-03-01",
     "description": "NEFT Dr-1010101010-SBIN0005555-NATIONAL RESOURCES CORP LTD",
     "debit": 500000.00, "credit": None},
    {"date": "2024-03-03 16:00:00", "value_date": "2024-03-03",
     "description": "NEFT Cr-2020202020-SBIN0005555-NATIONAL RESOURCES CORP LTD",
     "debit": None, "credit": 495000.00},
]

SCENARIOS = {
    "circular": CIRCULAR_TXNS,
    "shell": SHELL_TXNS,
    "routing": ROUTING_TXNS,
}


def poison_data(input_path: str, output_path: str, scenario: str, out_format: str):
    with open(input_path, "r") as f:
        data = json.load(f)

    fraud_txns = SCENARIOS[scenario]

    # Get a reasonable base balance from the original data
    base_balance = data["transactions"][0]["balance"] if data["transactions"] else 100000.0

    # Build injected transactions with running balances
    injected = []
    running = base_balance + 500000  # Give headroom so balance stays positive
    for tx in fraud_txns:
        debit = tx["debit"] or 0
        credit = tx["credit"] or 0
        running = running - debit + credit
        injected.append({
            "date": tx["date"],
            "value_date": tx["value_date"],
            "description": tx["description"],
            "cheque_no": "",
            "debit": tx["debit"],
            "credit": tx["credit"],
            "balance": round(running, 2),
            "branch_code": "9999",
            "failed": False,
        })

    # Merge: sort all transactions by date
    all_txns = injected + data["transactions"]
    all_txns.sort(key=lambda t: t["date"])

    # Recalculate running balance for the full statement
    balance = data.get("opening_balance", 50000.0)
    for tx in all_txns:
        debit = tx["debit"] or 0
        credit = tx["credit"] or 0
        balance = round(balance - debit + credit, 2)
        tx["balance"] = balance

    data["transactions"] = all_txns

    # Write output
    if out_format == "json":
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
    else:
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Date", "Description", "Debit", "Credit", "Balance"])
            writer.writeheader()
            for tx in all_txns:
                dt_obj = datetime.strptime(tx["date"][:10], "%Y-%m-%d")
                writer.writerow({
                    "Date": dt_obj.strftime("%d-%m-%Y"),
                    "Description": tx["description"],
                    "Debit": tx["debit"] if tx["debit"] else "",
                    "Credit": tx["credit"] if tx["credit"] else "",
                    "Balance": tx["balance"],
                })

    label = scenario.upper()
    n = len(fraud_txns)
    print(f"[+] Poisoned with {label}: {n} transactions injected into {len(all_txns)} total")
    print(f"    Output: {output_path} ({out_format})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inject fraud patterns into clean bank statement JSON")
    parser.add_argument("--input", required=True, help="Path to clean JSON from AgamiAI dataset")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), required=True)
    parser.add_argument("--format", choices=["json", "csv"], default="csv")
    args = parser.parse_args()

    poison_data(args.input, args.output, args.scenario, args.format)
