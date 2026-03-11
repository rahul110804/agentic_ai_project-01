# database.py
# ── Persistent storage — SQLite locally, PostgreSQL on Render ──
#
# Automatically switches based on DATABASE_URL env var:
#   - Not set → SQLite (local dev)
#   - Set      → PostgreSQL (Render production)

import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "")
_USE_PG      = bool(DATABASE_URL)

if _USE_PG:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3

DB_PATH = Path(__file__).parent / "rag_history.db"


# ============================================================
# CONNECTION HELPER — works for both SQLite and PostgreSQL
# ============================================================

@contextmanager
def _get_conn():
    if _USE_PG:
        # Render provides postgres:// but psycopg2 needs postgresql://
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
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


def _placeholder(n: int = 1) -> str:
    """Returns ? for SQLite, %s for PostgreSQL."""
    return "%s" if _USE_PG else "?"


def _ph(count: int = 1):
    """Returns tuple of placeholders."""
    p = "%s" if _USE_PG else "?"
    return ", ".join([p] * count)


# ============================================================
# SCHEMA INIT
# ============================================================

def init_db() -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    with _get_conn() as conn:
        if _USE_PG:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id          SERIAL PRIMARY KEY,
                    filename    TEXT    NOT NULL,
                    doc_type    TEXT    NOT NULL DEFAULT 'unknown',
                    num_pages   INTEGER NOT NULL DEFAULT 0,
                    num_chunks  INTEGER NOT NULL DEFAULT 0,
                    summary     TEXT    NOT NULL DEFAULT '',
                    loaded_at   TEXT    NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id          SERIAL PRIMARY KEY,
                    document_id INTEGER NOT NULL REFERENCES documents(id),
                    created_at  TEXT    NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id          SERIAL PRIMARY KEY,
                    session_id  INTEGER NOT NULL REFERENCES sessions(id),
                    role        TEXT    NOT NULL CHECK(role IN ('user', 'assistant')),
                    content     TEXT    NOT NULL,
                    task_mode   TEXT    NOT NULL DEFAULT 'general',
                    doc_type    TEXT    NOT NULL DEFAULT 'unknown',
                    timestamp   TEXT    NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session  ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_document ON sessions(document_id);
            """)
            cur.close()
        else:
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
                CREATE INDEX IF NOT EXISTS idx_messages_session  ON messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_sessions_document ON sessions(document_id);
            """)
    print(f"✅ Database ready ({'PostgreSQL' if _USE_PG else 'SQLite'})")


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
        if _USE_PG:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO documents (filename, doc_type, num_pages, num_chunks, summary, loaded_at)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (filename, str(doc_type), num_pages, num_chunks, summary, loaded_at),
            )
            row = cur.fetchone()
            cur.close()
            return row["id"]
        else:
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
        if _USE_PG:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO sessions (document_id, created_at) VALUES (%s, %s) RETURNING id",
                (document_id, datetime.now().isoformat()),
            )
            row = cur.fetchone()
            cur.close()
            return row["id"]
        else:
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
        if _USE_PG:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO messages (session_id, role, content, task_mode, doc_type, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (session_id, role, content, str(task_mode), str(doc_type), datetime.now().isoformat()),
            )
            row = cur.fetchone()
            cur.close()
            return row["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO messages (session_id, role, content, task_mode, doc_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, role, content, str(task_mode), str(doc_type), datetime.now().isoformat()),
            )
            return cursor.lastrowid


def save_turn(
    session_id: int,
    question:   str,
    answer:     str,
    task_mode:  str = "general",
    doc_type:   str = "unknown",
) -> None:
    save_message(session_id, "user",      question, task_mode, doc_type)
    save_message(session_id, "assistant", answer,   task_mode, doc_type)


# ============================================================
# HISTORY QUERIES
# ============================================================

