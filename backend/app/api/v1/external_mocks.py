"""
Mock External Intelligence APIs
================================
Simulates responses from two third-party bureau APIs used by the Credit Committee.

  GET /api/v1/mock/perfios  – GST reconciliation (Agent A: Capacity / Ghost Input)
  GET /api/v1/mock/karza    – Litigation history (Agent C: Character / Web Sleuth)

These are deterministic mock fixtures. In production they would call the real APIs
and return identical JSON schemas so the orchestrator layer never changes.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/mock", tags=["External Intelligence (Mock)"])


@router.get(
    "/perfios",
    summary="Perfios – GST Reconciliation Mock",
    description=(
        "Simulates a Perfios bureau response for GST-2A vs 3B reconciliation. "
        "gstr_2a_3b_mismatch_pct > 15 triggers Rule P-01 (Ghost Input Trap). "
        "circular_trading_flag indicates suspected circular invoicing patterns."
    ),
)
async def mock_perfios():
    """
    Fixture: 18.5% mismatch → P-01 triggered (+100 bps / −10% limit).
    """
    return {
        "status": "success",
        "provider": "Perfios (mock)",
        "entity": "Acme Steels Pvt Ltd",
        "assessment_period": "FY 2022-23",
        "gstr_2a_3b_mismatch_pct": 18.5,      # > 15% → P-01 Ghost Input Trap
        "circular_trading_flag": False,
        "gst_filing_consistency": "Regular",
        "itc_reversal_required": True,
        "itc_reversal_amount_lakh": 12.4,
        "metadata": {
            "data_freshness": "2023-12-31",
            "rule_triggered": "P-01",
            "trigger_condition": "gstr_2a_3b_mismatch_pct > 15",
        },
    }


@router.get(
    "/karza",
    summary="Karza – Litigation & Director KYB Mock",
    description=(
        "Simulates a Karza bureau response for litigation history and director KYB. "
        "active_litigations is a list of pending legal proceedings. "
        "director_disqualified=true would block approval outright."
    ),
)
async def mock_karza():
    """
    Fixture: One Section 138 cheque bounce case pending — secondary watch flag.
    """
    return {
        "status": "success",
        "provider": "Karza (mock)",
        "entity": "Acme Steels Pvt Ltd",
        "cin": "U27100MH2010PTC123456",
        "active_litigations": [
            "Section 138 NI Act – Cheque Bounce – Pending at JMFC Mumbai"
        ],
        "total_litigation_count": 1,
        "director_disqualified": False,
        "mca_charge_registered": True,
        "charge_amount_cr": 7.0,
        "charge_holders": ["HDFC Bank Ltd"],
        "epfo_compliance": "Regular",
        "metadata": {
            "data_freshness": "2024-01-15",
            "rule_triggered": None,    # litigation alone doesn't auto-trigger a penalty rule
            "watch_flag": "Section 138 pending — credit committee manual note required",
        },
    }


@router.get(
    "/network-graph",
    summary="Network Graph – Circular Trading Fraud Mock",
    description=(
        "Simulates a network intelligence response detecting a circular money-laundering loop. "
        "Returns a node-edge graph showing Acme Steels → Vertex Holdings → Nova Corp → Acme Steels. "
        "circular_trading_detected=true triggers Rule P-06 (Circular Fraud Detected, −50% limit)."
    ),
)
async def mock_network_graph():
    """
    Fixture: Three-entity circular trading loop.
    Acme Steels (applicant) → Vertex Holdings (shell, ₹5.0 Cr)
    → Nova Corp (shell, ₹4.8 Cr) → Acme Steels (₹4.5 Cr back).
    circular_trading_detected=True → P-06 triggered (−50% credit limit).
    """
    return {
        "status": "success",
        "provider": "Network Intelligence (mock)",
        "entity": "Acme Steels Pvt Ltd",
        "circular_trading_detected": True,
        "nodes": [
            {
                "id": "acme",
                "label": "Acme Steels\n(Applicant)",
                "type": "applicant",
                "amount_cr": 5.0,
            },
            {
                "id": "vertex",
                "label": "Vertex Holdings\n(Shell)",
                "type": "shell",
                "amount_cr": 4.8,
            },
            {
                "id": "nova",
                "label": "Nova Corp\n(Shell)",
                "type": "shell",
                "amount_cr": 4.5,
            },
        ],
        "links": [
            {"source": "acme",   "target": "vertex", "value": 5.0, "label": "₹5.0 Cr"},
            {"source": "vertex", "target": "nova",   "value": 4.8, "label": "₹4.8 Cr"},
            {"source": "nova",   "target": "acme",   "value": 4.5, "label": "₹4.5 Cr"},
        ],
        "metadata": {
            "data_freshness": "2024-01-15",
            "rule_triggered": "P-06",
            "trigger_condition": "circular_trading_detected == true",
            "loop_value_cr": 5.0,
        },
    }
