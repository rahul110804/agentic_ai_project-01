// app/page.tsx
"use client"

import { useState, useEffect, useCallback } from "react"
import PDFUpload    from "./components/PDFUpload"
import StatusBar    from "./components/StatusBar"
import ChatWindow   from "./components/ChatWindow"
import ChatInput    from "./components/ChatInput"
import HistoryPanel from "./components/HistoryPanel"
import {
  checkStatus,
  resetDocument,
  streamChat,
} from "@/lib/api"
import type { DocumentMeta, Message, AgentStep, TaskMode } from "@/types"

// ── helpers ───────────────────────────────────────────────────
function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}
function now() {
  return new Date().toISOString()
}

interface HistoryTurn {
  question: string
  answer:   string
}

// ── fetch history from backend ────────────────────────────────
async function fetchHistory(): Promise<HistoryTurn[]> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/history`
    )
    if (!res.ok) return []
    const data = await res.json()
    return data.turns || []
  } catch {
    return []
  }
}

export default function Page() {

  // ── state ─────────────────────────────────────────────────
  const [docMeta,          setDocMeta]          = useState<DocumentMeta | null>(null)
  const [messages,         setMessages]         = useState<Message[]>([])
  const [isStreaming,      setIsStreaming]       = useState(false)
  const [streamingSteps,   setStreamingSteps]   = useState<AgentStep[]>([])
  const [streamingMode,    setStreamingMode]    = useState<TaskMode | null>(null)
  const [isCheckingStatus, setIsCheckingStatus] = useState(true)
  const [history,          setHistory]          = useState<HistoryTurn[]>([])
  const [isHistoryOpen,    setIsHistoryOpen]    = useState(true)

  // ── on mount ──────────────────────────────────────────────
  useEffect(() => {
    checkStatus()
      .then(async res => {
        if (res.is_ready && res.document) {
          setDocMeta(res.document)
          // Load existing history if doc already loaded
          const turns = await fetchHistory()
          setHistory(turns)
        }
      })
      .catch(console.error)
      .finally(() => setIsCheckingStatus(false))
  }, [])

  // ── upload success ────────────────────────────────────────
  function handleUploadSuccess(doc: DocumentMeta) {
    setDocMeta(doc)
    setMessages([])
    setStreamingSteps([])
    setHistory([])
  }

  // ── reset ─────────────────────────────────────────────────
  async function handleReset() {
    try { await resetDocument() } catch (e) { console.error(e) }
    setDocMeta(null)
    setMessages([])
    setStreamingSteps([])
    setStreamingMode(null)
    setHistory([])
  }

  // ── history turn selected — scroll to message in chat ─────
  function handleHistorySelect(turn: HistoryTurn) {
    // Find the message in chat and highlight it
    // If not found (e.g. page was refreshed), add it as read-only
    const exists = messages.find(
      m => m.role === "user" && m.content === turn.question
    )
    if (!exists) {
      // Restore the turn as messages so user can read it
      const userMsg: Message = {
        id:        generateId(),
        role:      "user",
        content:   turn.question,
        timestamp: now(),
      }
      const assistantMsg: Message = {
        id:        generateId(),
        role:      "assistant",
        content:   turn.answer,
        timestamp: now(),
        steps:     [],
      }
      setMessages(prev => [...prev, userMsg, assistantMsg])
    }
  }

  // ── send message ──────────────────────────────────────────
  const handleSend = useCallback(async (
    question: string,
    mode:     TaskMode | null,
  ) => {
    if (isStreaming) return

    const userMsg: Message = {
      id:        generateId(),
      role:      "user",
      content:   question,
      timestamp: now(),
    }

    const assistantId = generateId()
    const assistantMsg: Message = {
      id:        assistantId,
      role:      "assistant",
      content:   "",
      timestamp: now(),
      steps:     [],
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)
    setStreamingSteps([])
    setStreamingMode(null)

    const localSteps: AgentStep[] = []

    try {
      await streamChat(question, mode, {

        onTaskDetected: (event) => {
          setStreamingMode(event.mode)
        },

        onStep: (event) => {
          const newStep: AgentStep = {
            iteration:    event.iteration,
            thought:      event.thought,
            action:       event.action,
            action_input: event.action_input,
            observation:  "",
          }
          localSteps.push(newStep)
          setStreamingSteps([...localSteps])
        },

        onObservation: (event) => {
          const step = localSteps.find(s => s.iteration === event.iteration)
          if (step) {
            step.observation = event.observation
            setStreamingSteps([...localSteps])
          }
        },

        onAnswer: (event) => {
          setMessages(prev => prev.map(msg =>
            msg.id === assistantId
              ? {
                  ...msg,
                  content:   event.answer,
                  task_mode: event.task_mode,
                  doc_type:  event.doc_type,
                  steps:     [...localSteps],
                }
              : msg
          ))
          // Refresh history panel after answer arrives
          fetchHistory().then(setHistory)
        },

        onError: (event) => {
          setMessages(prev => prev.map(msg =>
            msg.id === assistantId
              ? { ...msg, content: `❌ Error: ${event.message}` }
              : msg
          ))
        },

        onDone: () => {
          setIsStreaming(false)
          setStreamingSteps([])
          setStreamingMode(null)
        },
      })

    } catch (err: any) {
      setMessages(prev => prev.map(msg =>
        msg.id === assistantId
          ? { ...msg, content: `❌ Failed to connect: ${err.message}` }
          : msg
      ))
      setIsStreaming(false)
      setStreamingSteps([])
    }
  }, [isStreaming])

  // ── loading ───────────────────────────────────────────────
  if (isCheckingStatus) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-violet-500
                          border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  // ── no doc → upload screen ────────────────────────────────
  if (!docMeta) {
    return <PDFUpload onUploadSuccess={handleUploadSuccess} />
  }

  // ── doc loaded → chat screen ──────────────────────────────
  return (
    <div className="h-screen flex flex-col bg-gray-950">

      {/* Top bar */}
      <StatusBar doc={docMeta} onReset={handleReset} />

      {/* Middle — history panel + chat */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left — history sidebar */}
        <HistoryPanel
          history={history}
          isOpen={isHistoryOpen}
          onToggle={() => setIsHistoryOpen(p => !p)}
          onSelect={handleHistorySelect}
        />

        {/* Right — chat area */}
        <div className="flex flex-col flex-1 overflow-hidden">
          <ChatWindow
            messages={messages}
            streamingSteps={streamingSteps}
            isStreaming={isStreaming}
            streamingMode={streamingMode}
          />
          <ChatInput
            onSend={handleSend}
            isStreaming={isStreaming}
          />
        </div>

      </div>
    </div>
  )
}