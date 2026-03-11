"use client";

import { useState } from "react";
import { DocumentHistory } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
  documents: DocumentHistory[];
  onClose: () => void;
}

interface CompareResult {
  table: string;
  doc_a: string;
  doc_b: string;
}

type Tab = "history" | "upload";

export default function ComparePanel({ documents, onClose }: Props) {
  const [tab, setTab]           = useState<Tab>("history");
  const [docIdA, setDocIdA]     = useState<number | null>(null);
  const [docIdB, setDocIdB]     = useState<number | null>(null);
  const [fileA, setFileA]       = useState<File | null>(null);
  const [fileB, setFileB]       = useState<File | null>(null);
  const [question, setQuestion] = useState("Compare these two documents comprehensively");
  const [result, setResult]     = useState<CompareResult | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  // Always safe array — prevents .map crash if prop is undefined
  const safeDocs = Array.isArray(documents) ? documents : [];

  const canCompareHistory = docIdA !== null && docIdB !== null && docIdA !== docIdB;
  const canCompareUpload  = fileA !== null && fileB !== null;

  async function handleCompareHistory() {
    if (!canCompareHistory) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/compare`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ doc_id_a: docIdA, doc_id_b: docIdB, question }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Comparison failed");
      }
      setResult(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCompareUpload() {
    if (!canCompareUpload) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const form = new FormData();
      form.append("file_a",   fileA!);
      form.append("file_b",   fileB!);
      form.append("question", question);
      const res = await fetch(`${API_BASE_URL}/compare/upload`, {
        method: "POST",
        body:   form,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Comparison failed");
      }
      setResult(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function renderMarkdownTable(md: string) {
    const lines      = md.trim().split("\n");
    const tableLines = lines.filter(l => l.trim().startsWith("|"));
    const nonTable   = lines.filter(l => !l.trim().startsWith("|")).join("\n").trim();

    if (tableLines.length < 2) {
      return <pre className="text-gray-300 text-sm whitespace-pre-wrap">{md}</pre>;
    }

    const headerCells = tableLines[0].split("|").filter(c => c.trim() !== "");
    const bodyRows    = tableLines.slice(2).map(row =>
      row.split("|").filter(c => c.trim() !== "")
    );

    return (
      <div>
        <div className="overflow-x-auto rounded-lg border border-gray-700">
          <table className="w-full text-sm text-left">
            <thead className="bg-violet-900/40">
              <tr>
                {headerCells.map((h, i) => (
                  <th key={i} className="px-4 py-3 text-violet-300 font-semibold border-b border-gray-700 whitespace-nowrap">
                    {h.trim()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bodyRows.map((row, ri) => (
                <tr key={ri} className={ri % 2 === 0 ? "bg-gray-900/40" : "bg-gray-800/30"}>
                  {row.map((cell, ci) => (
                    <td key={ci} className={`px-4 py-3 border-b border-gray-800 ${ci === 0 ? "text-gray-300 font-medium" : "text-gray-400"}`}>
                      {cell.trim()}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {nonTable && (
          <div className="mt-4 p-4 bg-gray-800/40 rounded-lg border border-gray-700">
            <p className="text-xs text-violet-400 font-semibold mb-1 uppercase tracking-wider">Summary</p>
            <p className="text-gray-300 text-sm leading-relaxed">{nonTable}</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div>
            <h2 className="text-white font-bold text-lg">📊 Compare Two PDFs</h2>
            <p className="text-gray-400 text-xs mt-0.5">Side-by-side AI comparison</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl transition-colors">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-5">

          {/* Tabs */}
          <div className="flex gap-2">
            {(["history", "upload"] as Tab[]).map(t => (
              <button
                key={t}
                onClick={() => { setTab(t); setResult(null); setError(null); }}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  tab === t
                    ? "bg-violet-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white"
                }`}
              >
                {t === "history" ? "📚 From History" : "⬆️ Upload New"}
              </button>
            ))}
          </div>

          {/* FROM HISTORY */}
          {tab === "history" && (
            <div className="space-y-4">
              {safeDocs.length < 2 ? (
                <div className="text-center py-8 text-gray-500">
                  <p className="text-4xl mb-2">📂</p>
                  <p>You need at least 2 documents in history to compare.</p>
                  <p className="text-sm mt-1">Switch to "Upload New" to upload two PDFs directly.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  {["Document A", "Document B"].map((label, idx) => (
                    <div key={idx}>
                      <p className="text-xs text-gray-400 mb-2 font-medium uppercase tracking-wider">{label}</p>
                      <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                        {safeDocs.map(doc => {
                          const selected      = idx === 0 ? docIdA === doc.document_id : docIdB === doc.document_id;
                          const otherSelected = idx === 0 ? docIdB === doc.document_id : docIdA === doc.document_id;
                          return (
                            <button
                              key={doc.document_id}
                              onClick={() => idx === 0 ? setDocIdA(doc.document_id) : setDocIdB(doc.document_id)}
                              disabled={otherSelected}
                              className={`w-full text-left px-3 py-2 rounded-lg border text-sm transition-all ${
                                selected
                                  ? "border-violet-500 bg-violet-900/30 text-white"
                                  : otherSelected
                                    ? "border-gray-700 bg-gray-800/20 text-gray-600 cursor-not-allowed"
                                    : "border-gray-700 bg-gray-800/40 text-gray-300 hover:border-violet-500/50"
                              }`}
                            >
                              <p className="font-medium truncate">{doc.filename}</p>
                              <p className="text-xs text-gray-500 mt-0.5">{doc.doc_type} · {doc.num_pages} pages</p>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* UPLOAD NEW */}
          {tab === "upload" && (
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "Document A", file: fileA, setFile: setFileA },
                { label: "Document B", file: fileB, setFile: setFileB },
              ].map(({ label, file, setFile }, idx) => (
                <div key={idx}>
                  <p className="text-xs text-gray-400 mb-2 font-medium uppercase tracking-wider">{label}</p>
                  <label className={`flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-6 cursor-pointer transition-colors ${
                    file ? "border-violet-500 bg-violet-900/10" : "border-gray-700 hover:border-violet-500/50"
                  }`}>
                    <input
                      type="file"
                      accept=".pdf"
                      className="hidden"
                      onChange={e => setFile(e.target.files?.[0] || null)}
                    />
                    {file ? (
                      <>
                        <span className="text-2xl">✅</span>
                        <span className="text-violet-300 text-sm font-medium mt-1 text-center truncate w-full text-center">{file.name}</span>
                      </>
                    ) : (
                      <>
                        <span className="text-2xl text-gray-600">📄</span>
                        <span className="text-gray-500 text-sm mt-1">Click to upload PDF</span>
                      </>
                    )}
                  </label>
                </div>
              ))}
            </div>
          )}

          {/* Question */}
          <div>
            <p className="text-xs text-gray-400 mb-2 font-medium uppercase tracking-wider">Comparison Question</p>
            <input
              type="text"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="What do you want to compare?"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5
                         text-gray-200 text-sm focus:outline-none focus:border-violet-500 transition-colors"
            />
          </div>

          {/* Compare Button */}
          <button
            onClick={tab === "history" ? handleCompareHistory : handleCompareUpload}
            disabled={loading || (tab === "history" ? !canCompareHistory : !canCompareUpload)}
            className="w-full py-3 rounded-xl font-semibold text-sm transition-all
                       bg-violet-600 hover:bg-violet-500 text-white
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Comparing... this may take a moment
              </span>
            ) : "⚡ Compare Documents"}
          </button>

          {/* Error */}
          {error && (
            <div className="p-4 bg-red-900/20 border border-red-700/50 rounded-lg text-red-400 text-sm">
              ❌ {error}
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-green-400 text-sm font-semibold">✅ Comparison Complete</span>
                <span className="text-gray-500 text-xs">· {result.doc_a} vs {result.doc_b}</span>
              </div>
              {renderMarkdownTable(result.table)}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}