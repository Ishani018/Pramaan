"""Formatting utilities for dashboard and CAM-ready narratives."""

from __future__ import annotations

from typing import Any


def build_reasons(features: dict[str, Any]) -> list[str]:
    """Build concise explanation reasons from extracted features."""
    reasons: list[str] = []
    if features.get("commodity_exposure"):
        reasons.append("Input costs appear commodity-linked")
    if features.get("weather_exposure"):
        reasons.append("Business shows weather/seasonality sensitivity")
    if features.get("import_dependency"):
        reasons.append("Input sourcing appears import-dependent")
    if features.get("supplier_concentration_high"):
        reasons.append("High supplier concentration detected")
    if features.get("customer_concentration_high"):
        reasons.append("High customer concentration detected")
    if features.get("buyer_payment_risk"):
        reasons.append("Buyer payment reliability concerns are indicated")
    if features.get("receivables_stretched"):
        reasons.append("Trade receivables language suggests payment stretch")
    if features.get("buyer_type_is_weak_or_unorganized"):
        reasons.append("Downstream buyers appear small/unorganized")
    if features.get("single_product_dependency"):
        reasons.append("Revenue appears dependent on a narrow product set")

    if not reasons:
        reasons.append("No strong upstream or downstream stress signals were detected")

    return reasons


def build_confidence_notes(features: dict[str, Any]) -> list[str]:
    """Add confidence notes when details are not explicitly disclosed."""
    notes: list[str] = []
    if not features.get("supplier_identified"):
        notes.append("Supplier not explicitly identified; upstream risk inferred from generic disclosures.")
    if not features.get("buyer_identified"):
        notes.append("Buyer not explicitly identified; risk inferred from customer concentration language.")
    return notes


def dashboard_summary(overall_band: str, weakest_link: str) -> str:
    """Create one-line dashboard summary."""
    return f"Supply Chain Risk: {overall_band} -- Weakest link is {weakest_link}."


def cam_paragraph(
    *,
    overall_band: str,
    weakest_link: str,
    reasons: list[str],
    confidence_notes: list[str],
) -> str:
    """Generate CAM-ready professional paragraph."""
    if overall_band == "Low":
        opening = (
            "Supply-chain risk appears low based on available disclosures. "
            "The borrower does not appear materially dependent on unstable suppliers "
            "or weak downstream counterparties."
        )
    elif overall_band == "Moderate":
        opening = (
            "Supply-chain risk appears moderate due to some dependence on concentrated "
            "suppliers/customers and exposure to input or collection variability."
        )
    else:
        opening = (
            "Supply-chain risk appears high because the borrower's operating stability "
            f"depends on a weak or concentrated link in the value chain, particularly on the {weakest_link.lower()} side."
        )

    reason_text = "Key indicators include " + "; ".join(reasons[:4]) + "."
    notes_text = " " + " ".join(confidence_notes) if confidence_notes else ""
    return opening + " " + reason_text + notes_text
