# core/vector_store.py
# ── Wraps ChromaDB for storing and querying document embeddings ──
# Single Responsibility: vector persistence + similarity search.

from typing import List

import chromadb
from sentence_transformers import SentenceTransformer


MAX_SEARCH_RESULTS = 4


class VectorStore:

    def __init__(self, embedding_model: SentenceTransformer):
        self._client          = chromadb.Client()
        self._embedding_model = embedding_model
        self._collection      = None
        self._all_chunks: List[str] = []

    # ── public API ───────────────────────────────────────────

    def build(self, chunks: List[str], collection_name: str) -> None:
        """Embed chunks and store in a named ChromaDB collection."""
        self._drop_if_exists(collection_name)
        self._collection = self._client.create_collection(collection_name)
        self._all_chunks = chunks
        embeddings       = self._embedding_model.encode(chunks, show_progress_bar=False)
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            self._collection.add(
                ids        = [f"chunk_{i}"],
                embeddings = [emb.tolist()],
                documents  = [chunk],
            )

    def search(self, query: str, n_results: int = MAX_SEARCH_RESULTS) -> List[str]:
        """Return the top-n most relevant chunks for a query."""
        if self._collection is None:
            raise RuntimeError("No collection loaded. Call build() first.")
        qe = self._embedding_model.encode([query])[0]
        results = self._collection.query(
            query_embeddings = [qe.tolist()],
            n_results        = min(n_results, len(self._all_chunks)),
        )
        return results["documents"][0] if results["documents"][0] else []

    def get_all_chunks(self) -> List[str]:
        """Return every chunk — used by full-document analysis tools."""
        return self._all_chunks

    def is_ready(self) -> bool:
        return self._collection is not None

    # ── private ──────────────────────────────────────────────

    def _drop_if_exists(self, name: str) -> None:
        try:
            self._client.delete_collection(name)
        except Exception:
            pass