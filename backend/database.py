# database.py
# ── Persistent SQLite storage for documents, sessions, and messages ──
# Uses only Python's built-in sqlite3 — no extra packages needed.
#
# Schema:
#   documents → one row per PDF ever loaded
#   sessions  → one row per load_pdf() call (same PDF can have multiple sessions)
#   messages  → one row per question/answer turn

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from contextlib import contextmanager


# DB file lives next to main.py inside backend/
DB_PATH = Path(__file__).parent / "rag_history.db"


# ============================================================
# CONNECTION HELPER
# ============================================================

@contextmanager
def _get_conn():
    """Context manager — always closes connection even on error."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL") # safer concurrent writes
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# SCHEMA INIT — called once at startup
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
    """
    Insert a new document row and return its id.
    Called every time load_pdf() succeeds.
    """
    with _get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO documents (filename, doc_type, num_pages, num_chunks, summary, loaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (filename, str(doc_type), num_pages, num_chunks, summary, loaded_at),
        )
        return cursor.lastrowid


def get_all_documents() -> List[Dict]:
    """Return all documents ever loaded, newest first."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# SESSION OPERATIONS
# ============================================================

def create_session(document_id: int) -> int:
    """
    Create a new session for a document and return its id.
    A session = one load_pdf() call. Same PDF can have multiple sessions.
    """
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
    """
    Save a single message (user question or assistant answer).
    Returns the new message id.
    """
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
    """
    Save a complete question + answer turn as two message rows.
    Convenience wrapper around save_message() — call this after each answer.
    """
    save_message(session_id, "user",      question, task_mode, doc_type)
    save_message(session_id, "assistant", answer,   task_mode, doc_type)


def get_session_messages(session_id: int) -> List[Dict]:
    """Return all messages for a session in chronological order."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_history(limit: int = 100) -> List[Dict]:
    """
    Return recent conversation turns (question + answer pairs)
    joined with document info. Used by GET /history endpoint.
    """
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
            JOIN messages a  ON a.id      = q.id + 1
                             AND a.role   = 'assistant'
                             AND a.session_id = q.session_id
            JOIN sessions s  ON s.id      = q.session_id
            JOIN documents d ON d.id      = s.document_id
            WHERE q.role = 'user'
            ORDER BY q.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_document_history(filename: str, limit: int = 50) -> List[Dict]:
    """
    Return all conversation turns for a specific document filename.
    Useful for showing past sessions for the same PDF.
    """
    with _get_conn() as conn:
        rows = conn.execute(
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
            JOIN documents d ON d.id = s.document_id
            WHERE q.role = 'user'
              AND d.filename = ?
            ORDER BY q.id DESC
            LIMIT ?
            """,
            (filename, limit),
        ).fetchall()
        return [dict(r) for r in rows]