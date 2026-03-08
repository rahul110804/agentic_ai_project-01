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
} from "@/types"

// Base URL comes from .env.local
// NEXT_PUBLIC_ prefix makes it available in the browser
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"


// ── 1. Upload PDF ─────────────────────────────────────────────

export async function uploadPDF(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append("file", file)

  const res = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body:   formData,
    // Note: do NOT set Content-Type header manually for FormData
    // the browser sets it automatically with the correct boundary
  })

  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || "Upload failed")
  }

  return res.json()
}


// ── 2. Check Status ───────────────────────────────────────────
// Called on page load — checks if a PDF is already loaded
// so the UI can restore the chat state

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


// ── 4. Stream Chat ────────────────────────────────────────────
// The most important function.
// Opens a streaming connection and fires callbacks as events arrive.
//
// Why callbacks instead of returning data?
// Because events arrive over time — we need to update the UI
// as each event arrives, not wait for everything to finish.

export interface StreamCallbacks {
  onTaskDetected: (event: SSETaskDetected) => void  // mode detected
  onStep:         (event: SSEStep)         => void  // thinking step arrived
  onObservation:  (event: SSEObservation)  => void  // tool result arrived
  onAnswer:       (event: SSEAnswer)       => void  // final answer arrived
  onError:        (event: SSEError)        => void  // something went wrong
  onDone:         ()                       => void  // stream fully complete
}

export async function streamChat(
  question:      string,
  mode_override: TaskMode | null,
  callbacks:     StreamCallbacks,
): Promise<void> {

  // POST to /chat/stream with the question
  const res = await fetch(`${API_URL}/chat/stream`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ question, mode_override }),
  })

  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || "Chat request failed")
  }

  // res.body is a ReadableStream
  // We read it chunk by chunk using a reader
  const reader  = res.body!.getReader()
  const decoder = new TextDecoder()
  let   buffer  = ""   // accumulates partial chunks

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    // Decode the raw bytes into a string and add to buffer
    buffer += decoder.decode(value, { stream: true })

    // SSE format: each event is "data: {...}\n\n"
    // Split on double newline to get individual events
    const lines = buffer.split("\n\n")

    // Last element might be incomplete — keep it in buffer
    buffer = lines.pop() || ""

    for (const line of lines) {
      // Each line starts with "data: "
      if (!line.startsWith("data: ")) continue

      const raw = line.slice(6).trim()   // remove "data: " prefix

      // [DONE] is the stream end signal — not JSON
      if (raw === "[DONE]") {
        callbacks.onDone()
        return
      }

      // Parse and route to the right callback
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
        // Malformed JSON — skip silently
        console.warn("Could not parse SSE event:", raw)
      }
    }
  }

  // Stream ended without [DONE] — still call onDone
  callbacks.onDone()
}