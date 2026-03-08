import json
import random
from datetime import datetime, timedelta
import argparse
import os
import csv

def poison_data(input_path, output_path, scenario, out_format):
    with open(input_path, 'r') as f:
        data = json.load(f)

    applicant_name = data.get("account_holder", "Applicant")
    applicant_addr = data.get("account_holder_address", "")
    
    # Injected transactions will use this date range to ensure they are "recent" in the dataset context
    # Dataset 00001 is Q1 2024
    
    if scenario == "circular":
        # Scenario: Applicant -> Vertex -> Nova -> Applicant (P-06 / P-28)
        data["transactions"].insert(0, {
            "date": "2024-03-20 10:00:00",
            "value_date": "2024-03-20",
            "description": "NEFT Dr-9988776655-HDFC0001234-VERTEX HOLDINGS PVT LTD",
            "cheque_no": "",
            "debit": 1250000.00,
            "credit": None,
            "balance": data["transactions"][0]["balance"] - 1250000.00,
            "branch_code": "9999",
            "failed": False
        })
        data["transactions"].insert(1, {
            "date": "2024-03-22 14:00:00",
            "value_date": "2024-03-22",
            "description": "NEFT Cr-0099112233-ICIC0005678-NOVA CORP SOLUTIONS",
            "cheque_no": "",
            "debit": None,
            "credit": 1245000.00,
            "balance": data["transactions"][0]["balance"] + 1245000.00,
            "branch_code": "9999",
            "failed": False
        })
        print(f"Poisoned with CIRCULAR TRADING (Vertex -> Nova)")

    elif scenario == "shell":
        # Scenario: Counterparty has same address as Applicant (P-06 Network Intel)
        data["transactions"].insert(0, {
            "date": "2024-03-15 09:00:00",
            "value_date": "2024-03-15",
            "description": f"IMPS Dr-5544332211-SHELL ENTITIES LTD (SAME ADDR: {applicant_addr.splitlines()[0]})",
            "cheque_no": "",
            "debit": 500000.00,
            "credit": None,
            "balance": data["transactions"][0]["balance"] - 500000.00,
            "branch_code": "9999",
            "failed": False
        })
        print(f"Poisoned with SHELL COMPANY (Common Address)")

    elif scenario == "routing":
        # Scenario: Suspicious round number transfers (P-08 / P-28 details)
        for i in range(5):
            data["transactions"].insert(i, {
                "date": f"2024-03-{10+i} 11:00:00",
                "value_date": f"2024-03-{10+i}",
                "description": f"NEFT Dr-RTGS-ROUND-TRIP-TEST-{i}/SUSPICIOUS PARTY",
                "cheque_no": "",
                "debit": 1000000.00,
                "credit": None,
                "balance": data["transactions"][0]["balance"] - 1000000.00,
                "branch_code": "9999",
                "failed": False
            })
        print(f"Poisoned with SUSPICIOUS ROUTING (Round Numbers)")

    if out_format == "json":
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        # CSV Format: Date, Description, Debit, Credit, Balance
        with open(output_path, 'w', newline='') as f:
            fieldnames = ["Date", "Description", "Debit", "Credit", "Balance"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for tx in data["transactions"]:
                # Normalize date to DD-MM-YYYY
                dt_obj = datetime.strptime(tx["date"][:10], "%Y-%m-%d")
                writer.writerow({
                    "Date": dt_obj.strftime("%d-%m-%Y"),
                    "Description": tx["description"],
                    "Debit": tx["debit"] if tx["debit"] else "",
                    "Credit": tx["credit"] if tx["credit"] else "",
                    "Balance": tx["balance"]
                })

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--scenario", choices=["circular", "shell", "routing"], required=True)
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    args = parser.parse_args()
    
    poison_data(args.input, args.output, args.scenario, args.format)

