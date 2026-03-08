# core/pdf_processor.py
# ── Responsible only for reading and chunking PDF files ──
# Single Responsibility: text extraction + chunking + name sanitization.

import os
import re
from pathlib import Path
from typing import List

from pypdf import PdfReader


CHUNK_SIZE    = 1500
CHUNK_OVERLAP = 300


class PDFProcessor:

    @staticmethod
    def extract_text(pdf_path: str) -> tuple[str, int]:
        """
        Extract full text from a PDF.
        Returns (full_text, page_count).
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        reader    = PdfReader(pdf_path)
        full_text = "".join(page.extract_text() or "" for page in reader.pages)
        return full_text, len(reader.pages)

    @staticmethod
    def chunk_text(
        text:       str,
        chunk_size: int = CHUNK_SIZE,
        overlap:    int = CHUNK_OVERLAP,
    ) -> List[str]:
        """
        Split text into overlapping chunks.
        Overlap preserves context across chunk boundaries.
        """
        chunks, start = [], 0
        while start < len(text):
            chunk = text[start : start + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    @staticmethod
    def sanitize_collection_name(pdf_path: str) -> str:
        """
        ChromaDB collection names must be 3-512 chars,
        only alphanumeric/dots/dashes/underscores,
        starting and ending with alphanumeric.
        e.g. 'tech report for march.pdf' → 'doc_tech_report_for_march'
        """
        raw       = Path(pdf_path).stem
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', raw)
        sanitized = re.sub(r'^[^a-zA-Z0-9]+', '', sanitized)
        sanitized = re.sub(r'[^a-zA-Z0-9]+$', '', sanitized)
        if len(sanitized) < 3:
            sanitized = f"doc_{sanitized}_file"
        return f"doc_{sanitized}"