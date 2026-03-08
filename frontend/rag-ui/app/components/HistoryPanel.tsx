// app/components/HistoryPanel.tsx
"use client"

import { useState } from "react"

interface HistoryTurn {
  question: string
  answer:   string
}

interface Props {
  history:  HistoryTurn[]
  isOpen:   boolean
  onToggle: () => void
  onSelect: (turn: HistoryTurn) => void
}

export default function HistoryPanel({
  history,
  isOpen,
  onToggle,
  onSelect,
}: Props) {
  const [selected, setSelected] = useState<number | null>(null)

  function handleSelect(turn: HistoryTurn, index: number) {
    setSelected(index)
    onSelect(turn)
  }

  return (
    <div className={`
      flex-shrink-0 flex flex-col border-r border-gray-800
      bg-gray-900 transition-all duration-300
      ${isOpen ? "w-64" : "w-10"}
    `}>

      {/* Toggle button */}
      <button
        onClick={onToggle}
        className="flex items-center justify-between px-3 py-3
                   hover:bg-gray-800 transition-colors border-b
                   border-gray-800 flex-shrink-0"
        title={isOpen ? "Collapse history" : "Expand history"}
      >
        {isOpen ? (
          <>
            <span className="text-gray-300 text-xs font-medium">
              History
            </span>
            <span className="text-gray-500 text-xs">←</span>
          </>
        ) : (
          <span className="text-gray-500 text-sm mx-auto">🕐</span>
        )}
      </button>

      {/* History list — only visible when open */}
      {isOpen && (
        <div className="flex-1 overflow-y-auto">

          {/* Empty state */}
          {history.length === 0 && (
            <div className="px-3 py-6 text-center">
              <p className="text-gray-600 text-xs">
                No history yet.
              </p>
              <p className="text-gray-700 text-xs mt-1">
                Ask a question to get started.
              </p>
            </div>
          )}

          {/* Turn cards */}
          {history.map((turn, index) => (
            <button
              key={index}
              onClick={() => handleSelect(turn, index)}
              className={`
                w-full text-left px-3 py-3 border-b border-gray-800/50
                hover:bg-gray-800 transition-colors
                ${selected === index ? "bg-gray-800 border-l-2 border-l-violet-500" : ""}
              `}
            >
              {/* Question */}
              <p className="text-gray-300 text-xs font-medium leading-relaxed line-clamp-2">
                {turn.question}
              </p>

              {/* Answer preview */}
              <p className="text-gray-600 text-xs mt-1 line-clamp-2 leading-relaxed">
                {turn.answer
                  .replace(/#{1,6}\s/g, "")     // strip markdown headers
                  .replace(/\*\*/g, "")          // strip bold
                  .replace(/\*/g, "")            // strip italic
                  .slice(0, 100)}
                ...
              </p>

              {/* Turn number */}
              <p className="text-gray-700 text-xs mt-1.5">
                Turn {index + 1}
              </p>
            </button>
          ))}
        </div>
      )}

      {/* Turn count badge at bottom when collapsed */}
      {!isOpen && history.length > 0 && (
        <div className="mt-auto pb-3 flex justify-center">
          <span className="text-xs text-gray-600">
            {history.length}
          </span>
        </div>
      )}
    </div>
  )
}