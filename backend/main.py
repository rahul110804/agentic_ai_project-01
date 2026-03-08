"""
main.py
-------
FastAPI application — the backend server.

Run with:
    uvicorn main:app --reload --port 8000
"""

import json
import asyncio
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import settings, validate_settings, is_allowed_file, get_upload_path
from models import (
    ChatRequest,
    UploadResponse,
    DocumentMetaResponse,
    StatusResponse,
    ResetResponse,
    HistoryResponse,
    ConversationTurn,
    ErrorResponse,
    TaskModeEnum,
)
from agentic_rag import AgenticRAG, TaskMode
from database import init_db, save_document, create_session, save_turn, get_all_history


# ============================================================
# APP INIT
# ============================================================

app = FastAPI(
    title       = settings.API_TITLE,
    version     = settings.API_VERSION,
    description = settings.API_DESCRIPTION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.CORS_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

rag = AgenticRAG()

# Active session id — set when a PDF is loaded, used when saving messages
_current_session_id: Optional[int] = None


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():
    print("\n" + "=" * 50)
    print("  🚀 Agentic RAG API starting...")
    print("=" * 50)
    validate_settings()
    init_db()                               # creates tables if they don't exist
    print(f"📡 Docs at: http://localhost:{settings.PORT}/docs\n")


# ============================================================
# HELPERS
# ============================================================

def _doc_meta_to_response(meta) -> DocumentMetaResponse:
    return DocumentMetaResponse(
        filename    = meta.filename,
        num_pages   = meta.num_pages,
        num_chunks  = meta.num_chunks,
        loaded_at   = meta.loaded_at,
        doc_type    = meta.doc_type,
        doc_summary = meta.doc_summary,
    )


def _map_mode(mode_override: Optional[TaskModeEnum]) -> Optional[TaskMode]:
    if mode_override is None:
        return None
    return TaskMode(mode_override.value)


async def _sse_generator(
    question:      str,
    mode_override: Optional[TaskMode],
) -> AsyncGenerator[str, None]:
    """
    Streams SSE events from the agent.
    After the answer event arrives, persists the full turn to SQLite.
    DB failure never breaks the stream — it just logs a warning.
    """
    global _current_session_id

    last_answer    = None
    last_task_mode = "general"
    last_doc_type  = "unknown"

    try:
        for event in rag.ask_streaming(question, mode_override):
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(0)

            # Capture answer so we can persist after streaming completes
            if event.get("type") == "answer":
                last_answer    = event.get("answer", "")
                last_task_mode = str(event.get("task_mode", "general"))
                last_doc_type  = str(event.get("doc_type", "unknown"))

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    finally:
        # Persist completed turn to DB
        if last_answer and _current_session_id is not None:
            try:
                save_turn(
                    session_id = _current_session_id,
                    question   = question,
                    answer     = last_answer,
                    task_mode  = last_task_mode,
                    doc_type   = last_doc_type,
                )
            except Exception as db_err:
                print(f"⚠️  DB save failed (non-critical): {db_err}")

        yield "data: [DONE]\n\n"


# ============================================================
# ENDPOINTS
# ============================================================

@app.post(
    "/upload",
    response_model = UploadResponse,
    status_code    = status.HTTP_200_OK,
    summary        = "Upload and process a PDF",
    tags           = ["Document"],
)
async def upload_pdf(file: UploadFile = File(...)):
    global _current_session_id

    # Validate file type
    if not is_allowed_file(file.filename or ""):
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = f"Only PDF files allowed. Got: {file.filename}",
        )

    # Validate file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail      = f"File too large ({size_mb:.1f}MB). Max: {settings.MAX_FILE_SIZE_MB}MB",
        )

    # Save file to disk
    upload_path = get_upload_path(file.filename or "document.pdf")
    try:
        with open(upload_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail      = f"Failed to save file: {e}",
        )

    # Process with RAG engine
    try:
        meta = rag.load_pdf(str(upload_path))
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail      = f"Failed to process PDF: {e}",
        )

    # Persist document + open a new session in DB
    try:
        doc_id              = save_document(
            filename   = meta.filename,
            doc_type   = str(meta.doc_type),
            num_pages  = meta.num_pages,
            num_chunks = meta.num_chunks,
            summary    = meta.doc_summary,
            loaded_at  = meta.loaded_at,
        )
        _current_session_id = create_session(doc_id)
        print(f"💾 DB: document_id={doc_id} | session_id={_current_session_id}")
    except Exception as db_err:
        # DB failure must never block the user — RAG still works fine
        print(f"⚠️  DB save failed (non-critical): {db_err}")
        _current_session_id = None

    return UploadResponse(
        success  = True,
        message  = f"Successfully processed '{meta.filename}'",
        document = _doc_meta_to_response(meta),
    )


@app.post(
    "/chat/stream",
    summary = "Ask a question — returns SSE stream",
    tags    = ["Chat"],
)
async def chat_stream(request: ChatRequest):
    if not rag.is_ready:
        raise HTTPException(
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
            detail      = "No document loaded. Upload a PDF first.",
        )

    mode = _map_mode(request.mode_override)

    return StreamingResponse(
        _sse_generator(request.question, mode),
        media_type = "text/event-stream",
        headers    = {
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get(
    "/status",
    response_model = StatusResponse,
    summary        = "Check if document is loaded",
    tags           = ["Document"],
)
async def get_status():
    if rag.is_ready and rag.doc_meta:
        return StatusResponse(
            is_ready = True,
            document = _doc_meta_to_response(rag.doc_meta),
            message  = f"'{rag.doc_meta.filename}' is loaded and ready.",
        )
    return StatusResponse(
        is_ready = False,
        document = None,
        message  = "No document loaded.",
    )


@app.get(
    "/history",
    response_model = HistoryResponse,
    summary        = "Get conversation history — persistent across restarts",
    tags           = ["Chat"],
)
async def get_history():
    """
    Reads from SQLite first — survives server restarts.
    Falls back to in-memory history if DB read fails.
    """
    try:
        db_turns = get_all_history(limit=100)
        if db_turns:
            turns = [
                ConversationTurn(question=t["question"], answer=t["answer"])
                for t in db_turns
            ]
            return HistoryResponse(turns=turns, total=len(turns))
    except Exception as db_err:
        print(f"⚠️  DB read failed, falling back to in-memory: {db_err}")

    # Fallback — in-memory history from current session
    turns = [
        ConversationTurn(question=t["question"], answer=t["answer"])
        for t in rag.conversation_history
    ]
    return HistoryResponse(turns=turns, total=len(turns))


@app.delete(
    "/reset",
    response_model = ResetResponse,
    summary        = "Clear document and conversation",
    tags           = ["Document"],
)
async def reset():
    global _current_session_id
    rag.reset()
    _current_session_id = None      # close active session

    # Note: DB history is intentionally preserved across resets.
    # Past sessions remain on record — only the active document is cleared.
    try:
        for pdf_file in settings.UPLOAD_DIR.glob("*.pdf"):
            pdf_file.unlink()
    except Exception:
        pass

    return ResetResponse(
        success = True,
        message = "Cleared. Ready for a new upload.",
    )


@app.get("/health", summary="Health check", tags=["System"])
async def health():
    return {
        "status":             "ok",
        "version":            settings.API_VERSION,
        "web_search_enabled": rag.web_search_enabled,
    }


# ============================================================
# DEV ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host   = settings.HOST,
        port   = settings.PORT,
        reload = settings.RELOAD,
    )