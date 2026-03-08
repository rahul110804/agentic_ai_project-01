# core/models.py
# ── All enums and dataclasses used across the entire system ──
# Nothing imports from other core files here — pure data definitions.

from dataclasses import dataclass, field
from typing import List
from enum import Enum


# ============================================================
# ENUMS
# ============================================================

class TaskMode(str, Enum):
    AUTO    = "auto"
    CRITIC  = "critic"
    STUDY   = "study"
    EXTRACT = "extract"
    EXPLAIN = "explain"
    GENERAL = "general"


class DocType(str, Enum):
    RESUME          = "resume"
    RESEARCH_PAPER  = "research_paper"
    NEWS_ARTICLE    = "news_article"
    LEGAL_DOCUMENT  = "legal_document"
    TEXTBOOK        = "textbook"
    BUSINESS_REPORT = "business_report"
    UNKNOWN         = "unknown"


# ── Shared mapping used by both DocumentAnalyser and ToolRegistry ──
DOC_TYPE_MAP = {
    "resume":          DocType.RESUME,
    "research_paper":  DocType.RESEARCH_PAPER,
    "news_article":    DocType.NEWS_ARTICLE,
    "legal_document":  DocType.LEGAL_DOCUMENT,
    "textbook":        DocType.TEXTBOOK,
    "business_report": DocType.BUSINESS_REPORT,
}


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class AgentStep:
    """One ReAct reasoning step."""
    iteration:    int
    thought:      str
    action:       str
    action_input: str
    observation:  str = ""


@dataclass
class AgentResponse:
    """Final response returned after the agent loop completes."""
    answer:      str
    steps:       List[AgentStep] = field(default_factory=list)
    total_steps: int  = 0
    success:     bool = True
    task_mode:   str  = TaskMode.GENERAL
    doc_type:    str  = DocType.UNKNOWN


@dataclass
class DocumentMeta:
    """Metadata about the currently loaded document."""
    filename:    str
    num_pages:   int
    num_chunks:  int
    loaded_at:   str
    doc_type:    str = DocType.UNKNOWN
    doc_summary: str = ""