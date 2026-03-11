"""
compare_rag.py
--------------
Handles comparison of two PDFs.
Loads each PDF into its own isolated VectorStore,
queries both independently, then asks the LLM to produce
a structured side-by-side comparison table in Markdown.
"""

from pathlib import Path
from typing import Dict, Any

from sentence_transformers import SentenceTransformer

from core.pdf_processor import PDFProcessor
from core.vector_store import VectorStore
from core.llm_clients import GeminiClient
from core.document_analyser import DocumentAnalyser

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
MAX_CONTEXT_CHARS    = 3000   # per document — keeps prompt within token limits


class CompareRAG:
    """
    Loads two PDFs into separate vector stores and compares them
    based on a user question. Returns a markdown comparison table.
    """

    def __init__(self):
        self._embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self._llm             = GeminiClient()

    # ── Public API ────────────────────────────────────────────

    def compare(
        self,
        pdf_path_a: str,
        pdf_path_b: str,
        question:   str,
    ) -> Dict[str, Any]:
        """
        Returns:
          {
            "table":    "<markdown table>",
            "summary":  "<brief paragraph>",
            "doc_a":    "<filename A>",
            "doc_b":    "<filename B>",
          }
        """
        name_a = Path(pdf_path_a).name
        name_b = Path(pdf_path_b).name

        print(f"📊 Comparing: '{name_a}' vs '{name_b}'")

        # Load both PDFs into separate vector stores
        context_a = self._load_and_retrieve(pdf_path_a, question)
        context_b = self._load_and_retrieve(pdf_path_b, question)

        # Build comparison prompt
        prompt = self._build_prompt(name_a, context_a, name_b, context_b, question)

        # Single LLM call — returns markdown table + summary
        raw = self._llm.complete(prompt)

        return {
            "table":   raw,
            "doc_a":   name_a,
            "doc_b":   name_b,
        }

    # ── Private helpers ───────────────────────────────────────

    def _load_and_retrieve(self, pdf_path: str, question: str) -> str:
        """Load a PDF into a fresh VectorStore and retrieve relevant chunks."""
        text, _ = PDFProcessor.extract_text(pdf_path)
        chunks   = PDFProcessor.chunk_text(text)

        vs               = VectorStore(self._embedding_model)
        collection_name  = PDFProcessor.sanitize_collection_name(pdf_path)
        vs.build(chunks, collection_name)

        results = vs.search(question, n_results=5)
        context = "\n\n".join(results)
        return context[:MAX_CONTEXT_CHARS]

    def _build_prompt(
        self,
        name_a:    str,
        context_a: str,
        name_b:    str,
        context_b: str,
        question:  str,
    ) -> str:
        return f"""You are an expert document analyst. Compare these two documents based on the user's question.

USER QUESTION: {question}

--- DOCUMENT A: {name_a} ---
{context_a}

--- DOCUMENT B: {name_b} ---
{context_b}

INSTRUCTIONS:
1. Answer the user's question by comparing both documents.
2. First, output a markdown comparison table with these exact columns:
   | Aspect | {name_a} | {name_b} |
   Identify 5-8 key aspects relevant to the question.
3. After the table, write a short 2-3 sentence "Summary" paragraph highlighting the key differences.
4. Be factual — only use information from the documents above.
5. If a document doesn't mention something, write "Not mentioned" in that cell.

Output the table and summary now:"""