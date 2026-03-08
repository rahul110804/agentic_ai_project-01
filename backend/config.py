"""
config.py
---------
All application settings in one place.
Every value that might change lives here.

Usage anywhere:
    from config import settings
"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):

    # ── Gemini ───────────────────────────────────────────────
    GEMINI_API_KEY: str = ""

    # ── File Upload ──────────────────────────────────────────
    UPLOAD_DIR:         Path      = BASE_DIR / "uploads"
    MAX_FILE_SIZE_MB:   int       = 20
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]
    
    TAVILY_API_KEY: str = ""  

    # ── CORS ─────────────────────────────────────────────────
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ── FastAPI ──────────────────────────────────────────────
    API_TITLE:       str = "Agentic RAG API"
    API_VERSION:     str = "1.0.0"
    API_DESCRIPTION: str = "Advanced document analysis API using Agentic RAG."

    # ── Server ───────────────────────────────────────────────
    HOST:   str  = "0.0.0.0"
    PORT:   int  = 8000
    RELOAD: bool = True

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"
        case_sensitive    = True


settings = Settings()


def validate_settings() -> None:
    errors = []

    if not settings.GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is not set in .env")

    if not settings.UPLOAD_DIR.exists():
        try:
            settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created upload directory: {settings.UPLOAD_DIR}")
        except Exception as e:
            errors.append(f"Cannot create upload directory: {e}")

    if errors:
        for err in errors:
            print(f"❌ Config error: {err}")
        raise RuntimeError(f"Configuration errors: {errors}")

    print(f"✅ Config validated — upload dir: {settings.UPLOAD_DIR}")


def is_allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in settings.ALLOWED_EXTENSIONS


def get_upload_path(filename: str) -> Path:
    safe_name = Path(filename).name
    return settings.UPLOAD_DIR / safe_name