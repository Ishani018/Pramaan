"""Deterministic scoring rules for supply-chain risk."""

from __future__ import annotations

from typing import Any


def score_to_band(score: int) -> str:
    """Map score into risk bands."""
    if score <= 20:
        return "Low"
    if score <= 40:
        return "Moderate"
    return "High"


def _weakest_link(supplier_score: int, buyer_score: int) -> str:
    if buyer_score > supplier_score:
        return "Buyer concentration and payment reliability"
    if supplier_score > buyer_score:
        return "Input/supplier-side dependence"
    return "Both upstream and downstream dependencies"


def calculate_risk_scores(features: dict[str, Any]) -> dict[str, Any]:
    """Calculate supplier, buyer, and overall supply-chain risk."""
    supplier_score = 0
    buyer_score = 0

    if features.get("commodity_exposure", False):
        supplier_score += 20
    if features.get("weather_exposure", False) or features.get("import_dependency", False):
        supplier_score += 20
    if features.get("supplier_concentration_high", False):
        supplier_score += 20

    if features.get("customer_concentration_high", False):
        buyer_score += 25
    if features.get("buyer_payment_risk", False):
        buyer_score += 20
    if features.get("receivables_stretched", False):
        buyer_score += 15
    if features.get("buyer_type_is_weak_or_unorganized", False):
        buyer_score += 10

    overall_score = max(supplier_score, buyer_score)
    if score_to_band(supplier_score) in {"Moderate", "High"} and score_to_band(buyer_score) in {
        "Moderate",
        "High",
    }:
        overall_score += 10
    overall_score = min(100, overall_score)

    return {
        "supplier_risk_score": supplier_score,
        "supplier_risk_band": score_to_band(supplier_score),
        "buyer_risk_score": buyer_score,
        "buyer_risk_band": score_to_band(buyer_score),
        "overall_supply_chain_risk_score": overall_score,
        "overall_supply_chain_risk_band": score_to_band(overall_score),
        "weakest_link": _weakest_link(supplier_score, buyer_score),
    }
