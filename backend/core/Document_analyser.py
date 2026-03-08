# core/document_analyser.py
# ── Performs whole-document reasoning tasks via LLM ──
# Called only when needed — not on every agent step.
# Each method makes exactly ONE Gemini API call.

import json
import re

from core.models import DocType, TaskMode, DOC_TYPE_MAP
from core.llm_clients import GeminiClient
from core.vector_store import VectorStore


class DocumentAnalyser:

    def __init__(self, llm: GeminiClient, vector_store: VectorStore):
        self._llm = llm
        self._vs  = vector_store

    # ── load-time analysis (1 combined call) ─────────────────

    def detect_all_at_once(self) -> tuple:
        """
        Detects document type AND generates a summary in a single LLM call.
        Replaces the old separate detect_doc_type() + quick_summary() calls.
        Returns: (DocType, summary_string)
        """
        sample = " ".join(self._vs.get_all_chunks()[:3])[:4000]

        prompt = (
            "Analyse this document excerpt and return a JSON object with exactly these two fields:\n\n"
            "{\n"
            '  "doc_type": "<one of: resume | research_paper | news_article | legal_document | textbook | business_report | unknown>",\n'
            '  "summary":  "<exactly 2 sentences: what this document is, who wrote it if known, and its main purpose>"\n'
            "}\n\n"
            "Rules:\n"
            "- Respond with ONLY the JSON object — no markdown, no explanation, no code fences.\n"
            "- doc_type must be exactly one of the listed labels.\n"
            "- summary must be exactly 2 sentences, specific and factual.\n\n"
            f"Document excerpt:\n{sample}"
        )

        raw = self._llm.complete(prompt).strip()
        raw = re.sub(r"```json|```", "", raw).strip()

        try:
            parsed   = json.loads(raw)
            raw_type = parsed.get("doc_type", "unknown").strip().lower()
            summary  = parsed.get("summary", "").strip()
        except (json.JSONDecodeError, AttributeError):
            raw_type = "unknown"
            summary  = "Document loaded successfully."

        doc_type = DOC_TYPE_MAP.get(raw_type, DocType.UNKNOWN)
        return doc_type, summary

    # ── per-question analysis ─────────────────────────────────

    def detect_task(self, question: str, doc_type: DocType) -> TaskMode:
        """
        Classify user intent → TaskMode.
        Called once per question when mode is AUTO.
        """
        prompt = (
            f"Classify the user's intent. Document type: {doc_type}\n"
            f'User question: "{question}"\n\n'
            "Choose one:\n"
            "- critic   : wants problems, weaknesses, improvements, fixes, review\n"
            "- study    : wants summary, key points, flashcards, exam prep, notes\n"
            "- extract  : wants specific data pulled out (dates, names, numbers, lists)\n"
            "- explain  : wants something simplified or clarified\n"
            "- general  : wants a direct factual answer\n\n"
            "Respond with ONLY the single word label."
        )
        raw = self._llm.complete(prompt).strip().lower()
        try:
            return TaskMode(raw)
        except ValueError:
            return TaskMode.GENERAL

    # ── tool-level analysis (called by ToolRegistry) ──────────

    def critique_document(self, focus: str = "") -> str:
        """Full expert critique with problems, fixes, and scores."""
        all_text  = "\n\n".join(self._vs.get_all_chunks())
        focus_str = f"\nFocus especially on: {focus}" if focus else ""

        prompt = f"""You are an expert document reviewer. Analyse the document below.{focus_str}

Your response MUST use this exact markdown structure:

## 📋 Document Overview
[2-3 sentences about what this document is and its overall quality]

## ❌ Problems Found
For each problem use this format:
### Problem [N]: [Short title]
- **Section**: [which part of the document]
- **Issue**: [what is wrong]
- **Impact**: [why it matters]
- **Fix**: [specific, actionable recommendation]

## ✅ Strengths
[bullet list of what is done well]

## 🏆 Priority Action Plan
[numbered list of top 5 most impactful changes to make, in order of priority]

## 📊 Overall Score
Rate each dimension out of 10: Content / Clarity / Structure / Impact

Document:
{all_text}"""
        return self._llm.complete(prompt)

    def study_summary(self, style: str = "bullets") -> str:
        """Generate study material in the requested format."""
        all_text = "\n\n".join(self._vs.get_all_chunks())

        style_instructions = {
            "bullets": (
                "## 📚 Key Topics\n[bullet list of main topics]\n\n"
                "## 🔑 Key Concepts & Definitions\n[bullet list: **Term** — definition]\n\n"
                "## 📌 Important Facts & Figures\n[specific data, numbers, findings]\n\n"
                "## 💡 Core Ideas to Remember\n[5-7 most important takeaways]\n\n"
                "## ❓ Likely Exam Questions\n[5 questions with brief answers]"
            ),
            "flashcards": (
                "## 🃏 Flashcards\n\n"
                "**Card 1**\nQ: [question]\nA: [answer]\n\n"
                "[continue for 10-15 cards covering the most important content]"
            ),
            "mindmap": (
                "## 🗺️ Mind Map\n\n"
                "CENTRAL TOPIC: [main subject]\n"
                "├── [Branch 1]\n│   ├── [Sub-point]\n│   └── [Sub-point]\n"
                "├── [Branch 2]\n[cover all major themes]"
            ),
            "detailed": (
                "## 📖 Detailed Study Notes\n\n"
                "### [Section Title]\n[thorough explanation]\n**Key point:** [highlight]\n\n"
                "[continue section by section]"
            ),
        }

        instruction = style_instructions.get(style, style_instructions["bullets"])
        prompt = (
            "You are an expert study assistant. Create comprehensive study material.\n"
            f"Use this format:\n{instruction}\n\n"
            f"Document:\n{all_text}"
        )
        return self._llm.complete(prompt)

    def extract_structured(self, what_to_extract: str) -> str:
        """Pull specific structured data out of the document."""
        all_text = "\n\n".join(self._vs.get_all_chunks())
        prompt = (
            f"Extract the following from the document: {what_to_extract}\n\n"
            "Present results in clean structured markdown.\n"
            "If something is not found, write 'Not found'.\n"
            "Do not add information that is not in the document.\n\n"
            f"Document:\n{all_text}"
        )
        return self._llm.complete(prompt)