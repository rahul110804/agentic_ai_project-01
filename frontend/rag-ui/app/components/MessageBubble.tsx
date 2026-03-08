// app/components/MessageBubble.tsx
"use client"

import ReactMarkdown from "react-markdown"
import type { Message } from "@/types"

interface Props {
  message: Message
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString([], {
    hour:   "2-digit",
    minute: "2-digit",
  })
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user"

  // ── User message ─────────────────────────────────────────────
  if (isUser) {
    return (
      <div className="flex justify-end px-4 mb-4">
        <div className="max-w-[80%] space-y-1">
          <div className="bg-violet-600 text-white px-4 py-3 rounded-2xl
                          rounded-tr-sm text-sm leading-relaxed">
            {message.content}
          </div>
          <p className="text-gray-600 text-xs text-right pr-1">
            {formatTime(message.timestamp)}
          </p>
        </div>
      </div>
    )
  }

  // ── Assistant message ────────────────────────────────────────
  return (
    <div className="flex justify-start px-4 mb-4">
      <div className="max-w-[90%] space-y-1">

        {/* AI label */}
        <div className="flex items-center gap-2 mb-1.5 pl-1">
          <div className="w-6 h-6 bg-violet-600 rounded-full flex items-center
                          justify-center text-xs">
            🤖
          </div>
          <span className="text-gray-500 text-xs">Agentic RAG</span>
        </div>

        {/* Message card */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl
                        rounded-tl-sm px-4 py-3">
          <div className="prose prose-invert prose-sm max-w-none
                          prose-headings:text-white
                          prose-headings:font-semibold
                          prose-p:text-gray-300
                          prose-p:leading-relaxed
                          prose-strong:text-white
                          prose-li:text-gray-300
                          prose-code:text-violet-300
                          prose-code:bg-gray-800
                          prose-code:px-1
                          prose-code:rounded
                          prose-pre:bg-gray-800
                          prose-pre:border
                          prose-pre:border-gray-700
                          prose-blockquote:border-violet-500
                          prose-blockquote:text-gray-400
                          prose-table:text-gray-300
                          prose-th:text-white
                          prose-hr:border-gray-700">
            <ReactMarkdown>
              {message.content}
            </ReactMarkdown>
          </div>
        </div>

        {/* Timestamp */}
        <p className="text-gray-600 text-xs pl-1">
          {formatTime(message.timestamp)}
        </p>
      </div>
    </div>
  )
}