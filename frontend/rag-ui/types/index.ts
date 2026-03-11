// types/index.ts

// ── Document & Agent Enums ────────────────────────────────────

export type TaskMode = "auto" | "critic" | "study" | "extract" | "explain" | "general"

export type DocType =
  | "resume"
  | "research_paper"
  | "news_article"
  | "legal_document"
  | "textbook"
  | "business_report"
  | "unknown"


// ── Document Metadata ─────────────────────────────────────────

export interface DocumentMeta {
  filename:    string
  num_pages:   number
  num_chunks:  number
  loaded_at:   string
  doc_type:    DocType
  doc_summary: string
}


// ── Chat Messages ─────────────────────────────────────────────

export type MessageRole = "user" | "assistant"

export interface Message {
  id:         string
  role:       MessageRole
  content:    string
  timestamp:  string
  task_mode?: TaskMode
  doc_type?:  DocType
  steps?:     AgentStep[]
}


// ── Agent Thinking Steps ──────────────────────────────────────

export interface AgentStep {
  iteration:    number
  thought:      string
  action:       string
  action_input: string
  observation?: string
}


// ── History Types — ChatGPT-style ─────────────────────────────

export interface HistoryTurn {
  question:  string
  answer:    string
  task_mode: string
  timestamp: string
}

export interface DocumentHistory {
  document_id: number
  filename:    string
  doc_type:    string
  num_pages:   number
  summary:     string
  loaded_at:   string
  turns:       HistoryTurn[]
}


// ── SSE Events ────────────────────────────────────────────────

export interface SSETaskDetected {
  type:     "task_detected"
  mode:     TaskMode
  doc_type: DocType
}

export interface SSEStep {
  type:         "step"
  iteration:    number
  thought:      string
  action:       string
  action_input: string
}

export interface SSEObservation {
  type:        "observation"
  iteration:   number
  tool:        string
  observation: string
}

export interface SSEAnswer {
  type:        "answer"
  answer:      string
  total_steps: number
  task_mode:   TaskMode
  doc_type:    DocType
}

export interface SSEError {
  type:    "error"
  message: string
}

export type SSEEvent =
  | SSETaskDetected
  | SSEStep
  | SSEObservation
  | SSEAnswer
  | SSEError


// ── API Response shapes ───────────────────────────────────────

export interface UploadResponse {
  success:  boolean
  message:  string
  document: DocumentMeta
}

export interface StatusResponse {
  is_ready: boolean
  document: DocumentMeta | null
  message:  string
}

export interface HistoryResponse {
  turns: { question: string; answer: string }[]
  total: number
}

export interface DocumentHistoryResponse {
  documents: DocumentHistory[]
}