// app/components/StatusBar.tsx
"use client"

import type { DocumentMeta, DocType } from "@/types"

interface Props {
  doc:     DocumentMeta
  onReset: () => void
}

// Color + label for each doc type badge
const DOC_TYPE_CONFIG: Record<DocType, { label: string; color: string }> = {
  resume:          { label: "Resume",          color: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
  research_paper:  { label: "Research Paper",  color: "bg-green-500/20 text-green-400 border-green-500/30" },
  news_article:    { label: "News Article",    color: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30" },
  legal_document:  { label: "Legal Document",  color: "bg-red-500/20 text-red-400 border-red-500/30" },
  textbook:        { label: "Textbook",        color: "bg-purple-500/20 text-purple-400 border-purple-500/30" },
  business_report: { label: "Business Report", color: "bg-orange-500/20 text-orange-400 border-orange-500/30" },
  unknown:         { label: "Document",        color: "bg-gray-500/20 text-gray-400 border-gray-500/30" },
}

export default function StatusBar({ doc, onReset }: Props) {
  const typeConfig = DOC_TYPE_CONFIG[doc.doc_type] || DOC_TYPE_CONFIG.unknown

  return (
    <div className="w-full bg-gray-900 border-b border-gray-800 px-4 py-3
                    flex items-center justify-between gap-4">

      {/* Left — doc info */}
      <div className="flex items-center gap-3 min-w-0">

        {/* PDF icon */}
        <div className="w-8 h-8 bg-gray-800 rounded-lg flex items-center
                        justify-center text-sm flex-shrink-0">
          📄
        </div>

        {/* Filename */}
        <span className="text-white font-medium text-sm truncate">
          {doc.filename}
        </span>

        {/* Doc type badge */}
        <span className={`
          text-xs px-2 py-0.5 rounded-full border flex-shrink-0
          ${typeConfig.color}
        `}>
          {typeConfig.label}
        </span>

        {/* Stats — hidden on small screens */}
        <div className="hidden sm:flex items-center gap-3 text-gray-500 text-xs">
          <span>{doc.num_pages} {doc.num_pages === 1 ? "page" : "pages"}</span>
          <span>·</span>
          <span>{doc.num_chunks} chunks</span>
        </div>
      </div>

      {/* Right — new PDF button */}
      <button
        onClick={onReset}
        className="flex-shrink-0 text-xs px-3 py-1.5 rounded-lg
                   bg-gray-800 hover:bg-gray-700 text-gray-300
                   hover:text-white border border-gray-700
                   transition-colors flex items-center gap-1.5"
      >
        <span>↑</span>
        <span>New PDF</span>
      </button>
    </div>
  )
}