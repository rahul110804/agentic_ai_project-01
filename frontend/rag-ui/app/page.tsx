// app/page.tsx
"use client"

import { useState, useEffect, useCallback } from "react"
import PDFUpload    from "./components/PDFUpload"
import StatusBar    from "./components/StatusBar"
import ChatWindow   from "./components/ChatWindow"
import ChatInput    from "./components/ChatInput"
import HistoryPanel from "./components/HistoryPanel"
import ComparePanel from "./components/ComparePanel"
import {
  checkStatus,
  resetDocument,
  streamChat,
  fetchDocumentHistory,
} from "@/lib/api"
import type {
  DocumentMeta,
  Message,
  AgentStep,
  TaskMode,
  DocumentHistory,
} from "@/types"

// ── helpers ───────────────────────────────────────────────────
function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}
function now() {
  return new Date().toISOString()
}

export default function Page() {

  // ── state ─────────────────────────────────────────────────
  const [docMeta,          setDocMeta]          = useState<DocumentMeta | null>(null)
  const [messages,         setMessages]         = useState<Message[]>([])
  const [isStreaming,      setIsStreaming]       = useState(false)
  const [streamingSteps,   setStreamingSteps]   = useState<AgentStep[]>([])
  const [streamingMode,    setStreamingMode]    = useState<TaskMode | null>(null)
  const [isCheckingStatus, setIsCheckingStatus] = useState(true)
  const [isHistoryOpen,    setIsHistoryOpen]    = useState(true)
  const [showCompare,      setShowCompare]      = useState(false)

  // DocumentHistory[] — one entry per PDF, each with all its turns
  const [documentHistory,  setDocumentHistory]  = useState<DocumentHistory[]>([])
  // Which document's conversation is currently shown in chat
  const [activeDocId,      setActiveDocId]      = useState<number | null>(null)

  // ── refresh document history from backend ─────────────────
  const refreshHistory = useCallback(async () => {
    try {
      const data = await fetchDocumentHistory()
      const docs: DocumentHistory[] = Array.isArray(data)
        ? data
        : Array.isArray((data as any).documents)
          ? (data as any).documents
          : []
      setDocumentHistory(docs)
    } catch {
      setDocumentHistory([])
    }
  }, [])

  // ── on mount ──────────────────────────────────────────────
  useEffect(() => {
    checkStatus()
      .then(res => {
        if (res.is_ready && res.document) setDocMeta(res.document)
      })
      .catch(console.error)
      .finally(() => setIsCheckingStatus(false))

    refreshHistory()
  }, [refreshHistory])

  // ── upload success ────────────────────────────────────────
  function handleUploadSuccess(doc: DocumentMeta) {
    setDocMeta(doc)
    setMessages([])
    setStreamingSteps([])
    setActiveDocId(null)
    refreshHistory()
  }

  // ── reset ─────────────────────────────────────────────────
  async function handleReset() {
    try { await resetDocument() } catch (e) { console.error(e) }
    setDocMeta(null)
    setMessages([])
    setStreamingSteps([])
    setStreamingMode(null)
    setActiveDocId(null)
  }

  // ── select a past document from history sidebar ───────────
  // Loads all its Q&A turns into the chat window as read-only messages
  function handleSelectDocument(doc: DocumentHistory) {
    setActiveDocId(doc.document_id)

    const rebuilt: Message[] = []
    for (const turn of doc.turns) {
      rebuilt.push({
        id:        generateId(),
        role:      "user",
        content:   turn.question,
        timestamp: turn.timestamp ?? now(),
      })
      rebuilt.push({
        id:        generateId(),
        role:      "assistant",
        content:   turn.answer,
        timestamp: turn.timestamp ?? now(),
        steps:     [],
      })
    }
    setMessages(rebuilt)
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
    const assistantId  = generateId()
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
          // Refresh sidebar so new turn appears immediately
          refreshHistory()
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
  }, [isStreaming, refreshHistory])

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
    return (
      <div className="relative">
        <PDFUpload onUploadSuccess={handleUploadSuccess} />

        {documentHistory.length >= 2 && (
          <button
            onClick={() => setShowCompare(true)}
            className="fixed bottom-6 right-6 flex items-center gap-2 px-4 py-2.5
                       bg-violet-700 hover:bg-violet-600 text-white text-sm font-medium
                       rounded-xl shadow-lg transition-colors z-40"
          >
            📊 Compare PDFs
          </button>
        )}

        {showCompare && (
          <ComparePanel
            documents={documentHistory}
            onClose={() => setShowCompare(false)}
          />
        )}
      </div>
    )
  }

  // ── doc loaded → chat screen ──────────────────────────────
  return (
    <div className="h-screen flex flex-col bg-gray-950">

      <StatusBar doc={docMeta} onReset={handleReset} />

      <div className="flex flex-1 overflow-hidden">

        {/* History sidebar — grouped by document */}
        <HistoryPanel
          documents={documentHistory}
          activeDocumentId={activeDocId}
          isOpen={isHistoryOpen}
          onToggle={() => setIsHistoryOpen(p => !p)}
          onSelectDocument={handleSelectDocument}
        />

        {/* Chat area */}
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

      {/* Compare button */}
      <button
        onClick={() => setShowCompare(true)}
        className="fixed bottom-6 right-6 flex items-center gap-2 px-4 py-2.5
                   bg-violet-700 hover:bg-violet-600 text-white text-sm font-medium
                   rounded-xl shadow-lg transition-colors z-40"
      >
        📊 Compare PDFs
      </button>

      {showCompare && (
        <ComparePanel
          documents={documentHistory}
          onClose={() => setShowCompare(false)}
        />
      )}

    </div>
  )
}