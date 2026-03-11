# core/llm_clients.py
# ── All external API clients in one place ──
# GeminiClient   : wraps Google Gemini 2.0 Flash for LLM completions
# WebSearchClient: wraps Tavily for real-time web search

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Explicitly load .env from the backend directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GEMINI_MODEL_NAME = "gemini-2.5-flash"


# ============================================================
# GEMINI CLIENT
# ============================================================

class GeminiClient:

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY not set in .env")
        self._client = genai.Client(api_key=api_key)
        print(f"✅ LLM ready (Gemini — {GEMINI_MODEL_NAME})")

    def complete(self, prompt: str) -> str:
        """Send a prompt and return the text response."""
        response = self._client.models.generate_content(
            model    = GEMINI_MODEL_NAME,
            contents = prompt,
        )
        return response.text.strip()


# ============================================================
# WEB SEARCH CLIENT  (Tavily)
# ============================================================

class WebSearchClient:
    """
    Wraps Tavily search API for real-time web search.
    Fails gracefully if key is missing — agent falls back to document-only answers.
    """

    def __init__(self):
        api_key       = os.getenv("TAVILY_API_KEY", "")
        self._enabled = bool(api_key)

        if self._enabled:
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=api_key)
                print("✅ Web search enabled (Tavily)")
            except ImportError:
                self._enabled = False
                print("⚠️  tavily-python not installed — run: pip install tavily-python")
        else:
            print("⚠️  TAVILY_API_KEY not set — web search disabled")

    def search(self, query: str, max_results: int = 3) -> str:
        if not self._enabled:
            return (
                "Web search is currently unavailable. "
                "Answer using the document content or your own knowledge."
            )
        try:
            response = self._client.search(
                query          = query,
                max_results    = max_results,
                search_depth   = "basic",
                include_answer = True,
            )
            parts = []
            if response.get("answer"):
                parts.append("**Direct Answer:** " + str(response["answer"]) + "\n")
            for i, r in enumerate(response.get("results", []), 1):
                title   = r.get("title", "Unknown")
                url     = r.get("url", "")
                snippet = r.get("content", "")[:500]
                parts.append(
                    f"**Source {i}:** {title}\n"
                    f"**URL:** {url}\n"
                    f"**Content:** {snippet}\n"
                )
            return "\n\n".join(parts) if parts else "No results found for that query."
        except Exception as exc:
            return (
                f"Web search failed ({exc}). "
                "Answer using the document content or your own knowledge."
            )

    @property
    def is_enabled(self) -> bool:
        return self._enabled