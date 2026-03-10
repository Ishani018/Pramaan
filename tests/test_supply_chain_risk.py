from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "backend" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from supply_chain_risk.extractor import extract_features
from supply_chain_risk.module import run_supply_chain_risk
from supply_chain_risk.rules import calculate_risk_scores, score_to_band


def test_extractor_flags_high_buyer_risk() -> None:
    text = (
        "Top 2 customers account for 70% of revenue. "
        "Trade receivables increased. Receivable days increased from 60 to 85. "
        "Delayed payments were seen from key customers. "
        "Sales are via small buyers and local traders."
    )
    features = extract_features(text)

    assert features["customer_concentration_high"] is True
    assert features["buyer_payment_risk"] is True
    assert features["receivables_stretched"] is True
    assert features["buyer_type_is_weak_or_unorganized"] is True


def test_score_calculation_matches_rule_weights() -> None:
    features = {
        "commodity_exposure": True,
        "weather_exposure": False,
        "import_dependency": True,
        "supplier_concentration_high": True,
        "customer_concentration_high": True,
        "buyer_payment_risk": True,
        "receivables_stretched": False,
        "buyer_type_is_weak_or_unorganized": False,
    }
    scores = calculate_risk_scores(features)

    assert scores["supplier_risk_score"] == 60
    assert scores["buyer_risk_score"] == 45
    assert scores["overall_supply_chain_risk_score"] == 70


def test_band_calculation() -> None:
    assert score_to_band(0) == "Low"
    assert score_to_band(20) == "Low"
    assert score_to_band(21) == "Moderate"
    assert score_to_band(40) == "Moderate"
    assert score_to_band(41) == "High"


def test_weakest_link_logic_prefers_buyer_when_dominant() -> None:
    features = {
        "commodity_exposure": False,
        "weather_exposure": False,
        "import_dependency": False,
        "supplier_concentration_high": False,
        "customer_concentration_high": True,
        "buyer_payment_risk": True,
        "receivables_stretched": True,
        "buyer_type_is_weak_or_unorganized": False,
    }
    scores = calculate_risk_scores(features)
    assert scores["weakest_link"] == "Buyer concentration and payment reliability"


def test_final_output_shape_contains_required_fields() -> None:
    sample_text = (ROOT / "sample_data" / "sample_report_2.txt").read_text(encoding="utf-8")
    result = run_supply_chain_risk(sample_text)

    required_keys = {
        "major_supplier",
        "major_buyer",
        "supplier_risk_score",
        "supplier_risk_band",
        "buyer_risk_score",
        "buyer_risk_band",
        "overall_supply_chain_risk_score",
        "overall_supply_chain_risk_band",
        "weakest_link",
        "features",
        "dashboard_summary",
        "cam_paragraph",
        "reasons",
        "confidence_notes",
    }
    assert required_keys.issubset(set(result.keys()))
    assert isinstance(result["features"], dict)
    assert isinstance(result["dashboard_summary"], str)
    assert isinstance(result["cam_paragraph"], str)
