// app/components/AgentSteps.tsx
"use client"

import { useState } from "react"
import type { AgentStep, TaskMode } from "@/types"

interface Props {
  steps:       AgentStep[]
  isStreaming: boolean
  taskMode:    TaskMode | null
}

// Icon + color for each tool
const TOOL_CONFIG: Record<string, { icon: string; color: string }> = {
  critique_document: { icon: "🔍", color: "text-red-400" },
  study_summary:     { icon: "📚", color: "text-blue-400" },
  extract_data:      { icon: "📊", color: "text-yellow-400" },
  search_document:   { icon: "🔎", color: "text-green-400" },
  calculate:         { icon: "🧮", color: "text-purple-400" },
  get_current_date:  { icon: "📅", color: "text-gray-400" },
  finish:            { icon: "✅", color: "text-emerald-400" },
}

const MODE_CONFIG: Record<string, { label: string; color: string }> = {
  critic:  { label: "Critic Mode",  color: "text-red-400 bg-red-500/10 border-red-500/20" },
  study:   { label: "Study Mode",   color: "text-blue-400 bg-blue-500/10 border-blue-500/20" },
  extract: { label: "Extract Mode", color: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" },
  explain: { label: "Explain Mode", color: "text-purple-400 bg-purple-500/10 border-purple-500/20" },
  general: { label: "General Mode", color: "text-green-400 bg-green-500/10 border-green-500/20" },
  auto:    { label: "Auto Mode",    color: "text-gray-400 bg-gray-500/10 border-gray-500/20" },
}

export default function AgentSteps({ steps, isStreaming, taskMode }: Props) {
  const [isOpen, setIsOpen] = useState(true)

  if (steps.length === 0 && !isStreaming) return null

  const modeConfig = taskMode ? MODE_CONFIG[taskMode] : null

  return (
    <div className="mx-4 mb-2 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">

      {/* Header — clickable to collapse */}
      <button
        onClick={() => setIsOpen(p => !p)}
        className="w-full px-4 py-3 flex items-center justify-between
                   hover:bg-gray-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {/* Pulsing dot while streaming */}
          {isStreaming && (
            <span className="w-2 h-2 bg-violet-500 rounded-full animate-pulse" />
          )}
          <span className="text-gray-300 text-sm font-medium">
            {isStreaming ? "Agent is thinking..." : `Completed in ${steps.length} step${steps.length !== 1 ? "s" : ""}`}
          </span>

          {/* Mode badge */}
          {modeConfig && (
            <span className={`text-xs px-2 py-0.5 rounded-full border ${modeConfig.color}`}>
              {modeConfig.label}
            </span>
          )}
        </div>

        {/* Chevron */}
        <span className={`text-gray-500 text-xs transition-transform duration-200
                          ${isOpen ? "rotate-180" : ""}`}>
          ▼
        </span>
      </button>

      {/* Steps list */}
      {isOpen && (
        <div className="border-t border-gray-800 divide-y divide-gray-800/50">
          {steps.map((step) => {
            const toolInfo = TOOL_CONFIG[step.action] || { icon: "🔧", color: "text-gray-400" }

            return (
              <div key={step.iteration} className="px-4 py-3 space-y-2">

                {/* Step number + action */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-600 font-mono">
                    {step.iteration}
                  </span>
                  <span className={`text-xs font-medium ${toolInfo.color}`}>
                    {toolInfo.icon} {step.action}
                  </span>
                </div>

                {/* Thought */}
                {step.thought && (
                  <p className="text-gray-400 text-xs leading-relaxed pl-5">
                    💭 {step.thought}
                  </p>
                )}

                {/* Action input — only show if meaningful */}
                {step.action_input && step.action_input.length > 0 && step.action !== "finish" && (
                  <p className="text-gray-500 text-xs pl-5 font-mono truncate">
                    → {step.action_input.slice(0, 120)}
                    {step.action_input.length > 120 ? "..." : ""}
                  </p>
                )}

                {/* Observation */}
                {step.observation && (
                  <div className="pl-5">
                    <p className="text-gray-600 text-xs mb-1">Result:</p>
                    <p className="text-gray-400 text-xs leading-relaxed
                                  bg-gray-800/50 rounded-lg px-3 py-2 line-clamp-3">
                      {step.observation.slice(0, 200)}
                      {step.observation.length > 200 ? "..." : ""}
                    </p>
                  </div>
                )}
              </div>
            )
          })}

          {/* Loading indicator for next step */}
          {isStreaming && (
            <div className="px-4 py-3 flex items-center gap-2">
              <span className="text-gray-600 text-xs font-mono">
                {steps.length + 1}
              </span>
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-bounce"
                      style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-bounce"
                      style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 bg-violet-500 rounded-full animate-bounce"
                      style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}