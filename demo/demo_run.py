"""Demo runner for supply-chain risk MVP."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "backend" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from supply_chain_risk.module import run_supply_chain_risk  # noqa: E402


def _run_report(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    result = run_supply_chain_risk(text)
    print(f"\n=== {path.name} ===")
    print(json.dumps(result, indent=2))


def main() -> None:
    sample_paths = [
        ROOT / "sample_data" / "sample_report_1.txt",
        ROOT / "sample_data" / "sample_report_2.txt",
    ]
    for sample_path in sample_paths:
        _run_report(sample_path)


if __name__ == "__main__":
    main()
