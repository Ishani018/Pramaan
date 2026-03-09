"""
BSE Annual Report Surfer — API Routes
=======================================
Proxy endpoints for BSE India company search and annual report fetching.
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import Response

from app.agents.external.bse_surfer import BSESurfer

router = APIRouter(prefix="/bse", tags=["BSE Annual Report Surfer"])
surfer = BSESurfer()


@router.get("/search")
async def bse_search(q: str = Query(..., min_length=2, description="Company name to search")):
    """Search BSE for companies by name. Returns up to 15 matches."""
    results = await surfer.search_company(q)
    return {
        "results": [
            {
                "scrip_code": r.scrip_code,
                "company_name": r.company_name,
                "status": r.status,
                "group": r.group,
                "industry": r.industry,
            }
            for r in results
        ]
    }


@router.get("/annual-reports")
async def bse_annual_reports(
    scrip_code: str = Query(..., description="BSE scrip code"),
):
    """List annual report filings for a BSE scrip code."""
    reports = await surfer.get_annual_reports(scrip_code)
    if not reports:
        return {"reports": [], "message": "No annual reports found for this scrip code"}
    return {
        "reports": [
            {
                "year": r.year,
                "title": r.title,
                "pdf_url": r.pdf_url,
                "date": r.date,
            }
            for r in reports
        ]
    }


@router.get("/download-pdf")
async def bse_download_pdf(
    url: str = Query(..., description="BSE PDF URL to proxy-download"),
):
    """Proxy-download a PDF from BSE (avoids browser CORS issues)."""
    if not url.startswith("https://www.bseindia.com") and not url.startswith("https://api.bse-india.com"):
        raise HTTPException(status_code=400, detail="Only BSE India URLs are allowed")

    try:
        pdf_bytes = await surfer.download_pdf(url)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=annual_report.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to download from BSE: {str(e)}")
