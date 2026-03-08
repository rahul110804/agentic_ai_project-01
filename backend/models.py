"""
models.py
---------
Pydantic schemas for all FastAPI request and response bodies.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ============================================================
# ENUMS
# ============================================================

class TaskModeEnum(str, Enum):
    AUTO    = "auto"
    CRITIC  = "critic"
    STUDY   = "study"
    EXTRACT = "extract"
    EXPLAIN = "explain"
    GENERAL = "general"


class DocTypeEnum(str, Enum):
    RESUME          = "resume"
    RESEARCH_PAPER  = "research_paper"
    NEWS_ARTICLE    = "news_article"
    LEGAL_DOCUMENT  = "legal_document"
    TEXTBOOK        = "textbook"
    BUSINESS_REPORT = "business_report"
    UNKNOWN         = "unknown"


# ============================================================
# REQUEST MODELS
# ============================================================

class ChatRequest(BaseModel):
    question:      str                   = Field(..., min_length=1, max_length=2000)
    mode_override: Optional[TaskModeEnum] = Field(default=None)

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Find all problems in this resume and suggest fixes",
                "mode_override": None
            }
        }


# ============================================================
# RESPONSE MODELS
# ============================================================

class DocumentMetaResponse(BaseModel):
    filename:    str
    num_pages:   int
    num_chunks:  int
    loaded_at:   str
    doc_type:    DocTypeEnum
    doc_summary: str


class UploadResponse(BaseModel):
    success:  bool
    message:  str
    document: DocumentMetaResponse


class StatusResponse(BaseModel):
    is_ready: bool
    document: Optional[DocumentMetaResponse] = None
    message:  str


class ResetResponse(BaseModel):
    success: bool
    message: str


class ConversationTurn(BaseModel):
    question: str
    answer:   str


class HistoryResponse(BaseModel):
    turns: List[ConversationTurn]
    total: int


class ErrorResponse(BaseModel):
    error:  str
    detail: Optional[str] = None