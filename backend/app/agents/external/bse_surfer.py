"""
BSE Annual Report Surfer
=========================
Fetches company listings and annual report PDFs from BSE India's
undocumented web API (same endpoints the BSE website uses).
"""
import logging
from typing import List, Dict, Any
from dataclasses import dataclass, field

import requests
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(f"pramaan.{__name__}")

BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bseindia.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.bseindia.com",
}

TIMEOUT = 10


@dataclass
class BSECompany:
    scrip_code: str = ""
    company_name: str = ""
    status: str = ""
    group: str = ""
    industry: str = ""


@dataclass
class BSEAnnualReport:
    year: str = ""
    title: str = ""
    pdf_url: str = ""
    date: str = ""


class BSESurfer:
    """Proxy client for BSE India's web API."""

    SEARCH_URL = "https://api.bse-india.com/BseIndiaAPI/api/Suggest/w"
    FILINGS_URL = "https://api.bse-india.com/BseIndiaAPI/api/AnnualReport/w"

    async def search_company(self, query: str) -> List[BSECompany]:
        """Search BSE for companies matching query string."""
        try:
            results = await run_in_threadpool(self._search_sync, query)
            return results
        except Exception as e:
            logger.warning(f"BSE search failed for '{query}': {e}")
            return []

    def _search_sync(self, query: str) -> List[BSECompany]:
        resp = requests.get(
            self.SEARCH_URL,
            params={"q": query},
            headers=BSE_HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        companies = []
        # BSE Suggest API returns a flat list of pipe-delimited strings
        # Format: "scrip_code|company_name|status|group|industry|..."
        if isinstance(data, list):
            for item in data[:15]:
                if isinstance(item, str):
                    parts = item.split("|")
                    if len(parts) >= 2:
                        companies.append(BSECompany(
                            scrip_code=parts[0].strip(),
                            company_name=parts[1].strip(),
                            status=parts[2].strip() if len(parts) > 2 else "",
                            group=parts[3].strip() if len(parts) > 3 else "",
                            industry=parts[4].strip() if len(parts) > 4 else "",
                        ))
                elif isinstance(item, dict):
                    companies.append(BSECompany(
                        scrip_code=str(item.get("scrip_code", item.get("ScripCode", ""))),
                        company_name=item.get("company_name", item.get("LongName", item.get("SCRIP_CD", ""))),
                        status=item.get("status", item.get("Status", "")),
                        group=item.get("group", item.get("Scrip_grp", "")),
                        industry=item.get("industry", item.get("Industry", "")),
                    ))

        logger.info(f"BSE search '{query}' → {len(companies)} results")
        return companies

    async def get_annual_reports(self, scrip_code: str) -> List[BSEAnnualReport]:
        """Fetch annual report filings for a given scrip code."""
        try:
            results = await run_in_threadpool(self._filings_sync, scrip_code)
            return results
        except Exception as e:
            logger.warning(f"BSE filings failed for scrip {scrip_code}: {e}")
            return []

    def _filings_sync(self, scrip_code: str) -> List[BSEAnnualReport]:
        resp = requests.get(
            self.FILINGS_URL,
            params={"scripcode": scrip_code},
            headers=BSE_HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        reports = []
        items = data if isinstance(data, list) else data.get("Table", data.get("data", []))

        for item in items:
            if not isinstance(item, dict):
                continue

            pdf_url = (
                item.get("Ession_File", "")
                or item.get("ATTACHMENT_NAME", "")
                or item.get("file_url", "")
            )

            # Ensure full URL
            if pdf_url and not pdf_url.startswith("http"):
                pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pdf_url}"

            if not pdf_url:
                continue

            title = (
                item.get("SLONGNAME", "")
                or item.get("HEAD", "")
                or item.get("News_subject", "")
                or "Annual Report"
            )

            date = (
                item.get("News_dt", "")
                or item.get("DT_TM", "")
                or item.get("SUBMISSION_DATE", "")
                or ""
            )

            # Extract year from date or title
            year = ""
            if date and len(date) >= 4:
                year = date[:4] if date[0].isdigit() else ""
            if not year and "20" in title:
                import re
                m = re.search(r"20\d{2}", title)
                if m:
                    year = m.group()

            reports.append(BSEAnnualReport(
                year=year,
                title=title.strip(),
                pdf_url=pdf_url.strip(),
                date=date.strip(),
            ))

        # Sort by date descending
        reports.sort(key=lambda r: r.date, reverse=True)
        logger.info(f"BSE filings for {scrip_code} → {len(reports)} annual reports")
        return reports[:10]  # Cap at 10

    async def download_pdf(self, pdf_url: str) -> bytes:
        """Proxy-download a PDF from BSE (avoids CORS)."""
        try:
            result = await run_in_threadpool(self._download_sync, pdf_url)
            return result
        except Exception as e:
            logger.error(f"BSE PDF download failed for {pdf_url}: {e}")
            raise

    def _download_sync(self, pdf_url: str) -> bytes:
        resp = requests.get(
            pdf_url,
            headers=BSE_HEADERS,
            timeout=30,
            stream=False,
        )
        resp.raise_for_status()
        return resp.content
