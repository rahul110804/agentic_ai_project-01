// app/components/PDFUpload.tsx
"use client"

import { useState, useRef, DragEvent, ChangeEvent } from "react"
import { uploadPDF } from "@/lib/api"
import type { DocumentMeta } from "@/types"

interface Props {
  onUploadSuccess: (doc: DocumentMeta) => void
}

export default function PDFUpload({ onUploadSuccess }: Props) {
  const [isDragging, setIsDragging]   = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError]             = useState<string | null>(null)
  const [progress, setProgress]       = useState<string>("")
  const fileInputRef                  = useRef<HTMLInputElement>(null)

  // ── Validation ──────────────────────────────────────────────
  function validateFile(file: File): string | null {
    if (!file.name.endsWith(".pdf"))
      return "Only PDF files are allowed."
    if (file.size > 20 * 1024 * 1024)
      return "File is too large. Maximum size is 20MB."
    return null
  }

  // ── Handle upload ───────────────────────────────────────────
  async function handleFile(file: File) {
    const validationError = validateFile(file)
    if (validationError) {
      setError(validationError)
      return
    }

    setError(null)
    setIsUploading(true)
    setProgress("Uploading PDF...")

    try {
      setProgress("Extracting text and creating embeddings...")
      const response = await uploadPDF(file)

      setProgress("Detecting document type...")
      await new Promise(r => setTimeout(r, 500)) // small delay for UX

      onUploadSuccess(response.document)
    } catch (err: any) {
      setError(err.message || "Upload failed. Please try again.")
    } finally {
      setIsUploading(false)
      setProgress("")
    }
  }

  // ── Drag events ─────────────────────────────────────────────
  function onDragOver(e: DragEvent) {
    e.preventDefault()
    setIsDragging(true)
  }

  function onDragLeave(e: DragEvent) {
    e.preventDefault()
    setIsDragging(false)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  // ── File picker ─────────────────────────────────────────────
  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center p-6">

      {/* Header */}
      <div className="mb-10 text-center">
        <h1 className="text-4xl font-bold text-white mb-3">
          Agentic RAG
        </h1>
        <p className="text-gray-400 text-lg">
          Upload a PDF and ask anything — critic, study, extract, explain
        </p>
      </div>

      {/* Drop Zone */}
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`
          w-full max-w-xl border-2 border-dashed rounded-2xl p-12
          flex flex-col items-center justify-center gap-4
          cursor-pointer transition-all duration-200
          ${isDragging
            ? "border-violet-500 bg-violet-500/10"
            : "border-gray-700 bg-gray-900 hover:border-violet-600 hover:bg-gray-900/80"
          }
          ${isUploading ? "pointer-events-none opacity-70" : ""}
        `}
      >
        {/* Icon */}
        <div className={`
          w-16 h-16 rounded-full flex items-center justify-center text-3xl
          ${isDragging ? "bg-violet-500/20" : "bg-gray-800"}
        `}>
          {isUploading ? "⏳" : "📄"}
        </div>

        {/* Text */}
        {isUploading ? (
          <div className="text-center">
            <p className="text-violet-400 font-medium text-lg animate-pulse">
              {progress}
            </p>
            <p className="text-gray-500 text-sm mt-1">
              This may take a few seconds...
            </p>
          </div>
        ) : (
          <div className="text-center">
            <p className="text-white font-medium text-lg">
              {isDragging ? "Drop it here!" : "Drag & drop your PDF here"}
            </p>
            <p className="text-gray-500 text-sm mt-1">or click to browse</p>
            <p className="text-gray-600 text-xs mt-3">PDF only · Max 20MB</p>
          </div>
        )}

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={onFileChange}
          className="hidden"
        />
      </div>

      {/* Browse Button */}
      {!isUploading && (
        <button
          onClick={() => fileInputRef.current?.click()}
          className="mt-4 px-6 py-2.5 bg-violet-600 hover:bg-violet-500
                     text-white rounded-xl font-medium transition-colors"
        >
          Browse Files
        </button>
      )}

      {/* Error Message */}
      {error && (
        <div className="mt-4 w-full max-w-xl bg-red-500/10 border border-red-500/30
                        rounded-xl px-4 py-3 text-red-400 text-sm text-center">
          ⚠️ {error}
        </div>
      )}

      {/* Feature hints */}
      {!isUploading && (
        <div className="mt-10 grid grid-cols-2 gap-3 w-full max-w-xl">
          {[
            { icon: "🔍", label: "Critic Mode",  desc: "Find problems & fixes" },
            { icon: "📚", label: "Study Mode",   desc: "Flashcards & key points" },
            { icon: "📊", label: "Extract Mode", desc: "Pull structured data" },
            { icon: "💡", label: "Explain Mode", desc: "Simplify complex content" },
          ].map(f => (
            <div key={f.label}
              className="bg-gray-900 border border-gray-800 rounded-xl p-3 flex gap-3 items-start">
              <span className="text-xl">{f.icon}</span>
              <div>
                <p className="text-white text-sm font-medium">{f.label}</p>
                <p className="text-gray-500 text-xs">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}