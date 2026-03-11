// app/components/HistoryPanel.tsx
"use client"

import { useState } from "react"
import type { DocumentHistory, HistoryTurn } from "@/types"

interface Props {
  documents:        DocumentHistory[]
  activeDocumentId: number | null
  isOpen:           boolean
  onToggle:         () => void
  onSelectDocument: (doc: DocumentHistory) => void
}

const DOC_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  resume:          { label: "Resume",   color: "text-violet-400 bg-violet-500/10 border-violet-500/20" },
  research_paper:  { label: "Research", color: "text-blue-400 bg-blue-500/10 border-blue-500/20"       },
  news_article:    { label: "News",     color: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20" },
  legal_document:  { label: "Legal",    color: "text-red-400 bg-red-500/10 border-red-500/20"          },
  textbook:        { label: "Textbook", color: "text-green-400 bg-green-500/10 border-green-500/20"    },
  business_report: { label: "Business", color: "text-orange-400 bg-orange-500/10 border-orange-500/20" },
  unknown:         { label: "Doc",      color: "text-gray-400 bg-gray-500/10 border-gray-500/20"       },
}

function formatDate(iso: string): string {
  try {
    const d       = new Date(iso)
    const now     = new Date()
    const diffMs  = now.getTime() - d.getTime()
    const diffDay = Math.floor(diffMs / 86_400_000)
    if (diffDay === 0) return "Today"
    if (diffDay === 1) return "Yesterday"
    if (diffDay < 7)  return `${diffDay}d ago`
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
  } catch { return "" }
}

// ── Single expandable document conversation card ──────────────
function DocCard({
  doc,
  isActive,
  onSelect,
}: {
  doc:      DocumentHistory
  isActive: boolean
  onSelect: (doc: DocumentHistory) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const typeConfig = DOC_TYPE_CONFIG[doc.doc_type] ?? DOC_TYPE_CONFIG.unknown
  const lastTurn   = doc.turns[doc.turns.length - 1]

  return (
    <div className={`
      border-b border-gray-800/60
      ${isActive ? "bg-gray-800/50 border-l-2 border-l-violet-500" : "border-l-2 border-l-transparent"}
    `}>

      {/* ── Document header row (click = load convo) ── */}
      <div
        className="flex items-start gap-2 px-3 py-3 hover:bg-gray-800/40 transition-colors cursor-pointer"
        onClick={() => onSelect(doc)}
      >
        {/* Expand / collapse turns toggle */}
        <button
          onClick={e => { e.stopPropagation(); setExpanded(p => !p) }}
          className="mt-0.5 flex-shrink-0 text-gray-600 hover:text-gray-400 transition-colors text-xs w-4"
          title={expanded ? "Collapse" : "Expand turns"}
        >
          {expanded ? "▾" : "▸"}
        </button>

        <div className="flex-1 min-w-0">
          {/* Filename */}
          <p className="text-gray-200 text-xs font-semibold truncate leading-relaxed">
            📄 {doc.filename.replace(/\.pdf$/i, "")}
          </p>

          {/* Badge row */}
          <div className="flex items-center gap-1.5 mt-1">
            <span className={`text-xs px-1.5 py-0.5 rounded border ${typeConfig.color}`}>
              {typeConfig.label}
            </span>
            <span className="text-gray-600 text-xs">
              {doc.turns.length} {doc.turns.length === 1 ? "msg" : "msgs"}
            </span>
            <span className="text-gray-700 text-xs ml-auto flex-shrink-0">
              {formatDate(doc.loaded_at)}
            </span>
          </div>

          {/* Last question preview — only when collapsed */}
          {!expanded && lastTurn && (
            <p className="text-gray-500 text-xs mt-1.5 line-clamp-2 leading-relaxed">
              {lastTurn.question}
            </p>
          )}
        </div>
      </div>

      {/* ── Expanded turns list ── */}
      {expanded && doc.turns.length > 0 && (
        <div className="pb-2 pl-7 pr-3 space-y-1">
          {doc.turns.map((turn, i) => (
            <button
              key={i}
              onClick={() => onSelect(doc)}
              className="w-full text-left group"
              title={turn.question}
            >
              <div className="flex items-start gap-1.5 px-2 py-1.5 rounded-lg
                              hover:bg-gray-700/40 transition-colors">
                <span className="text-gray-600 text-xs mt-0.5 flex-shrink-0">Q{i + 1}</span>
                <p className="text-gray-400 text-xs line-clamp-2 leading-relaxed
                               group-hover:text-gray-200 transition-colors">
                  {turn.question}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}

      {expanded && doc.turns.length === 0 && (
        <p className="pl-9 pr-3 pb-3 text-gray-600 text-xs italic">No messages yet</p>
      )}
    </div>
  )
}


// ── Main panel ────────────────────────────────────────────────
export default function HistoryPanel({
  documents,
  activeDocumentId,
  isOpen,
  onToggle,
  onSelectDocument,
}: Props) {

  const safeDocs = Array.isArray(documents) ? documents : []

  return (
    <div className={`
      flex-shrink-0 flex flex-col border-r border-gray-800
      bg-gray-900/80 transition-all duration-300
      ${isOpen ? "w-64" : "w-10"}
    `}>

      {/* Toggle */}
      <button
        onClick={onToggle}
        className="flex items-center justify-between px-3 py-3
                   hover:bg-gray-800 transition-colors border-b
                   border-gray-800 flex-shrink-0"
        title={isOpen ? "Collapse history" : "Expand history"}
      >
        {isOpen ? (
          <>
            <div className="flex items-center gap-2">
              <span className="text-gray-400 text-sm">🕐</span>
              <span className="text-gray-300 text-xs font-medium">History</span>
            </div>
            <span className="text-gray-500 text-xs">←</span>
          </>
        ) : (
          <span className="text-gray-500 text-sm mx-auto">🕐</span>
        )}
      </button>

      {/* Document conversation list */}
      {isOpen && (
        <div className="flex-1 overflow-y-auto">

          {safeDocs.length === 0 && (
            <div className="px-4 py-8 text-center">
              <p className="text-2xl mb-2">📂</p>
              <p className="text-gray-500 text-xs font-medium">No history yet</p>
              <p className="text-gray-600 text-xs mt-1">
                Upload a PDF and start chatting
              </p>
            </div>
          )}

          {safeDocs.map(doc => (
            <DocCard
              key={doc.document_id}
              doc={doc}
              isActive={doc.document_id === activeDocumentId}
              onSelect={onSelectDocument}
            />
          ))}
        </div>
      )}

      {/* Collapsed badge */}
      {!isOpen && safeDocs.length > 0 && (
        <div className="mt-auto pb-3 flex justify-center">
          <span className="text-xs text-gray-600 bg-gray-800 rounded-full
                           w-5 h-5 flex items-center justify-center">
            {safeDocs.length}
          </span>
        </div>
      )}
    </div>
  )
}