"""
ML Baseline Model — Base Rate & Limit Predictor
================================================
Uses a scikit-learn RandomForestRegressor trained on synthetic financial ratio data
to predict the INITIAL Base Rate (% p.a.) and Base Limit (₹ Cr) for a borrower.

The deterministic P-01 / P-03 / P-04 / P-05 penalties from the ComplianceScanner
and WebSleuth are applied ON TOP of this ML-predicted base.

Key input features (financial ratios derived from bureau data or officer entry):
  - dscr               : Debt Service Coverage Ratio  (healthy = >1.25)
  - leverage_ratio      : Total Debt / EBITDA           (healthy = <3.5)
  - current_ratio       : Current Assets / Current Liabilities (healthy = >1.2)
  - revenue_growth_pct  : YoY Revenue Growth %          (healthy = >5%)
  - gst_compliance_pct  : % of months with on-time GSTR-3B filing (0-100)
  - promoter_holding_pct: % shares held by promoters    (higher = better alignment)
  - years_in_business   : Age of entity in years        (older = more stable)

Model persistence:
  - Saved to models/ml_baseline.joblib on first train
  - Auto-loaded on subsequent calls
  - If not found, train_dummy_model() is called automatically
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np

logger = logging.getLogger(f"pramaan.{__name__}")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL_DIR  = Path(__file__).parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "ml_baseline.joblib"

FEATURE_NAMES = [
    "dscr",
    "leverage_ratio",
    "current_ratio",
    "revenue_growth_pct",
    "gst_compliance_pct",
    "promoter_holding_pct",
    "years_in_business",
]

# Fallback constants if model fails
FALLBACK_BASE_RATE  = 9.0
FALLBACK_BASE_LIMIT = 10.0

_cached_model = None   # in-memory cache after first load


# ---------------------------------------------------------------------------
# Synthetic training data generator
# ---------------------------------------------------------------------------
def _generate_synthetic_dataset(n_samples: int = 2000):
    """
    Generate synthetic financial ratio → rate/limit dataset.

    Ground-truth rule (manually engineered):
      base_rate  ~ 8.0 + (low DSCR penalty) + (high leverage penalty) - (GST compliance bonus) + noise
      base_limit ~ 12.0 - (leverage penalty) + (DSCR bonus) - (current ratio risk) + noise

    This simulates what a credit committee's historical pricing decisions would look like
    if encoded as training data from a Loan Origination System (LOS).
    """
    rng = np.random.default_rng(42)

    # Generate realistic ranges for each feature
    dscr                = rng.uniform(0.6, 3.5,   n_samples)    # <1 = stress
    leverage_ratio      = rng.uniform(0.5, 8.0,   n_samples)    # >5 = high risk
    current_ratio       = rng.uniform(0.5, 3.0,   n_samples)    # <1 = liquidity stress
    revenue_growth_pct  = rng.uniform(-15, 40,    n_samples)    # negative = shrinking
    gst_compliance_pct  = rng.uniform(40,  100,   n_samples)    # % months filed
    promoter_holding_pct= rng.uniform(20,  75,    n_samples)    # % promoter stake
    years_in_business   = rng.uniform(1,   40,    n_samples)    # entity age

    X = np.column_stack([
        dscr, leverage_ratio, current_ratio,
        revenue_growth_pct, gst_compliance_pct,
        promoter_holding_pct, years_in_business,
    ])

    # Engineered base rate (target 1)
    base_rate = (
        8.5
        + np.clip(1.5 - dscr, 0, 2.0)                        # low DSCR → higher rate
        + np.clip(leverage_ratio - 3.5, 0, 3.0) * 0.3        # high leverage → higher rate
        - np.clip(gst_compliance_pct - 80, 0, 20) * 0.02     # good GST → discount
        - np.clip(revenue_growth_pct, 0, 20) * 0.015         # growth → discount
        + rng.normal(0, 0.3, n_samples)                       # pricing noise
    )
    base_rate = np.clip(base_rate, 7.5, 14.0)

    # Engineered base limit in ₹ Cr (target 2)
    base_limit = (
        10.0
        + np.clip(dscr - 1.0, 0, 2.0) * 2.0                  # good DSCR → higher limit
        - np.clip(leverage_ratio - 3.5, 0, 5.0) * 0.8        # high leverage → lower limit
        + np.clip(current_ratio - 1.2, 0, 1.5) * 1.5         # liquidity buffer → higher limit
        + np.clip(years_in_business - 5, 0, 20) * 0.1        # vintage → higher limit
        + rng.normal(0, 0.5, n_samples)
    )
    base_limit = np.clip(base_limit, 2.0, 25.0)

    return X, base_rate, base_limit


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------
def train_dummy_model(save: bool = True):
    """
    Train a RandomForestRegressor on synthetic data and optionally persist it.
    Called automatically if no saved model is found.

    Returns the trained MultiOutputRegressor (rate + limit).
    """
    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.multioutput import MultiOutputRegressor
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
        import joblib

        logger.info("Training ML baseline model on synthetic financial ratio dataset…")
        X, y_rate, y_limit = _generate_synthetic_dataset(n_samples=2000)
        Y = np.column_stack([y_rate, y_limit])

        model = Pipeline([
            ("scaler", StandardScaler()),
            ("rf", MultiOutputRegressor(
                RandomForestRegressor(
                    n_estimators=120,
                    max_depth=8,
                    min_samples_leaf=10,
                    random_state=42,
                    n_jobs=-1,
                )
            )),
        ])
        model.fit(X, Y)

        if save:
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, MODEL_PATH)
            logger.info(f"ML model saved → {MODEL_PATH}")

        return model

    except ImportError as exc:
        logger.error(f"scikit-learn not installed: {exc}. Run: pip install scikit-learn joblib")
        return None


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
def _load_model():
    """Load from disk if available; otherwise train fresh."""
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    try:
        import joblib
        if MODEL_PATH.exists():
            _cached_model = joblib.load(MODEL_PATH)
            logger.info(f"ML model loaded from {MODEL_PATH}")
        else:
            logger.info("No saved model found — training from scratch…")
            _cached_model = train_dummy_model(save=True)
    except Exception as exc:
        logger.warning(f"Model load failed ({exc}) — will use fallback constants")
        _cached_model = None

    return _cached_model


# ---------------------------------------------------------------------------
# Public prediction API
# ---------------------------------------------------------------------------
def predict_base_terms(financial_ratios: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a dict of financial ratios, predict the ML-recommended Base Rate and Limit.

    Args:
        financial_ratios: dict with keys matching FEATURE_NAMES.
                          Missing features default to sector medians.

    Returns:
        {
          "ml_base_rate_pct":  float,   # ML predicted rate before penalties
          "ml_base_limit_cr":  float,   # ML predicted limit before penalties
          "feature_vector":    list,    # input features used (for transparency)
          "model_status":      str,     # "predicted" | "fallback"
        }
    """
    # Defaults (sector median for Indian mid-market manufacturing)
    defaults = {
        "dscr":                1.3,
        "leverage_ratio":      3.2,
        "current_ratio":       1.35,
        "revenue_growth_pct":  8.0,
        "gst_compliance_pct":  85.0,
        "promoter_holding_pct": 52.0,
        "years_in_business":   12.0,
    }
    defaults.update({k: v for k, v in financial_ratios.items() if k in FEATURE_NAMES})

    feature_vector = [defaults[f] for f in FEATURE_NAMES]

    model = _load_model()
    if model is None:
        return {
            "ml_base_rate_pct": FALLBACK_BASE_RATE,
            "ml_base_limit_cr": FALLBACK_BASE_LIMIT,
            "feature_vector":   feature_vector,
            "model_status":     "fallback_no_model",
        }

    try:
        X     = np.array([feature_vector])
        preds = model.predict(X)[0]
        return {
            "ml_base_rate_pct": round(float(preds[0]), 2),
            "ml_base_limit_cr": round(float(preds[1]), 2),
            "feature_vector":   feature_vector,
            "feature_names":    FEATURE_NAMES,
            "model_status":     "predicted",
        }
    except Exception as exc:
        logger.warning(f"ML prediction failed: {exc} — using fallback")
        return {
            "ml_base_rate_pct": FALLBACK_BASE_RATE,
            "ml_base_limit_cr": FALLBACK_BASE_LIMIT,
            "feature_vector":   feature_vector,
            "model_status":     f"fallback_error:{str(exc)}",
        }


def derive_ratios_from_perfios(perfios_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract / impute financial ratios from a Perfios bureau response.
    In production these would come from the actual Perfios financial data.
    Here we derive proxies from the GST/compliance signals available in the mock.
    """
    mismatch = perfios_data.get("gstr_2a_3b_mismatch_pct", 0)
    filing   = perfios_data.get("gst_filing_consistency", "Regular")

    # Impute from compliance signals
    gst_pct  = 95 if filing == "Regular" else 70
    # Mismatch implies ITC inflation → imputed leverage is higher
    implied_leverage = 3.0 + mismatch * 0.05

    return {
        "gst_compliance_pct": gst_pct,
        "leverage_ratio":     round(implied_leverage, 2),
        # Remaining features → sector median; would come from full financials in production
    }
