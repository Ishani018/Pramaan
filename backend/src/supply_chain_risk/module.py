"""Public module orchestration for supply-chain risk MVP."""

from __future__ import annotations

from typing import Any

from .extractor import extract_features
from .formatter import build_confidence_notes, build_reasons, cam_paragraph, dashboard_summary
from .rules import calculate_risk_scores


FEATURE_KEYS_FOR_OUTPUT = [
    "supplier_identified",
    "buyer_identified",
    "commodity_exposure",
    "weather_exposure",
    "import_dependency",
    "supplier_concentration_high",
    "customer_concentration_high",
    "buyer_payment_risk",
    "receivables_stretched",
    "single_product_dependency",
]


def run_supply_chain_risk(report_text: str) -> dict[str, Any]:
    """Run the full deterministic supply-chain risk workflow."""
    features = extract_features(report_text)
    scores = calculate_risk_scores(features)
    reasons = build_reasons(features)
    confidence_notes = build_confidence_notes(features)

    result: dict[str, Any] = {
        "major_supplier": features.get("major_supplier") or "Not explicitly identified",
        "major_buyer": features.get("major_buyer") or "Not explicitly identified",
        **scores,
        "features": {key: bool(features.get(key, False)) for key in FEATURE_KEYS_FOR_OUTPUT},
        "reasons": reasons,
        "confidence_notes": confidence_notes,
    }

    result["dashboard_summary"] = dashboard_summary(
        result["overall_supply_chain_risk_band"],
        result["weakest_link"],
    )
    result["cam_paragraph"] = cam_paragraph(
        overall_band=result["overall_supply_chain_risk_band"],
        weakest_link=result["weakest_link"],
        reasons=reasons,
        confidence_notes=confidence_notes,
    )
    return result


class SupplyChainRiskModule:
    """Simple class wrapper for easier integration in larger pipelines."""

    def run(self, report_text: str) -> dict[str, Any]:
        return run_supply_chain_risk(report_text)
