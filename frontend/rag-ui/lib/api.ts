// lib/api.ts

import type {
  UploadResponse,
  StatusResponse,
  TaskMode,
  SSEEvent,
  SSEStep,
  SSEObservation,
  SSEAnswer,
  SSEError,
  SSETaskDetected,
  DocumentHistoryResponse,
} from "@/types"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"


// ── 1. Upload PDF ─────────────────────────────────────────────

export async function uploadPDF(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append("file", file)

  const res = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body:   formData,
  })

  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || "Upload failed")
  }

  return res.json()
}


// ── 2. Check Status ───────────────────────────────────────────

export async function checkStatus(): Promise<StatusResponse> {
  const res = await fetch(`${API_URL}/status`)
  if (!res.ok) throw new Error("Status check failed")
  return res.json()
}


// ── 3. Reset Document ─────────────────────────────────────────

export async function resetDocument(): Promise<void> {
  const res = await fetch(`${API_URL}/reset`, { method: "DELETE" })
  if (!res.ok) throw new Error("Reset failed")
}


// ── 4. Fetch Document History (ChatGPT-style) ─────────────────
// Returns all past documents, each with their full Q&A turns.
// Powers the left sidebar history panel.

export async function fetchDocumentHistory(): Promise<DocumentHistoryResponse> {
  try {
    const res = await fetch(`${API_URL}/history/documents`)
    if (!res.ok) return { documents: [] }
    return res.json()
  } catch {
    return { documents: [] }
  }
}


// ── 5. Stream Chat ────────────────────────────────────────────

export interface StreamCallbacks {
  onTaskDetected: (event: SSETaskDetected) => void
  onStep:         (event: SSEStep)         => void
  onObservation:  (event: SSEObservation)  => void
  onAnswer:       (event: SSEAnswer)       => void
  onError:        (event: SSEError)        => void
  onDone:         ()                       => void
}

export async function streamChat(
  question:      string,
  mode_override: TaskMode | null,
  callbacks:     StreamCallbacks,
): Promise<void> {

  const res = await fetch(`${API_URL}/chat/stream`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ question, mode_override }),
  })

  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || "Chat request failed")
  }

  const reader  = res.body!.getReader()
  const decoder = new TextDecoder()
  let   buffer  = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n\n")
    buffer = lines.pop() || ""

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue
      const raw = line.slice(6).trim()

      if (raw === "[DONE]") {
        callbacks.onDone()
        return
      }

      try {
        const event = JSON.parse(raw) as SSEEvent
        switch (event.type) {
          case "task_detected": callbacks.onTaskDetected(event); break
          case "step":          callbacks.onStep(event);         break
          case "observation":   callbacks.onObservation(event);  break
          case "answer":        callbacks.onAnswer(event);       break
          case "error":         callbacks.onError(event);        break
        }
      } catch {
        console.warn("Could not parse SSE event:", raw)
      }
    }
  }

  callbacks.onDone()
}