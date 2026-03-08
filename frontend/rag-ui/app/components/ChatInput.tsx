// app/components/ChatInput.tsx
"use client"

import { useState, KeyboardEvent } from "react"
import type { TaskMode } from "@/types"

interface Props {
  onSend:      (question: string, mode: TaskMode | null) => void
  isStreaming: boolean
}

const MODE_OPTIONS: { value: TaskMode | "auto"; label: string; desc: string }[] = [
  { value: "auto",    label: "Auto",    desc: "Agent decides" },
  { value: "critic",  label: "Critic",  desc: "Find problems & fixes" },
  { value: "study",   label: "Study",   desc: "Summarize & flashcards" },
  { value: "extract", label: "Extract", desc: "Pull structured data" },
  { value: "explain", label: "Explain", desc: "Simplify & clarify" },
]

export default function ChatInput({ onSend, isStreaming }: Props) {
  const [question, setQuestion] = useState("")
  const [mode, setMode]         = useState<TaskMode | "auto">("auto")

  function handleSend() {
    const trimmed = question.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed, mode === "auto" ? null : mode)
    setQuestion("")
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Send on Enter, new line on Shift+Enter
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t border-gray-800 bg-gray-950 px-4 py-3">

      {/* Mode selector */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-gray-600 text-xs">Mode:</span>
        <div className="flex gap-1 flex-wrap">
          {MODE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setMode(opt.value)}
              disabled={isStreaming}
              title={opt.desc}
              className={`
                text-xs px-2.5 py-1 rounded-lg border transition-colors
                ${mode === opt.value
                  ? "bg-violet-600 border-violet-500 text-white"
                  : "bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-600"
                }
                ${isStreaming ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
              `}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Input row */}
      <div className="flex items-end gap-2">

        {/* Textarea — grows with content */}
        <textarea
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder={
            isStreaming
              ? "Agent is thinking..."
              : "Ask anything about your document..."
          }
          rows={1}
          className={`
            flex-1 bg-gray-900 border border-gray-700 rounded-xl
            px-4 py-3 text-white text-sm placeholder-gray-600
            resize-none outline-none leading-relaxed
            focus:border-violet-500 transition-colors
            max-h-32 overflow-y-auto
            ${isStreaming ? "opacity-50 cursor-not-allowed" : ""}
          `}
          style={{ fieldSizing: "content" } as React.CSSProperties}
        />

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={isStreaming || !question.trim()}
          className={`
            w-11 h-11 rounded-xl flex items-center justify-center
            text-white font-medium transition-all flex-shrink-0
            ${isStreaming || !question.trim()
              ? "bg-gray-800 text-gray-600 cursor-not-allowed"
              : "bg-violet-600 hover:bg-violet-500 cursor-pointer"
            }
          `}
        >
          {isStreaming ? (
            <span className="w-4 h-4 border-2 border-gray-600 border-t-gray-400
                             rounded-full animate-spin" />
          ) : (
            <span>↑</span>
          )}
        </button>
      </div>

      {/* Hint */}
      <p className="text-gray-700 text-xs mt-2 text-center">
        Enter to send · Shift+Enter for new line
      </p>
    </div>
  )
}