def get_all_history(limit: int = 100) -> List[Dict]:
    with _get_conn() as conn:
        p = "%s" if _USE_PG else "?"
        if _USE_PG:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT q.content AS question, a.content AS answer,
                       a.task_mode, a.doc_type, d.filename, a.timestamp
                FROM messages q
                JOIN messages a  ON a.id = q.id + 1
                                 AND a.role = 'assistant'
                                 AND a.session_id = q.session_id
                JOIN sessions s  ON s.id = q.session_id
                JOIN documents d ON d.id = s.document_id
                WHERE q.role = 'user'
                ORDER BY q.id DESC
                LIMIT {p}
                """,
                (limit,),
            )
            rows = cur.fetchall()
            cur.close()
            return [dict(r) for r in rows]
        else:
            rows = conn.execute(
                f"""
                SELECT q.content AS question, a.content AS answer,
                       a.task_mode, a.doc_type, d.filename, a.timestamp
                FROM messages q
                JOIN messages a  ON a.id = q.id + 1
                                 AND a.role = 'assistant'
                                 AND a.session_id = q.session_id
                JOIN sessions s  ON s.id = q.session_id
                JOIN documents d ON d.id = s.document_id
                WHERE q.role = 'user'
                ORDER BY q.id DESC
                LIMIT {p}
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]


def get_documents_with_history() -> List[Dict]:
    with _get_conn() as conn:
        if _USE_PG:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT d.id AS document_id, d.filename, d.doc_type,
                       d.num_pages, d.summary, d.loaded_at
                FROM documents d
                JOIN sessions s ON s.document_id = d.id
                JOIN messages m ON m.session_id  = s.id
                ORDER BY d.id DESC
            """)
            docs = cur.fetchall()
            result = []
            for doc in docs:
                doc_dict = dict(doc)
                cur2 = conn.cursor()
                cur2.execute("""
                    SELECT q.content AS question, a.content AS answer,
                           a.task_mode, a.timestamp
                    FROM messages q
                    JOIN messages a ON a.id = q.id + 1
                                   AND a.role = 'assistant'
                                   AND a.session_id = q.session_id
                    JOIN sessions s ON s.id = q.session_id
                    WHERE q.role = 'user' AND s.document_id = %s
                    ORDER BY q.id ASC
                """, (doc_dict["document_id"],))
                turns = cur2.fetchall()
                cur2.close()
                doc_dict["turns"] = [dict(t) for t in turns]
                if doc_dict["turns"]:
                    result.append(doc_dict)
            cur.close()
            return result
        else:
            docs = conn.execute("""
                SELECT DISTINCT d.id AS document_id, d.filename, d.doc_type,
                       d.num_pages, d.summary, d.loaded_at
                FROM documents d
                JOIN sessions s ON s.document_id = d.id
                JOIN messages m ON m.session_id  = s.id
                ORDER BY d.id DESC
            """).fetchall()
            result = []
            for doc in docs:
                doc_dict = dict(doc)
                turns = conn.execute("""
                    SELECT q.content AS question, a.content AS answer,
                           a.task_mode, a.timestamp
                    FROM messages q
                    JOIN messages a ON a.id = q.id + 1
                                   AND a.role = 'assistant'
                                   AND a.session_id = q.session_id
                    JOIN sessions s ON s.id = q.session_id
                    WHERE q.role = 'user' AND s.document_id = ?
                    ORDER BY q.id ASC
                """, (doc_dict["document_id"],)).fetchall()
                doc_dict["turns"] = [dict(t) for t in turns]
                if doc_dict["turns"]:
                    result.append(doc_dict)
            return result


def get_document_by_id(doc_id: int) -> dict:
    with _get_conn() as conn:
        p = "%s" if _USE_PG else "?"
        if _USE_PG:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, filename, doc_type, num_pages, summary, loaded_at FROM documents WHERE id = {p}",
                (doc_id,)
            )
            row = cur.fetchone()
            cur.close()
        else:
            row = conn.execute(
                f"SELECT id, filename, doc_type, num_pages, summary, loaded_at FROM documents WHERE id = {p}",
                (doc_id,)
            ).fetchone()
        if not row:
            raise ValueError(f"No document with id={doc_id}")
        return dict(row)