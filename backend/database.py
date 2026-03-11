# database.py
# ── Persistent SQLite storage for documents, sessions, and messages ──
# Uses only Python's built-in sqlite3 — no extra packages needed.
#
# Schema:
#   documents → one row per PDF ever loaded
#   sessions  → one row per load_pdf() call (same PDF can have multiple sessions)
#   messages  → one row per question/answer turn

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from contextlib import contextmanager


DB_PATH = Path(__file__).parent / "rag_history.db"


# ============================================================
# CONNECTION HELPER
# ============================================================

@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# SCHEMA INIT
# ============================================================

def init_db() -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                filename    TEXT    NOT NULL,
                doc_type    TEXT    NOT NULL DEFAULT 'unknown',
                num_pages   INTEGER NOT NULL DEFAULT 0,
                num_chunks  INTEGER NOT NULL DEFAULT 0,
                summary     TEXT    NOT NULL DEFAULT '',
                loaded_at   TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES documents(id),
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL REFERENCES sessions(id),
                role        TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                content     TEXT    NOT NULL,
                task_mode   TEXT    NOT NULL DEFAULT 'general',
                doc_type    TEXT    NOT NULL DEFAULT 'unknown',
                timestamp   TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id);

            CREATE INDEX IF NOT EXISTS idx_sessions_document
                ON sessions(document_id);
        """)
    print(f"✅ Database ready: {DB_PATH}")


# ============================================================
# DOCUMENT OPERATIONS
# ============================================================

def save_document(
    filename:   str,
    doc_type:   str,
    num_pages:  int,
    num_chunks: int,
    summary:    str,
    loaded_at:  str,
) -> int:
    with _get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO documents (filename, doc_type, num_pages, num_chunks, summary, loaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (filename, str(doc_type), num_pages, num_chunks, summary, loaded_at),
        )
        return cursor.lastrowid


# ============================================================
# SESSION OPERATIONS
# ============================================================

def create_session(document_id: int) -> int:
    with _get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO sessions (document_id, created_at) VALUES (?, ?)",
            (document_id, datetime.now().isoformat()),
        )
        return cursor.lastrowid


# ============================================================
# MESSAGE OPERATIONS
# ============================================================

def save_message(
    session_id: int,
    role:       str,
    content:    str,
    task_mode:  str = "general",
    doc_type:   str = "unknown",
) -> int:
    with _get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO messages (session_id, role, content, task_mode, doc_type, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                str(task_mode),
                str(doc_type),
                datetime.now().isoformat(),
            ),
        )
        return cursor.lastrowid


def save_turn(
    session_id: int,
    question:   str,
    answer:     str,
    task_mode:  str = "general",
    doc_type:   str = "unknown",
) -> None:
    """Save a complete Q&A turn as two message rows."""
    save_message(session_id, "user",      question, task_mode, doc_type)
    save_message(session_id, "assistant", answer,   task_mode, doc_type)


# ============================================================
# HISTORY QUERIES
# ============================================================

def get_all_history(limit: int = 100) -> List[Dict]:
    """Simple flat list of turns — used as fallback."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                q.content   AS question,
                a.content   AS answer,
                a.task_mode AS task_mode,
                a.doc_type  AS doc_type,
                d.filename  AS filename,
                a.timestamp AS timestamp
            FROM messages q
            JOIN messages a  ON a.id = q.id + 1
                             AND a.role = 'assistant'
                             AND a.session_id = q.session_id
            JOIN sessions s  ON s.id = q.session_id
            JOIN documents d ON d.id = s.document_id
            WHERE q.role = 'user'
            ORDER BY q.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_documents_with_history() -> List[Dict]:
    """
    Returns all documents that have at least one message,
    each with their full list of Q&A turns — newest document first.

    Structure:
    [
      {
        document_id: 1,
        filename: "resume.pdf",
        doc_type: "resume",
        loaded_at: "2024-...",
        turns: [
          { question: "...", answer: "...", task_mode: "...", timestamp: "..." },
          ...
        ]
      },
      ...
    ]
    """
    with _get_conn() as conn:
        # Get all documents that have messages
        docs = conn.execute(
            """
            SELECT DISTINCT
                d.id        AS document_id,
                d.filename  AS filename,
                d.doc_type  AS doc_type,
                d.num_pages AS num_pages,
                d.summary   AS summary,
                d.loaded_at AS loaded_at
            FROM documents d
            JOIN sessions s  ON s.document_id = d.id
            JOIN messages m  ON m.session_id  = s.id
            ORDER BY d.id DESC
            """,
        ).fetchall()

        result = []
        for doc in docs:
            doc_dict = dict(doc)

            # Get all turns for this document across all its sessions
            turns = conn.execute(
                """
                SELECT
                    q.content   AS question,
                    a.content   AS answer,
                    a.task_mode AS task_mode,
                    a.timestamp AS timestamp
                FROM messages q
                JOIN messages a  ON a.id = q.id + 1
                                 AND a.role = 'assistant'
                                 AND a.session_id = q.session_id
                JOIN sessions s  ON s.id = q.session_id
                WHERE q.role = 'user'
                  AND s.document_id = ?
                ORDER BY q.id ASC
                """,
                (doc_dict["document_id"],),
            ).fetchall()

            doc_dict["turns"] = [dict(t) for t in turns]

            # Only include documents that actually have turns
            if doc_dict["turns"]:
                result.append(doc_dict)

        return result


def get_document_by_id(doc_id: int) -> dict:
    """Fetch a single document record by its ID."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, filename, doc_type, num_pages, summary, loaded_at FROM documents WHERE id = ?",
            (doc_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"No document with id={doc_id}")
        return {
            "id":        row[0],
            "filename":  row[1],
            "doc_type":  row[2],
            "num_pages": row[3],
            "summary":   row[4],
            "loaded_at": row[5],
        }
    finally:
        conn.close()