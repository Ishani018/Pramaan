import requests, re, logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(f"pramaan.{__name__}")

@dataclass
class ECourtsResult:
    entity_name: str = ""
    cases_found: int = 0
    cases: List[dict] = field(default_factory=list)
    high_risk_cases: int = 0
    triggered_rules: List[str] = field(default_factory=list)
    findings: List[dict] = field(default_factory=list)
    source: str = "eCourts Public API"

HIGH_RISK_KEYWORDS = [
    "winding up", "insolvency", "nclt", "nclat",
    "fraud", "cheque bounce", "section 138",
    "money laundering", "pmla", "enforcement directorate",
    "sfio", "recovery", "debt recovery tribunal",
    "drt", "sarfaesi", "npa", "wilful defaulter"
]

class ECourtsScanner:

    def scan(self, entity_name: str) -> ECourtsResult:
        result = ECourtsResult(entity_name=entity_name)
        try:
            url = "https://api.ecourts.gov.in/pnc/appdet.php"
            params = {
                "cino": "",
                "party_name": entity_name,
                "case_type": "",
                "court_complex_code": "",
                "est_code": ""
            }
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
            response = requests.get(
                url, params=params,
                headers=headers, timeout=5)
            logger.info(
                f"ECourtsScanner: HTTP {response.status_code} "
                f"for '{entity_name}'")

            if response.status_code == 200:
                data = response.json()
                cases = data.get("cases",
                        data.get("data", []))
                result.cases_found = len(cases)

                for case in cases[:10]:
                    title = (
                        case.get("case_title", "") or
                        case.get("title", "") or
                        case.get("party_name", "")
                    ).lower()

                    is_high_risk = any(
                        kw in title
                        for kw in HIGH_RISK_KEYWORDS)

                    if is_high_risk:
                        result.high_risk_cases += 1
                        result.findings.append({
                            "signal": f"High-risk case: {case.get('case_title', 'Unknown')}",
                            "court": case.get("court_name", ""),
                            "filing_date": case.get("filing_date", ""),
                            "severity": "HIGH"
                        })

                if result.high_risk_cases > 0:
                    result.triggered_rules.append("P-15")
                    logger.warning(
                        f"ECourtsScanner: P-15 TRIGGERED — "
                        f"{result.high_risk_cases} high-risk cases")

                logger.info(
                    f"ECourtsScanner: {result.cases_found} cases, "
                    f"{result.high_risk_cases} high-risk")
            else:
                logger.warning(
                    f"ECourtsScanner: non-200 response, "
                    f"status={response.status_code}, "
                    f"body={response.text[:200]}")

        except Exception as e:
            logger.warning(f"ECourtsScanner: API unreachable — requires NIC network access (Error: {e})")

        return result
