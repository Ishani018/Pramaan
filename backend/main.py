"""
Project Pramaan – FastAPI Application Entry Point
==================================================
"The Deterministic AI Credit Engine"

Architecture:
  - Async FastAPI with CORS configured for browser access
  - Versioned API: /api/v1/...
  - Deep Reader Agent: POST /api/v1/analyze-report
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.v1.router import api_v1_router

import logging.config

# ---------------------------------------------------------------------------
# Logging – configured inside lifespan so it runs AFTER uvicorn's own setup
# ---------------------------------------------------------------------------
logger = logging.getLogger("pramaan")

def _configure_logging():
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": "INFO",
                "stream": "ext://sys.stderr",
            },
            "file": {
                "class": "logging.FileHandler",
                "formatter": "standard",
                "level": "INFO",
                "filename": "pramaan.log",
                "mode": "a",
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "pramaan": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
            "app": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
            "uvicorn": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
            "fastapi": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        },
        "root": {
            "handlers": ["console", "file"],
            "level": "INFO",
        }
    }
    logging.config.dictConfig(logging_config)

# Call immediately at module level
_configure_logging()


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown hooks)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()          # ← runs AFTER uvicorn has finished its setup
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.VERSION}")
    logger.info("  Credit Committee Architecture – Online")
    logger.info("=" * 60)
    yield
    logger.info("Pramaan shutting down. Audit trail preserved.")


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Project Pramaan: Next-Gen Corporate Credit Decisioning Engine. "
        "Deterministic, explainable, and built for the Indian lending landscape."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS Middleware ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    summary="Health Check",
    tags=["System"],
    response_description="Service health status",
)
async def health():
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.VERSION}


@app.get(
    "/",
    summary="Root",
    tags=["System"],
    include_in_schema=False,
)
async def root():
    return JSONResponse(
        content={
            "project": "Pramaan – Intelli-Credit Engine",
            "docs": "/docs",
            "health": "/health",
            "api_v1": settings.API_V1_STR,
        }
    )


# Mount versioned API
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
