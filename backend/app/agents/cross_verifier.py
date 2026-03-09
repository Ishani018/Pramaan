"""
Cross-Verifier
===============
Takes claims extracted from the annual report and verifies them against
external data sources (bank statements, Perfios/GST, CIBIL, Karza, MCA,
eCourts, news, site visit, sector benchmarks).

Produces a structured verification report with MATCH / MISMATCH / PARTIAL_MATCH
/ UNVERIFIABLE status for each claim-source pair.
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Statuses
MATCH = "MATCH"
MISMATCH = "MISMATCH"
PARTIAL = "PARTIAL_MATCH"
UNVERIFIABLE = "UNVERIFIABLE"

# Severities
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
INFO = "INFO"


class CrossVerifier:

    def verify(
        self,
        claims: Dict[str, Dict[str, Any]],
        bank_result: Optional[Any] = None,
        perfios_data: Optional[Dict] = None,
        cibil_data: Optional[Dict] = None,
        karza_data: Optional[Dict] = None,
        mca_data: Optional[Any] = None,
        ecourts_data: Optional[Dict] = None,
        news_data: Optional[Dict] = None,
        site_visit_result: Optional[Any] = None,
        benchmark_result: Optional[Any] = None,
    ) -> Dict[str, Any]:
        verifications: List[Dict] = []

        # Revenue verification
        if "revenue" in claims:
            verifications.append(self._verify_revenue(
                claims["revenue"], bank_result, perfios_data))

        # Profitability verification
        if "profitability" in claims:
            verifications.append(self._verify_profitability(
                claims["profitability"], benchmark_result))

        # Statutory defaults verification
        if "no_statutory_defaults" in claims:
            verifications.append(self._verify_defaults(
                claims["no_statutory_defaults"], cibil_data, karza_data))

        # Going concern verification
        if "going_concern" in claims:
            verifications.append(self._verify_going_concern(
                claims["going_concern"], news_data, cibil_data))

        # Credit rating verification
        if "credit_rating" in claims:
            verifications.append(self._verify_credit_rating(
                claims["credit_rating"], cibil_data))

        # Litigation verification
        if "litigation_status" in claims:
            verifications.append(self._verify_litigation(
                claims["litigation_status"], ecourts_data, karza_data))

        # Promoter stability verification
        if "promoter_stability" in claims:
            verifications.append(self._verify_promoter(claims["promoter_stability"]))

        # Management outlook verification
        if "management_outlook" in claims:
            verifications.append(self._verify_outlook(
                claims["management_outlook"], site_visit_result))

        # Compute summary
        summary = self._compute_summary(verifications)
        triggered_rules = self._compute_triggered_rules(verifications)

        logger.info(
            f"Cross-verification complete: {summary['verified']} verified, "
            f"{summary['mismatched']} mismatched, {summary['partial']} partial, "
            f"{summary['unverifiable']} unverifiable"
        )

        return {
            "verifications": verifications,
            "summary": summary,
            "triggered_rules": triggered_rules,
        }

    # ── Revenue ─────────────────────────────────────────────────────────────

    def _verify_revenue(self, claim, bank_result, perfios_data):
        checks = []
        revenue_val = claim.get("value", 0)

        # Check 1: Bank statement credits vs claimed revenue
        if bank_result and hasattr(bank_result, "total_credits") and bank_result.total_credits > 0:
            credits_cr = bank_result.total_credits / 1_00_00_000  # Convert from Rs to Cr
            if revenue_val > 0:
                ratio = credits_cr / revenue_val
                if ratio >= 0.90:
                    status, severity = MATCH, INFO
                    finding = (f"Bank deposits: {credits_cr:,.1f} Cr "
                               f"({ratio:.0%} of claimed revenue)")
                    detail = "Bank credits are consistent with reported revenue."
                elif ratio >= 0.70:
                    status, severity = PARTIAL, MEDIUM
                    finding = (f"Bank deposits: {credits_cr:,.1f} Cr "
                               f"({ratio:.0%} of claimed revenue)")
                    detail = (f"Bank credits are {(1-ratio):.0%} below claimed revenue. "
                              f"Some gap is normal (multi-bank, inter-company) but warrants review.")
                else:
                    status, severity = MISMATCH, HIGH
                    gap = revenue_val - credits_cr
                    finding = (f"Bank deposits: {credits_cr:,.1f} Cr "
                               f"(only {ratio:.0%} of claimed revenue)")
                    detail = (f"Bank credits {gap:,.1f} Cr below claimed revenue — "
                              f"a {(1-ratio):.0%} shortfall suggesting revenue inflation "
                              f"or collections routed through undisclosed accounts.")
            else:
                status, severity = UNVERIFIABLE, LOW
                finding = f"Bank deposits: {credits_cr:,.1f} Cr"
                detail = "Revenue not extracted from annual report; cannot compare."
            checks.append(self._check("Bank Statement", "bank", finding, status, severity, detail))
        else:
            checks.append(self._check(
                "Bank Statement", "bank",
                "No bank statement provided",
                UNVERIFIABLE, LOW,
                "Upload a bank statement CSV to verify revenue against actual deposits."))

        # Check 2: Perfios / GST mismatch
        if perfios_data and perfios_data.get("status") == "success":
            mismatch_pct = perfios_data.get("gstr_2a_3b_mismatch_pct", 0)
            if mismatch_pct > 15:
                status, severity = MISMATCH, HIGH
                finding = f"GST 2A vs 3B mismatch: {mismatch_pct}%"
                detail = (f"GSTR-2A/3B gap of {mismatch_pct}% indicates invoices claimed "
                          f"as input tax credit may not have corresponding supplier filings. "
                          f"Suggests potential ghost invoicing or inflated purchases.")
            elif mismatch_pct > 5:
                status, severity = PARTIAL, MEDIUM
                finding = f"GST 2A vs 3B mismatch: {mismatch_pct}%"
                detail = (f"Moderate GST mismatch of {mismatch_pct}%. Some gap is normal "
                          f"(timing differences) but above comfortable threshold.")
            else:
                status, severity = MATCH, INFO
                finding = f"GST 2A vs 3B mismatch: {mismatch_pct}% (within limits)"
                detail = "GST filings are consistent with supplier data."
            checks.append(self._check("Perfios / GST", "gst", finding, status, severity, detail))
        else:
            checks.append(self._check(
                "Perfios / GST", "gst",
                "GST reconciliation data not available",
                UNVERIFIABLE, LOW,
                "Perfios GST data not available for verification."))

        return self._verification_entry("revenue", claim["claim"], checks)

    # ── Profitability ───────────────────────────────────────────────────────

    def _verify_profitability(self, claim, benchmark_result):
        checks = []
        if benchmark_result and hasattr(benchmark_result, "sector_used"):
            comparisons = getattr(benchmark_result, "comparisons", {})
            ebitda_cmp = comparisons.get("ebitda_margin") or comparisons.get("ebitda")
            if ebitda_cmp:
                deviation = ebitda_cmp.get("deviation_pct", 0)
                if deviation < -25:
                    status, severity = MISMATCH, HIGH
                    finding = f"EBITDA margin {abs(deviation):.0f}% below sector benchmark"
                    detail = "Significant underperformance vs sector peers raises questions about reported profitability."
                elif deviation < -10:
                    status, severity = PARTIAL, MEDIUM
                    finding = f"EBITDA margin {abs(deviation):.0f}% below sector average"
                    detail = "Moderate underperformance vs sector — not alarming but notable."
                else:
                    status, severity = MATCH, INFO
                    finding = "EBITDA margin in line with sector benchmark"
                    detail = "Reported profitability is consistent with industry performance."
                checks.append(self._check("Sector Benchmark", "benchmark", finding, status, severity, detail))
            else:
                checks.append(self._check(
                    "Sector Benchmark", "benchmark",
                    "EBITDA benchmark data not available",
                    UNVERIFIABLE, LOW,
                    "Sector comparison could not be performed for profitability."))
        else:
            checks.append(self._check(
                "Sector Benchmark", "benchmark",
                "Sector benchmark not available",
                UNVERIFIABLE, LOW,
                "No sector benchmark data to compare profitability against."))

        return self._verification_entry("profitability", claim["claim"], checks)

    # ── Statutory defaults ──────────────────────────────────────────────────

    def _verify_defaults(self, claim, cibil_data, karza_data):
        checks = []
        ar_clean = claim.get("clean", True)

        # CIBIL check
        if cibil_data and cibil_data.get("status") == "success":
            dpd_30 = cibil_data.get("dpd_30_count", 0)
            dpd_90 = cibil_data.get("dpd_90_count", 0)
            suit_filed = cibil_data.get("suit_filed_amount_cr", 0)

            if dpd_90 > 0 or suit_filed > 0:
                status = MISMATCH if ar_clean else MATCH
                severity = HIGH if ar_clean else INFO
                finding = f"CIBIL: {dpd_30} DPD-30, {dpd_90} DPD-90, suit filed {suit_filed} Cr"
                detail = ("Bureau data shows payment defaults and/or suit filed — "
                          "contradicts clean compliance claim in annual report."
                          if ar_clean else
                          "Bureau data confirms compliance issues flagged in auditor report.")
            elif dpd_30 > 0:
                status = PARTIAL if ar_clean else MATCH
                severity = MEDIUM if ar_clean else INFO
                finding = f"CIBIL: {dpd_30} instances of 30-day past due"
                detail = ("Minor payment delays detected in bureau data. "
                          "Not severe but inconsistent with clean compliance narrative."
                          if ar_clean else
                          "Bureau data shows minor delays, consistent with auditor flags.")
            else:
                status = MATCH
                severity = INFO
                finding = "CIBIL: No DPD or suits filed"
                detail = "Bureau data confirms clean payment history."
            checks.append(self._check("CIBIL Bureau", "cibil", finding, status, severity, detail))
        else:
            checks.append(self._check(
                "CIBIL Bureau", "cibil", "CIBIL data not available",
                UNVERIFIABLE, LOW, "Credit bureau data not available for verification."))

        # Karza check
        if karza_data and karza_data.get("status") == "success":
            disqualified = karza_data.get("director_disqualified", False)
            epfo = karza_data.get("epfo_compliance", "Unknown")
            litigations = karza_data.get("active_litigations", [])

            issues = []
            if disqualified:
                issues.append("director disqualified")
            if epfo not in ("Regular", "Unknown"):
                issues.append(f"EPFO: {epfo}")

            if issues:
                status = MISMATCH if ar_clean else MATCH
                severity = HIGH if ar_clean else INFO
                finding = f"Karza: {', '.join(issues)}"
                detail = "Registry data shows compliance issues not disclosed in annual report." if ar_clean else "Consistent with auditor findings."
            else:
                status = MATCH
                severity = INFO
                finding = f"Karza: EPFO {epfo}, no director disqualification"
                detail = "Company registry confirms clean compliance status."
            checks.append(self._check("Karza Registry", "karza", finding, status, severity, detail))
        else:
            checks.append(self._check(
                "Karza Registry", "karza", "Karza data not available",
                UNVERIFIABLE, LOW, "Karza registry data not available."))

        return self._verification_entry("no_statutory_defaults", claim["claim"], checks)

    # ── Going concern ───────────────────────────────────────────────────────

    def _verify_going_concern(self, claim, news_data, cibil_data):
        checks = []
        ar_clean = claim.get("clean", True)

        # News check
        if news_data and news_data.get("adverse_media_detected"):
            red_flags = news_data.get("red_flags", [])
            concern_keywords = ["winding up", "nclt", "insolvency", "bankruptcy", "closure"]
            has_concern_flags = any(
                any(kw in (rf.get("headline", "") + rf.get("summary", "")).lower()
                    for kw in concern_keywords)
                for rf in red_flags
            )
            if has_concern_flags:
                status = MISMATCH if ar_clean else MATCH
                severity = HIGH if ar_clean else MEDIUM
                finding = f"Adverse media: {len(red_flags)} red flag article(s) with going-concern signals"
                detail = "News reports mention insolvency/NCLT proceedings — contradicts going concern assumption." if ar_clean else "Media confirms concerns already flagged by auditor."
            else:
                status = PARTIAL if ar_clean else MATCH
                severity = MEDIUM
                finding = f"Adverse media detected ({len(red_flags)} articles) but no going-concern keywords"
                detail = "Negative press found but not specifically about business continuity."
            checks.append(self._check("News / Media", "news", finding, status, severity, detail))
        elif news_data:
            checks.append(self._check(
                "News / Media", "news",
                "No adverse media detected",
                MATCH, INFO,
                "Media scan found no negative reports about the company."))
        else:
            checks.append(self._check(
                "News / Media", "news", "News data not available",
                UNVERIFIABLE, LOW, "News scan not performed."))

        # CIBIL credit score as going concern proxy
        if cibil_data and cibil_data.get("status") == "success":
            score = cibil_data.get("credit_score", 0)
            if score < 40:
                status = MISMATCH if ar_clean else MATCH
                severity = HIGH
                finding = f"CIBIL score: {score}/100 (distressed)"
                detail = "Very low credit score signals severe financial stress — going concern risk."
            elif score < 60:
                status = PARTIAL
                severity = MEDIUM
                finding = f"CIBIL score: {score}/100 (below average)"
                detail = "Below-average credit score suggests financial strain."
            else:
                status = MATCH
                severity = INFO
                finding = f"CIBIL score: {score}/100 (adequate)"
                detail = "Credit score does not indicate going concern risk."
            checks.append(self._check("CIBIL Score", "cibil", finding, status, severity, detail))

        return self._verification_entry("going_concern", claim["claim"], checks)

    # ── Credit rating ───────────────────────────────────────────────────────

    def _verify_credit_rating(self, claim, cibil_data):
        checks = []
        ar_rating = claim.get("rating", "")
        ar_inv_grade = claim.get("is_investment_grade", None)

        if cibil_data and cibil_data.get("status") == "success":
            bureau_rating = cibil_data.get("rating", "")
            if ar_rating and bureau_rating:
                # Simple grade comparison
                ar_upper = ar_rating.upper().replace(" ", "")
                bureau_upper = bureau_rating.upper().replace(" ", "")
                if ar_upper == bureau_upper:
                    status, severity = MATCH, INFO
                    finding = f"Bureau rating {bureau_rating} matches AR disclosure"
                    detail = "Credit rating confirmed by independent bureau."
                else:
                    # Check if both are same grade tier
                    inv_grades = {"AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"}
                    ar_inv = ar_upper in inv_grades
                    bureau_inv = bureau_upper in inv_grades
                    if ar_inv != bureau_inv:
                        status, severity = MISMATCH, HIGH
                        finding = f"Bureau rating {bureau_rating} vs AR disclosed {ar_rating} — grade tier mismatch"
                        detail = ("Annual report claims investment grade but bureau shows sub-investment, "
                                  "or vice versa. Significant discrepancy." )
                    else:
                        status, severity = PARTIAL, MEDIUM
                        finding = f"Bureau rating {bureau_rating} vs AR disclosed {ar_rating}"
                        detail = "Ratings differ but within same tier. May reflect timing or agency differences."
                checks.append(self._check("CIBIL Rating", "cibil", finding, status, severity, detail))
            else:
                checks.append(self._check(
                    "CIBIL Rating", "cibil",
                    "Rating comparison not possible",
                    UNVERIFIABLE, LOW,
                    "Either AR or bureau rating not available for comparison."))
        else:
            checks.append(self._check(
                "CIBIL Rating", "cibil", "Bureau data not available",
                UNVERIFIABLE, LOW, "CIBIL data not available for rating verification."))

        return self._verification_entry("credit_rating", claim["claim"], checks)

    # ── Litigation ──────────────────────────────────────────────────────────

    def _verify_litigation(self, claim, ecourts_data, karza_data):
        checks = []
        ar_clean = claim.get("clean", True)

        # eCourts check
        if ecourts_data:
            high_risk = ecourts_data.get("high_risk_cases", 0)
            total_cases = ecourts_data.get("cases_found", 0)
            if high_risk > 0 and ar_clean:
                status, severity = MISMATCH, HIGH
                finding = f"eCourts: {high_risk} high-risk case(s) out of {total_cases} total"
                detail = "Court records show material litigation not adequately disclosed in annual report."
            elif total_cases > 0 and ar_clean:
                status, severity = PARTIAL, MEDIUM
                finding = f"eCourts: {total_cases} case(s) found, {high_risk} high-risk"
                detail = "Some court proceedings found — annual report may understate litigation exposure."
            elif total_cases > 0:
                status, severity = MATCH, INFO
                finding = f"eCourts: {total_cases} case(s) found"
                detail = "Court cases consistent with disclosures in auditor report."
            else:
                status, severity = MATCH, INFO
                finding = "eCourts: No cases found"
                detail = "Court records confirm clean litigation status."
            checks.append(self._check("eCourts", "ecourts", finding, status, severity, detail))
        else:
            checks.append(self._check(
                "eCourts", "ecourts", "Court data not available",
                UNVERIFIABLE, LOW, "eCourts scan not performed."))

        # Karza litigation check
        if karza_data and karza_data.get("status") == "success":
            litigations = karza_data.get("active_litigations", [])
            if litigations and ar_clean:
                status, severity = PARTIAL, MEDIUM
                finding = f"Karza: {len(litigations)} active litigation(s)"
                detail = f"Registry shows: {'; '.join(litigations[:3])}. Annual report does not flag these."
            elif litigations:
                status, severity = MATCH, INFO
                finding = f"Karza: {len(litigations)} active litigation(s)"
                detail = "Consistent with auditor disclosures."
            else:
                status, severity = MATCH, INFO
                finding = "Karza: No active litigations"
                detail = "Registry confirms clean litigation status."
            checks.append(self._check("Karza Litigation", "karza", finding, status, severity, detail))

        return self._verification_entry("litigation_status", claim["claim"], checks)

    # ── Promoter stability ──────────────────────────────────────────────────

    def _verify_promoter(self, claim):
        checks = []
        pledged = claim.get("pledged_pct", 0)
        holding = claim.get("holding_pct", 0)

        if holding > 0:
            if pledged > 50:
                status, severity = MISMATCH, HIGH
                finding = f"Promoter pledge: {pledged:.1f}% of holding"
                detail = ("Over half of promoter shares are pledged — "
                          "signals financial stress and potential forced liquidation risk.")
            elif pledged > 20:
                status, severity = PARTIAL, MEDIUM
                finding = f"Promoter pledge: {pledged:.1f}% of holding"
                detail = "Significant share pledge warrants monitoring."
            else:
                status, severity = MATCH, INFO
                finding = f"Promoter pledge: {pledged:.1f}% — within acceptable limits"
                detail = "Promoter shareholding appears stable."
            checks.append(self._check("Shareholding Pattern", "shareholding", finding, status, severity, detail))

            if holding < 26:
                checks.append(self._check(
                    "Shareholding Pattern", "shareholding",
                    f"Low promoter holding: {holding:.1f}%",
                    PARTIAL, MEDIUM,
                    "Promoter holding below 26% raises control and commitment concerns."))
        else:
            checks.append(self._check(
                "Shareholding Pattern", "shareholding",
                "Shareholding data not extracted",
                UNVERIFIABLE, LOW,
                "Could not extract shareholding details from annual report."))

        return self._verification_entry("promoter_stability", claim["claim"], checks)

    # ── Management outlook ──────────────────────────────────────────────────

    def _verify_outlook(self, claim, site_visit_result):
        checks = []
        sentiment_label = claim.get("sentiment_label", "neutral")

        if site_visit_result and hasattr(site_visit_result, "findings") and site_visit_result.findings:
            adverse_count = len(site_visit_result.findings)
            if sentiment_label == "positive" and adverse_count > 0:
                status, severity = MISMATCH, MEDIUM
                finding = f"Site visit: {adverse_count} adverse finding(s) vs positive MD&A tone"
                detail = ("Management projects optimism in MD&A but site visit reveals operational "
                          "issues — narrative may be misleading.")
            elif adverse_count > 0:
                status, severity = MATCH, INFO
                finding = f"Site visit: {adverse_count} finding(s), consistent with cautious MD&A tone"
                detail = "Site visit findings align with management's measured outlook."
            else:
                status, severity = MATCH, INFO
                finding = "Site visit: No adverse findings"
                detail = "On-ground observations support management claims."
            checks.append(self._check("Site Visit", "site_visit", finding, status, severity, detail))
        else:
            checks.append(self._check(
                "Site Visit", "site_visit",
                "No site visit data available",
                UNVERIFIABLE, LOW,
                "Site visit not conducted or no notes provided."))

        return self._verification_entry("management_outlook", claim["claim"], checks)

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _check(source, source_icon, finding, status, severity, detail):
        return {
            "source": source,
            "source_icon": source_icon,
            "finding": finding,
            "status": status,
            "severity": severity,
            "detail": detail,
        }

    @staticmethod
    def _verification_entry(claim_id, claim_text, checks):
        statuses = [c["status"] for c in checks]
        severities = [c["severity"] for c in checks]

        # Overall status = worst case
        if MISMATCH in statuses:
            overall_status = MISMATCH
        elif PARTIAL in statuses:
            overall_status = PARTIAL
        elif MATCH in statuses:
            overall_status = MATCH
        else:
            overall_status = UNVERIFIABLE

        sev_order = {HIGH: 0, MEDIUM: 1, LOW: 2, INFO: 3}
        overall_severity = min(severities, key=lambda s: sev_order.get(s, 99)) if severities else INFO

        return {
            "claim_id": claim_id,
            "claim_text": claim_text,
            "checks": checks,
            "overall_status": overall_status,
            "overall_severity": overall_severity,
        }

    @staticmethod
    def _compute_summary(verifications):
        total = len(verifications)
        verified = sum(1 for v in verifications if v["overall_status"] == MATCH)
        mismatched = sum(1 for v in verifications if v["overall_status"] == MISMATCH)
        partial = sum(1 for v in verifications if v["overall_status"] == PARTIAL)
        unverifiable = sum(1 for v in verifications if v["overall_status"] == UNVERIFIABLE)
        return {
            "total_claims": total,
            "verified": verified,
            "mismatched": mismatched,
            "partial": partial,
            "unverifiable": unverifiable,
        }

    @staticmethod
    def _compute_triggered_rules(verifications):
        rules = []
        has_revenue_mismatch = False
        has_compliance_mismatch = False

        for v in verifications:
            if v["overall_status"] == MISMATCH:
                if v["claim_id"] == "revenue":
                    has_revenue_mismatch = True
                elif v["claim_id"] in ("no_statutory_defaults", "litigation_status",
                                        "credit_rating", "going_concern"):
                    has_compliance_mismatch = True

        if has_revenue_mismatch:
            rules.append("P-31")
        if has_compliance_mismatch:
            rules.append("P-32")
        return rules
