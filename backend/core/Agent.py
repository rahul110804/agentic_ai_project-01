"""
agentic_rag.py
--------------
Public facade for the Agentic RAG system.
This file only wires the core modules together — all logic lives in core/.

Capabilities (via core modules):
  1. Critic Mode        — find problems + generate fixes
  2. Study Mode         — summarize, flashcards, key concepts
  3. Doc Type Detection — auto-classifies document
  4. Structured Output  — formatted markdown output
  5. Task Detection     — auto-detects intent, supports manual override
  6. Multi-turn Memory  — follow-up questions with context
  7. Streaming          — SSE-ready event generator
  8. Web Search         — real-time search via Tavily (NEW)

Usage:
    rag  = AgenticRAG()
    meta = rag.load_pdf("resume.pdf")

    response = rag.ask("Find problems and suggest fixes")
    response = rag.ask("Key points", mode_override=TaskMode.STUDY)

    for event in rag.ask_streaming("Is my skill set competitive in 2025?"):
        print(event)   # agent auto-decides: PDF + web search
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, Any, List, Optional

from sentence_transformers import SentenceTransformer

from core.models import AgentResponse, DocumentMeta, DocType, TaskMode
from core.pdf_processor import PDFProcessor
from core.vector_store import VectorStore
from core.llm_clients import GeminiClient, WebSearchClient
from core.document_analyser import DocumentAnalyser
from core.tool_registry import ToolRegistry
from core.memory import ConversationMemory
from core.agent import ReActAgent


EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


class AgenticRAG:
    """
    Top-level interface used by FastAPI (main.py) and the CLI.
    Instantiate once at startup — it's stateful.
    """

    def __init__(self):
        # Shared across all requests — initialised once
        self._embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self._llm             = GeminiClient()
        self._web_search      = WebSearchClient()
        self._memory          = ConversationMemory()

        # Document-scoped — rebuilt on each load_pdf() call
        self._vector_store    = VectorStore(self._embedding_model)
        self._analyser        = DocumentAnalyser(self._llm, self._vector_store)
        self._tools           = ToolRegistry(self._vector_store, self._analyser, self._web_search)
        self._agent           = ReActAgent(self._llm, self._tools, self._memory, self._analyser)

        self._doc_meta: Optional[DocumentMeta] = None

    # ── Document management ───────────────────────────────────

    def load_pdf(self, pdf_path: str) -> DocumentMeta:
        """
        Full pipeline:
          PDF → extract text → chunk → embed → detect type + summary (1 LLM call)
        After this returns, the system is ready to answer questions.
        """
        text, pages = PDFProcessor.extract_text(pdf_path)
        chunks      = PDFProcessor.chunk_text(text)

        collection_name = PDFProcessor.sanitize_collection_name(pdf_path)
        self._vector_store.build(chunks, collection_name)
        self._memory.clear()

        print("🔍 Detecting document type and generating summary...")
        doc_type, doc_summary = self._analyser.detect_all_at_once()

        # Inject document context into the agent
        self._agent.doc_type    = doc_type
        self._agent.doc_summary = doc_summary

        self._doc_meta = DocumentMeta(
            filename    = Path(pdf_path).name,
            num_pages   = pages,
            num_chunks  = len(chunks),
            loaded_at   = datetime.now().isoformat(),
            doc_type    = doc_type,
            doc_summary = doc_summary,
        )

        print(f"✅ '{self._doc_meta.filename}' | {doc_type} | {pages} pages | {len(chunks)} chunks")
        return self._doc_meta

    def reset(self) -> None:
        """
        Clear the current document and conversation.
        LLM client and web search client are preserved — no need to reinitialise.
        """
        self._vector_store = VectorStore(self._embedding_model)
        self._analyser     = DocumentAnalyser(self._llm, self._vector_store)
        self._tools        = ToolRegistry(self._vector_store, self._analyser, self._web_search)
        self._agent        = ReActAgent(self._llm, self._tools, self._memory, self._analyser)
        self._memory.clear()
        self._doc_meta = None

    # ── Querying ──────────────────────────────────────────────

    def ask(
        self,
        question:      str,
        mode_override: Optional[TaskMode] = None,
    ) -> AgentResponse:
        """
        Synchronous. Returns a complete AgentResponse.
        mode_override=None → auto-detect from question.
        """
        self._ensure_ready()
        return self._agent.run(question, mode_override)

    def ask_streaming(
        self,
        question:      str,
        mode_override: Optional[TaskMode] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Streaming. Yields SSE-ready dicts — consumed by FastAPI StreamingResponse.
        Agent self-decides: PDF / web / both / own knowledge.
        """
        self._ensure_ready()
        yield from self._agent.run_streaming(question, mode_override)

    # ── Status ────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._vector_store.is_ready()

    @property
    def doc_meta(self) -> Optional[DocumentMeta]:
        return self._doc_meta

    @property
    def conversation_history(self) -> List[Dict[str, str]]:
        return self._memory.turns

    @property
    def web_search_enabled(self) -> bool:
        return self._web_search.is_enabled

    def _ensure_ready(self) -> None:
        if not self.is_ready:
            raise RuntimeError("No document loaded. Call load_pdf() first.")


# ============================================================
# CLI — local testing
# ============================================================

def _run_cli():
    import re
    from pathlib import Path

    print("\n" + "=" * 60)
    print("  ADVANCED AGENTIC RAG — CLI")
    print("=" * 60)
    print("\nOptional mode prefix before your question:")
    print("  [critic]  [study]  [extract]  [explain]  [auto]")
    print("  Example:  [study] give me flashcards\n")

    rag       = AgenticRAG()
    pdf_files = list(Path(".").glob("*.pdf"))
    if not pdf_files:
        print("❌ No PDF found in the current directory.")
        return

    print(f"📚 Found: {[p.name for p in pdf_files]}")
    meta = rag.load_pdf(str(pdf_files[0]))
    print(f"\n📄 Type       : {meta.doc_type}")
    print(f"📝 Summary    : {meta.doc_summary}")
    print(f"🌐 Web search : {'enabled' if rag.web_search_enabled else 'disabled'}\n")

    MODE_MAP = {m.value: m for m in TaskMode}

    while True:
        try:
            raw_input = input("❓ Question (or 'quit'): ").strip()
            if raw_input.lower() in {"quit", "exit", "q"}:
                print("\n👋 Goodbye!")
                break
            if not raw_input:
                continue

            mode_override = None
            question      = raw_input
            match = re.match(r"^\[(\w+)\]\s*(.*)", raw_input, re.IGNORECASE)
            if match:
                mode_key      = match.group(1).lower()
                question      = match.group(2).strip()
                mode_override = MODE_MAP.get(mode_key)

            response = rag.ask(question, mode_override)
            print(f"\n🎯 Mode  : {response.task_mode}")
            print(f"🔢 Steps : {response.total_steps}")
            print(f"\n{'─' * 60}")
            print(response.answer)
            print(f"{'─' * 60}\n")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as exc:
            print(f"\n❌ Error: {exc}")


if __name__ == "__main__":
    _run_cli()