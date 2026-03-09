"""
API v1 Router – aggregates all v1 endpoints.
"""
from fastapi import APIRouter

from app.api.v1.analyze_report import router as analyze_router
from app.api.v1.external_mocks  import router as mocks_router
from app.api.v1.export_cam      import router as cam_router
from app.api.v1.decision_narrative import router as narrative_router
from app.api.v1.bse_routes import router as bse_router

api_v1_router = APIRouter()

# Deep Reader Compliance Agent
api_v1_router.include_router(analyze_router, prefix="")

# External Intelligence Mock APIs
api_v1_router.include_router(mocks_router,   prefix="")

# CAM Export
api_v1_router.include_router(cam_router,     prefix="")

# Decision Narrative
api_v1_router.include_router(narrative_router, prefix="")

# BSE Annual Report Surfer
api_v1_router.include_router(bse_router, prefix="")
