# core/tool_registry.py
# ── Registers and executes all tools available to the ReAct agent ──
# Adding a new tool = add entry to self._tools + add a method below.

from datetime import datetime
from typing import Dict, List

from core.vector_store import VectorStore
from core.document_analyser import DocumentAnalyser
from core.llm_clients import WebSearchClient


class ToolRegistry:

    def __init__(
        self,
        vector_store:  VectorStore,
        analyser:      DocumentAnalyser,
        web_search:    WebSearchClient,
    ):
        self._vs         = vector_store
        self._analyser   = analyser
        self._web_search = web_search

        # ── Tool definitions ─────────────────────────────────
        # Each entry: fn (callable or None for finish) + description for the LLM prompt
        self._tools: Dict[str, Dict] = {

            "search_document": {
                "fn": self.search_document,
                "description": (
                    "Search the uploaded PDF for specific information. "
                    "Use when the answer is likely inside the document. "
                    "Input: a focused search query string."
                ),
            },

            "search_web": {
                "fn": self.search_web,
                "description": (
                    "Search the internet for current or external information. "
                    "Use when: the question needs real-time data, recent events, industry benchmarks, "
                    "or context that goes beyond what is in the PDF. "
                    "Input: a clear search query string."
                ),
            },

            "critique_document": {
                "fn": self.critique_document,
                "description": (
                    "Perform a full expert critique of the entire document. "
                    "Finds problems, weaknesses, and provides specific actionable fixes. "
                    "Use for: 'what is wrong', 'how to improve', 'review this'. "
                    "Input: optional focus area e.g. 'skills section', or empty string for full critique."
                ),
            },

            "study_summary": {
                "fn": self.study_summary,
                "description": (
                    "Generate comprehensive study material from the full document. "
                    "Use for: exam prep, summarization, key concepts, flashcards. "
                    "Input: one of 'bullets' | 'flashcards' | 'mindmap' | 'detailed'."
                ),
            },

            "extract_data": {
                "fn": self.extract_data,
                "description": (
                    "Extract specific structured data from the document. "
                    "Use when user wants items pulled out: dates, names, numbers, skills, lists. "
                    "Input: description of what to extract e.g. 'all dates and deadlines'."
                ),
            },

            "calculate": {
                "fn": self.calculate,
                "description": (
                    "Perform mathematical calculations. "
                    "Input: a valid Python arithmetic expression e.g. '365 * 24'."
                ),
            },

            "get_current_date": {
                "fn": self.get_current_date,
                "description": "Return today's date and current time. No input needed.",
            },

            "finish": {
                "fn": None,
                "description": (
                    "Call this when you have a complete, well-formed answer ready. "
                    "Input: the full final answer in well-structured markdown."
                ),
            },
        }

    # ── Tool implementations ──────────────────────────────────

    def search_document(self, query: str) -> str:
        if not self._vs.is_ready():
            return "ERROR: No document loaded."
        chunks = self._vs.search(query)
        return "\n\n---\n\n".join(chunks) if chunks else "No relevant information found."

    def search_web(self, query: str) -> str:
        return self._web_search.search(query)

    def critique_document(self, focus: str = "") -> str:
        return self._analyser.critique_document(focus)

    def study_summary(self, style: str = "bullets") -> str:
        style = style.strip().lower()
        if style not in {"bullets", "flashcards", "mindmap", "detailed"}:
            style = "bullets"
        return self._analyser.study_summary(style)

    def extract_data(self, what: str) -> str:
        return self._analyser.extract_structured(what)

    def calculate(self, expression: str) -> str:
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as exc:
            return f"Calculation error: {exc}"

    def get_current_date(self, *_) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Registry interface (used by agent + prompt builder) ───

    def execute(self, tool_name: str, tool_input: str) -> str:
        if tool_name not in self._tools:
            return f"ERROR: Unknown tool '{tool_name}'."
        fn = self._tools[tool_name]["fn"]
        if fn is None:
            return ""          # finish — no execution needed
        return fn(tool_input)

    def descriptions(self) -> str:
        return "\n".join(
            f"- {name}: {info['description']}"
            for name, info in self._tools.items()
        )

    def names(self) -> List[str]:
        return list(self._tools.keys())