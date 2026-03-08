// app/components/ChatWindow.tsx
"use client"

import { useEffect, useRef } from "react"
import MessageBubble from "./MessageBubble"
import AgentSteps from "./AgentSteps"
import type { Message, AgentStep, TaskMode } from "@/types"

interface Props {
  messages:      Message[]
  streamingSteps: AgentStep[]
  isStreaming:   boolean
  streamingMode: TaskMode | null
}

export default function ChatWindow({
  messages,
  streamingSteps,
  isStreaming,
  streamingMode,
}: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto scroll to bottom whenever messages or steps update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamingSteps])

  return (
    <div className="flex-1 overflow-y-auto py-4 space-y-1">

      {/* Empty state */}
      {messages.length === 0 && !isStreaming && (
        <div className="h-full flex flex-col items-center justify-center
                        text-center px-6 py-20">
          <div className="text-5xl mb-4">💬</div>
          <h2 className="text-white font-semibold text-xl mb-2">
            Document ready — ask anything
          </h2>
          <p className="text-gray-500 text-sm max-w-md">
            Try asking it to critique your document, summarize for study,
            extract key data, or just answer a question about it.
          </p>

          {/* Suggestion chips */}
          <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-lg">
            {[
              "Find problems and suggest fixes",
              "Summarize this for my exam",
              "Extract all key dates and names",
              "What is this document about?",
              "Give me flashcards to study",
              "Explain the main findings simply",
            ].map(suggestion => (
              <span
                key={suggestion}
                className="text-xs px-3 py-1.5 bg-gray-800 border border-gray-700
                           text-gray-400 rounded-full"
              >
                {suggestion}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      {messages.map((message, index) => {
        const isLastAssistant =
          message.role === "assistant" &&
          index === messages.length - 1

        return (
          <div key={message.id}>
            {/* Agent steps above assistant messages */}
            {message.role === "assistant" && (
              <AgentSteps
                // While streaming the last message gets live steps
                // After streaming it gets the steps saved on the message
                steps={isLastAssistant && isStreaming
                  ? streamingSteps
                  : (message.steps || [])}
                isStreaming={isLastAssistant && isStreaming}
                taskMode={isLastAssistant && isStreaming
                  ? streamingMode
                  : (message.task_mode || null)}
              />
            )}
            <MessageBubble message={message} />
          </div>
        )
      })}

      {/* Show AgentSteps when streaming but no assistant message yet */}
      {isStreaming && (
        messages.length === 0 ||
        messages[messages.length - 1].role === "user"
      ) && (
        <AgentSteps
          steps={streamingSteps}
          isStreaming={isStreaming}
          taskMode={streamingMode}
        />
      )}

      {/* Invisible div at bottom — scroll target */}
      <div ref={bottomRef} />
    </div>
  )
}