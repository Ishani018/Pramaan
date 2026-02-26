"""
Deep Reader Agent – Gemini 1.5 Pro Extractor
=============================================
Sends pre-chunked section text to the Gemini 1.5 Pro API and extracts
two specific credit-risk signals:

  1. CARO 2020 Clause (vii) – statutory defaults (PF, ESI, TDS, GST, etc.)
  2. Auditor qualifications – "Except for…" or "Adverse" opinions

This is the ONLY component that makes an LLM call.
Everything else in the Deep Reader is fully deterministic.
Every finding is returned with a source_excerpt so judges can verify it.
"""
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured output schema returned by this extractor
# ---------------------------------------------------------------------------
def _empty_result() -> Dict[str, Any]:
    return {
        "caro_2020_defaults": [],
        "auditor_qualifications": [],
        "gemini_model_used": None,
        "extraction_status": "not_run",
        "error": None,
    }


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def _build_prompt(auditors_text: str, notes_text: str) -> str:
    combined = ""
    if auditors_text.strip():
        combined += f"=== INDEPENDENT AUDITOR'S REPORT ===\n{auditors_text[:12000]}\n\n"
    if notes_text.strip():
        combined += f"=== NOTES TO FINANCIAL STATEMENTS ===\n{notes_text[:12000]}\n\n"

    if not combined.strip():
        return ""

    return f"""You are a senior credit analyst reviewing an Indian corporate annual report.
Extract ONLY the following two categories of findings from the provided text. 
Be precise and quote the source text directly. Return ONLY valid JSON — no markdown, no preamble.

TEXT TO ANALYSE:
{combined}

Return this exact JSON structure:
{{
  "caro_2020_defaults": [
    {{
      "clause": "CARO 2020 Clause (vii)",
      "description": "<what statutory dues are overdue — PF, ESI, TDS, GST, Customs, etc.>",
      "amount_if_mentioned": "<amount in INR if stated, else null>",
      "period_of_default": "<financial year or period if mentioned>",
      "source_excerpt": "<exact quote from the text, max 200 chars>"
    }}
  ],
  "auditor_qualifications": [
    {{
      "type": "<'Except for' | 'Adverse' | 'Disclaimer' | 'Emphasis of Matter'>",
      "paragraph_number": "<paragraph or point number if mentioned, else null>",
      "description": "<brief explanation of the qualification or emphasis>",
      "financial_impact": "<quantified impact if stated, else null>",
      "source_excerpt": "<exact quote from the text, max 200 chars>"
    }}
  ]
}}

Rules:
- If there are NO CARO defaults found, return an empty list for "caro_2020_defaults".
- If the auditor opinion is UNQUALIFIED with NO emphasis of matter, return an empty list for "auditor_qualifications".
- Do NOT invent findings. Extract only what is explicitly stated.
- Indian-context: CARO = Companies (Auditor's Report) Order, 2020. Clause (vii) covers statutory dues.
"""


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------
async def extract_credit_signals(
    auditors_report_text: str,
    notes_text: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends the auditor's report and notes sections to Gemini 1.5 Pro.
    Returns structured extraction of CARO defaults and auditor qualifications.

    Args:
        auditors_report_text: Raw text of the Independent Auditor's Report section
        notes_text:           Raw text of the Notes to Financial Statements section
        api_key:              Gemini API key. Falls back to GEMINI_API_KEY env var.

    Returns:
        Dict with keys: caro_2020_defaults, auditor_qualifications,
                        gemini_model_used, extraction_status, error
    """
    result = _empty_result()

    # ── Resolve API key ──────────────────────────────────────────────────────
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        logger.warning(
            "GEMINI_API_KEY not set — Gemini extraction skipped. "
            "Set the env var to enable LLM-powered signal extraction."
        )
        result["extraction_status"] = "skipped_no_api_key"
        result["error"] = (
            "GEMINI_API_KEY environment variable not set. "
            "Structured extraction from CARO 2020 and auditor qualifications was skipped."
        )
        return result

    # ── Build prompt ─────────────────────────────────────────────────────────
    prompt = _build_prompt(auditors_report_text, notes_text)
    if not prompt:
        result["extraction_status"] = "skipped_no_text"
        result["error"] = "Both auditor report and notes sections were empty — nothing to send to Gemini."
        return result

    # ── Call Gemini ───────────────────────────────────────────────────────────
    try:
        import google.generativeai as genai
        import json

        genai.configure(api_key=key)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro-latest",
            generation_config=genai.types.GenerationConfig(
                temperature=0.0,      # deterministic — no creativity for credit analysis
                response_mime_type="application/json",
            ),
        )

        logger.info("Sending request to Gemini 1.5 Pro for CARO / auditor signal extraction...")
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Strip accidental markdown code fences
        if raw_text.startswith("```"):
            raw_text = "\n".join(raw_text.split("\n")[1:])
        if raw_text.endswith("```"):
            raw_text = "\n".join(raw_text.split("\n")[:-1])

        parsed: Dict[str, List] = json.loads(raw_text)

        result["caro_2020_defaults"]    = parsed.get("caro_2020_defaults", [])
        result["auditor_qualifications"] = parsed.get("auditor_qualifications", [])
        result["gemini_model_used"]      = "gemini-1.5-pro-latest"
        result["extraction_status"]      = "success"

        logger.info(
            f"Gemini extraction complete — "
            f"{len(result['caro_2020_defaults'])} CARO findings, "
            f"{len(result['auditor_qualifications'])} auditor qualifications"
        )

    except ImportError:
        logger.error("google-generativeai not installed. Run: pip install google-generativeai")
        result["extraction_status"] = "error"
        result["error"] = "google-generativeai package not installed."

    except Exception as exc:
        logger.exception(f"Gemini extraction failed: {exc}")
        result["extraction_status"] = "error"
        result["error"] = str(exc)

    return result
