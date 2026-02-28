"""
Project Pramaan - Application Settings
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "Project Pramaan – Intelli-Credit Engine"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # CORS – allow all by default; tighten in production
    CORS_ORIGINS: list[str] = ["*"]

    # Temporary storage for uploaded PDFs during analysis
    UPLOAD_DIR: Path = Path("tmp/uploads")

    NEWS_API_KEY: str | None = None
    DATA_GOV_API_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure upload dir exists on startup
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
