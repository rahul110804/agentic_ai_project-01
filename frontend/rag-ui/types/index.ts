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
// Returned by /upload and /status
// Shown in StatusBar

export interface DocumentMeta {
  filename:    string
  num_pages:   number
  num_chunks:  number
  loaded_at:   string
  doc_type:    DocType
  doc_summary: string
}


// ── Chat Messages ─────────────────────────────────────────────
// Every bubble in ChatWindow is one Message

export type MessageRole = "user" | "assistant"

export interface Message {
  id:        string          // unique id for React key
  role:      MessageRole
  content:   string
  timestamp: string
  task_mode?: TaskMode       // only on assistant messages
  doc_type?:  DocType        // only on assistant messages
  steps?:     AgentStep[]    // thinking steps attached to this message
}


// ── Agent Thinking Steps ──────────────────────────────────────
// Each ReAct step shown in AgentSteps panel

export interface AgentStep {
  iteration:    number
  thought:      string
  action:       string
  action_input: string
  observation?: string       // arrives slightly after the step
}


// ── SSE Events ───────────────────────────────────────────────
// Every event type that streams in from /chat/stream

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