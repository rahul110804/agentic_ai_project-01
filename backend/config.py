"""
config.py — All application settings in one place.
Reads from environment variables — works locally (.env) and on Render (dashboard vars).
"""

import os
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):

    # ── Gemini API ────────────────────────────────────────────
    GEMINI_API_KEY: str = ""

    # ── Tavily Web Search ─────────────────────────────────────
    TAVILY_API_KEY: str = ""

    # ── Database ──────────────────────────────────────────────
    # Set automatically by Render via render.yaml
    # Not set locally → falls back to SQLite
    DATABASE_URL: str = ""

    # ── File Upload ───────────────────────────────────────────
    UPLOAD_DIR:         Path      = BASE_DIR / "uploads"
    MAX_FILE_SIZE_MB:   int       = 20
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]

    # ── CORS — add your Vercel URL here after frontend deploy ─
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # ── FastAPI ───────────────────────────────────────────────
    API_TITLE:       str = "Agentic RAG API"
    API_VERSION:     str = "1.0.0"
    API_DESCRIPTION: str = "Advanced document analysis API using Agentic RAG."

    # ── Server ────────────────────────────────────────────────
    HOST:   str  = "0.0.0.0"
    PORT:   int  = 8000
    RELOAD: bool = False       # always False in production

    class Config:
        env_file          = ".env"
        env_file_encoding = "utf-8"
        case_sensitive    = True


settings = Settings()


def validate_settings() -> None:
    errors = []

    if not settings.GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is not set")

    # Create upload dir if missing (Render ephemeral disk)
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

    db_type = "PostgreSQL" if settings.DATABASE_URL else "SQLite"
    print(f"✅ Config OK — DB: {db_type} | Upload dir: {settings.UPLOAD_DIR}")


def is_allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in settings.ALLOWED_EXTENSIONS


def get_upload_path(filename: str) -> Path:
    safe_name = Path(filename).name
    return settings.UPLOAD_DIR / safe_name