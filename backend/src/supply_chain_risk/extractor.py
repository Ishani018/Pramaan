"""Deterministic feature extraction for supply-chain risk signals."""

from __future__ import annotations

import re
from typing import Any


def _clean_item(item: str) -> str:
    cleaned = re.sub(r"\s+", " ", item).strip(" .,:;\n\t")
    return cleaned


def _split_list_text(value: str) -> list[str]:
    parts = re.split(r",| and |/|;", value)
    items = [_clean_item(part) for part in parts if _clean_item(part)]
    return items[:6]


def _extract_named_entity(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = _clean_item(match.group(1))
            if re.search(
                r"\b(concentration|accounts? for|contributed|reported|remained|increased)\b",
                candidate,
                flags=re.IGNORECASE,
            ):
                continue
            return candidate
    return None


def _extract_list_after_label(text: str, labels: list[str]) -> list[str]:
    for label in labels:
        pattern = rf"{label}\s*[:\-]\s*([^\.\n]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _split_list_text(match.group(1))
    return []


def _contains_any(text: str, keywords: list[str]) -> bool:
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), text, flags=re.IGNORECASE):
            start = match.start()
            window = text[max(0, start - 35) : start]
            if re.search(r"(no|not|without|nil|none|absence of)[^\.;,\n]{0,25}$", window, flags=re.IGNORECASE):
                continue
            return True
    return False


def _extract_percent_near_keyword(text: str, keyword: str) -> int | None:
    pattern = rf"{keyword}[^%\n]{{0,80}}?(\d{{1,3}})\s*%"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _receivable_days_jump(text: str) -> bool:
    patterns = [
        r"receivable(?:s)?\s+days\s+(?:increased|rose)\s+from\s+(\d+)\s+to\s+(\d+)",
        r"collection\s+period\s+(?:increased|rose)\s+from\s+(\d+)\s+to\s+(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            old_days = int(match.group(1))
            new_days = int(match.group(2))
            if new_days - old_days >= 10:
                return True
    return False


def extract_features(report_text: str) -> dict[str, Any]:
    """Extract deterministic supply-chain features from annual-report text."""
    text = re.sub(r"\s+", " ", report_text).strip()
    lowered = text.lower()

    major_supplier = _extract_named_entity(
        text,
        patterns=[
            r"major supplier(?:s)?\s*(?:include|is|are)\s*[:\-]?\s*([^\.\n]+)",
            r"key supplier(?:s)?\s*(?:include|is|are)\s*[:\-]?\s*([^\.\n]+)",
            r"principal supplier(?:s)?\s*(?:include|is|are)\s*[:\-]?\s*([^\.\n]+)",
        ],
    )
    major_buyer = _extract_named_entity(
        text,
        patterns=[
            r"major customer(?:s)?\s*(?:include|is|are)\s*[:\-]?\s*([^\.\n]+)",
            r"key customer(?:s)?\s*(?:include|is|are)\s*[:\-]?\s*([^\.\n]+)",
            r"major buyer(?:s)?\s*(?:include|is|are)\s*[:\-]?\s*([^\.\n]+)",
            r"top customer(?:s)?\s*(?:include|is|are)\s*[:\-]?\s*([^\.\n]+)",
        ],
    )

    major_products = _extract_list_after_label(
        text,
        labels=["major products", "principal products", "products"],
    )
    principal_raw_materials = _extract_list_after_label(
        text,
        labels=["principal raw materials", "raw materials", "key inputs", "major inputs"],
    )

    commodity_exposure = _contains_any(
        lowered,
        [
            "commodity",
            "commodity prices",
            "input price volatility",
            "volatile raw material prices",
            "price fluctuation in steel",
            "price fluctuation in crude",
            "agri commodity",
        ],
    )
    weather_exposure = _contains_any(
        lowered,
        ["weather", "monsoon", "seasonal", "seasonality", "rainfall", "climate"],
    )
    import_dependency = _contains_any(
        lowered,
        [
            "import dependence",
            "import dependency",
            "imported raw material",
            "dependent on imports",
            "foreign supplier",
        ],
    )

    supplier_concentration_high = _contains_any(
        lowered,
        [
            "supplier concentration",
            "single supplier",
            "few suppliers",
            "limited supplier base",
            "concentrated supplier",
        ],
    )
    supplier_percent = _extract_percent_near_keyword(text, "top supplier")
    if supplier_percent is not None and supplier_percent >= 50:
        supplier_concentration_high = True

    customer_concentration_high = _contains_any(
        lowered,
        [
            "customer concentration",
            "concentrated customer",
            "few customers",
            "single customer",
            "top 2 customers",
            "top two customers",
        ],
    )
    customer_percent = _extract_percent_near_keyword(text, "top customer")
    if customer_percent is not None and customer_percent >= 40:
        customer_concentration_high = True

    buyer_payment_risk = _contains_any(
        lowered,
        [
            "delayed payment",
            "payment delays",
            "slow collections",
            "overdue receivables",
            "collection challenges",
            "extended credit period",
            "payment reliability",
            "receivable risk",
            "collections remained weak",
        ],
    )
    receivables_stretched = _contains_any(
        lowered,
        [
            "trade receivables increased",
            "receivables increased",
            "stretched receivables",
            "high receivable days",
            "collection period increased",
            "debtor days increased",
        ],
    ) or _receivable_days_jump(text)

    buyer_type_is_weak_or_unorganized = _contains_any(
        lowered,
        [
            "unorganized buyers",
            "small buyers",
            "local traders",
            "fragmented buyer base",
            "small retailers",
            "informal channel",
        ],
    )

    single_product_dependency = _contains_any(
        lowered,
        [
            "single product",
            "single-product",
            "majority of revenue from one product",
            "dependence on one product",
        ],
    )

    features: dict[str, Any] = {
        "major_products": major_products,
        "principal_raw_materials": principal_raw_materials,
        "major_supplier": major_supplier,
        "major_buyer": major_buyer,
        "supplier_identified": bool(major_supplier),
        "buyer_identified": bool(major_buyer),
        "commodity_exposure": commodity_exposure,
        "weather_exposure": weather_exposure,
        "import_dependency": import_dependency,
        "supplier_concentration_high": supplier_concentration_high,
        "customer_concentration_high": customer_concentration_high,
        "buyer_payment_risk": buyer_payment_risk,
        "receivables_stretched": receivables_stretched,
        "buyer_type_is_weak_or_unorganized": buyer_type_is_weak_or_unorganized,
        "single_product_dependency": single_product_dependency,
    }
    return features
