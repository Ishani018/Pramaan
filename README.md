# Supply Chain Risk MVP (`supply_chain_risk_module`)

This prototype adds a deterministic **Supply Chain Risk** block to CAM/risk memo generation.

It is designed to detect hidden credit risk that may not be visible from borrower financials alone.

## Why this matters

A borrower can look stable on paper but still face elevated repayment risk when:
- upstream suppliers are unstable or concentrated,
- input costs are commodity/weather/import sensitive,
- downstream buyers are concentrated or weak,
- collections are delayed and receivables are stretched.

This MVP evaluates the borrower's immediate value chain (not the full world supply network).

## 3-Block framework

- **Block A (Upstream):** raw material supplier/input-side risk
- **Block B (Borrower):** dependence profile from disclosures
- **Block C (Downstream):** buyer concentration/payment reliability risk

## What the module returns

`run_supply_chain_risk(report_text: str)` returns a dict containing:
- extracted features,
- supplier score + band,
- buyer score + band,
- overall score + band,
- weakest link,
- dashboard summary,
- CAM-ready narrative paragraph,
- reason list and confidence notes.

## Deterministic scoring rules

Supplier score:
- +20 if `commodity_exposure`
- +20 if `weather_exposure` or `import_dependency`
- +20 if `supplier_concentration_high`

Buyer score:
- +25 if `customer_concentration_high`
- +20 if `buyer_payment_risk`
- +15 if `receivables_stretched`
- +10 if `buyer_type_is_weak_or_unorganized`

Overall score:
- `max(supplier_score, buyer_score)`
- add `+10` if both supplier and buyer are at least Moderate

Bands:
- `0-20`: Low
- `21-40`: Moderate
- `41+`: High

## Project structure

```
backend/
  src/
    supply_chain_risk/
    __init__.py
    extractor.py
    rules.py
    formatter.py
    module.py
tests/
  test_supply_chain_risk.py
demo/
  demo_run.py
sample_data/
  sample_report_1.txt
  sample_report_2.txt
README.md
```

## Run demo

From repo root:

```bash
python demo/demo_run.py
```

This runs both sample reports and prints JSON output.

## Run tests

```bash
python -m pytest tests/test_supply_chain_risk.py
```

## MVP limitations

- Uses keyword/regex heuristics only (no ML, no external APIs).
- Works on provided report text; no web scraping or data enrichment.
- Focuses on immediate disclosed counterparties and dependency language.
- If supplier/buyer names are not explicitly disclosed, outputs confidence notes and inference-based flags.
