"""
agentic_rag.py
--------------
Advanced Agentic RAG Engine using ReAct (Reason + Act) pattern.

Capabilities:
  1. Critic Mode        — find problems + generate fixes (resume, essays, reports)
  2. Study Mode         — summarize, flashcards, key concepts for exam prep
  3. Doc Type Detection — auto-classifies document, applies right strategy
  4. Structured Output  — formatted markdown: tables, bullets, sections
  5. Task Detection     — auto-detects user intent, supports manual override
  6. Multi-turn Memory  — follow-up questions with conversation context
  7. Streaming          — SSE-ready event generator for typewriter UI
"""

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import chromadb
from google import genai
import os
import json
import re
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, field
from enum import Enum

load_dotenv()


# ============================================================
# CONSTANTS
# ============================================================

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
GEMINI_MODEL_NAME    = "gemini-2.5-flash"
CHUNK_SIZE           = 1500
CHUNK_OVERLAP        = 300
MAX_SEARCH_RESULTS   = 4
MAX_ITERATIONS       = 10


# ============================================================
# ENUMS
# ============================================================

class TaskMode(str, Enum):
    AUTO    = "auto"
    CRITIC  = "critic"
    STUDY   = "study"
    EXTRACT = "extract"
    EXPLAIN = "explain"
    GENERAL = "general"


class DocType(str, Enum):
    RESUME          = "resume"
    RESEARCH_PAPER  = "research_paper"
    NEWS_ARTICLE    = "news_article"
    LEGAL_DOCUMENT  = "legal_document"
    TEXTBOOK        = "textbook"
    BUSINESS_REPORT = "business_report"
    UNKNOWN         = "unknown"


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class AgentStep:
    iteration:    int
    thought:      str
    action:       str
    action_input: str
    observation:  str = ""


@dataclass
class AgentResponse:
    answer:      str
    steps:       List[AgentStep] = field(default_factory=list)
    total_steps: int  = 0
    success:     bool = True
    task_mode:   str  = TaskMode.GENERAL
    doc_type:    str  = DocType.UNKNOWN


@dataclass
class DocumentMeta:
    filename:    str
    num_pages:   int
    num_chunks:  int
    loaded_at:   str
    doc_type:    str = DocType.UNKNOWN
    doc_summary: str = ""


# ============================================================
# PDF PROCESSOR
# ============================================================

class PDFProcessor:

    @staticmethod
    def extract_text(pdf_path: str) -> tuple[str, int]:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        reader    = PdfReader(pdf_path)
        full_text = "".join(page.extract_text() or "" for page in reader.pages)
        return full_text, len(reader.pages)

    @staticmethod
    def chunk_text(
        text:       str,
        chunk_size: int = CHUNK_SIZE,
        overlap:    int = CHUNK_OVERLAP,
    ) -> List[str]:
        chunks, start = [], 0
        while start < len(text):
            chunk = text[start : start + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    @staticmethod
    def sanitize_collection_name(pdf_path: str) -> str:
        """
        ChromaDB collection names must be 3-512 chars,
        only alphanumeric, dots, dashes, underscores,
        and must start/end with alphanumeric.
        """
        raw       = Path(pdf_path).stem
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', raw)
        sanitized = re.sub(r'^[^a-zA-Z0-9]+', '', sanitized)
        sanitized = re.sub(r'[^a-zA-Z0-9]+$', '', sanitized)
        # Fallback if name becomes too short after sanitizing
        if len(sanitized) < 3:
            sanitized = f"doc_{sanitized}_file"
        return f"doc_{sanitized}"


# ============================================================
# VECTOR STORE
# ============================================================

class VectorStore:

    def __init__(self, embedding_model: SentenceTransformer):
        self._client          = chromadb.Client()
        self._embedding_model = embedding_model
        self._collection      = None
        self._all_chunks: List[str] = []

    def build(self, chunks: List[str], collection_name: str) -> None:
        self._drop_if_exists(collection_name)
        self._collection = self._client.create_collection(collection_name)
        self._all_chunks = chunks
        embeddings       = self._embedding_model.encode(chunks, show_progress_bar=False)
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            self._collection.add(
                ids        = [f"chunk_{i}"],
                embeddings = [emb.tolist()],
                documents  = [chunk],
            )

    def search(self, query: str, n_results: int = MAX_SEARCH_RESULTS) -> List[str]:
        if self._collection is None:
            raise RuntimeError("No collection loaded.")
        qe = self._embedding_model.encode([query])[0]
        results = self._collection.query(
            query_embeddings = [qe.tolist()],
            n_results        = min(n_results, len(self._all_chunks)),
        )
        return results["documents"][0] if results["documents"][0] else []

    def get_all_chunks(self) -> List[str]:
        return self._all_chunks

    def is_ready(self) -> bool:
        return self._collection is not None

    def _drop_if_exists(self, name: str) -> None:
        try:
            self._client.delete_collection(name)
        except Exception:
            pass


# ============================================================
# GEMINI CLIENT
# ============================================================

class GeminiClient:

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY not set.")
        self._client = genai.Client(api_key=api_key)

    def complete(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model    = GEMINI_MODEL_NAME,
            contents = prompt,
        )
        return response.text.strip()


# ============================================================
# DOCUMENT ANALYSER
# ============================================================

class DocumentAnalyser:
    """
    Performs whole-document reasoning tasks directly via LLM.
    Called only when needed — not on every agent step.
    """

    def __init__(self, llm: GeminiClient, vector_store: VectorStore):
        self._llm = llm
        self._vs  = vector_store

    def detect_all_at_once(self) -> tuple:
        """
        Combined call — replaces detect_doc_type() + quick_summary().
        Saves 1 Gemini API call every time a PDF is loaded.
        Returns (doc_type, summary).
        """
        sample = " ".join(self._vs.get_all_chunks()[:3])[:4000]

        prompt = (
            "Analyse this document excerpt and return a JSON object with exactly these two fields:\n\n"
            "{\n"
            '  "doc_type": "<one of: resume | research_paper | news_article | legal_document | textbook | business_report | unknown>",\n'
            '  "summary":  "<exactly 2 sentences: what this document is, who wrote it if known, and its main purpose>"\n'
            "}\n\n"
            "Rules:\n"
            "- Respond with ONLY the JSON object — no markdown, no explanation, no code fences.\n"
            "- doc_type must be exactly one of the listed labels.\n"
            "- summary must be exactly 2 sentences, specific and factual.\n\n"
            f"Document excerpt:\n{sample}"
        )

        raw = self._llm.complete(prompt).strip()
        raw = re.sub(r"```json|```", "", raw).strip()

        try:
            parsed   = json.loads(raw)
            raw_type = parsed.get("doc_type", "unknown").strip().lower()
            summary  = parsed.get("summary", "").strip()
        except (json.JSONDecodeError, AttributeError):
            raw_type = "unknown"
            summary  = "Document loaded successfully."

        mapping = {
            "resume":          DocType.RESUME,
            "research_paper":  DocType.RESEARCH_PAPER,
            "news_article":    DocType.NEWS_ARTICLE,
            "legal_document":  DocType.LEGAL_DOCUMENT,
            "textbook":        DocType.TEXTBOOK,
            "business_report": DocType.BUSINESS_REPORT,
        }
        doc_type = mapping.get(raw_type, DocType.UNKNOWN)
        return doc_type, summary

    def detect_task(self, question: str, doc_type: DocType) -> TaskMode:
        prompt = (
            f"Classify the user's intent. Document type: {doc_type}\n"
            f'User question: "{question}"\n\n'
            "Choose one:\n"
            "- critic   : wants problems, weaknesses, improvements, fixes, review\n"
            "- study    : wants summary, key points, flashcards, exam prep, notes\n"
            "- extract  : wants specific data pulled out (dates, names, numbers, lists)\n"
            "- explain  : wants something simplified or clarified\n"
            "- general  : wants a direct factual answer\n\n"
            "Respond with ONLY the single word label."
        )
        raw = self._llm.complete(prompt).strip().lower()
        try:
            return TaskMode(raw)
        except ValueError:
            return TaskMode.GENERAL

    def critique_document(self, focus: str = "") -> str:
        all_text  = "\n\n".join(self._vs.get_all_chunks())
        focus_str = f"\nFocus especially on: {focus}" if focus else ""
        prompt = f"""You are an expert document reviewer. Analyse the document below.{focus_str}

Your response MUST use this exact markdown structure:

## 📋 Document Overview
[2-3 sentences about what this document is and its overall quality]

## ❌ Problems Found
For each problem use this format:
### Problem [N]: [Short title]
- **Section**: [which part of the document]
- **Issue**: [what is wrong]
- **Impact**: [why it matters]
- **Fix**: [specific, actionable recommendation]

## ✅ Strengths
[bullet list of what is done well]

## 🏆 Priority Action Plan
[numbered list of top 5 most impactful changes to make, in order of priority]

## 📊 Overall Score
Rate each dimension out of 10: Content / Clarity / Structure / Impact

Document:
{all_text}"""
        return self._llm.complete(prompt)

    def study_summary(self, style: str = "bullets") -> str:
        all_text = "\n\n".join(self._vs.get_all_chunks())

        style_instructions = {
            "bullets": (
                "## 📚 Key Topics\n[bullet list of main topics]\n\n"
                "## 🔑 Key Concepts & Definitions\n[bullet list: **Term** — definition]\n\n"
                "## 📌 Important Facts & Figures\n[specific data, numbers, findings]\n\n"
                "## 💡 Core Ideas to Remember\n[5-7 most important takeaways]\n\n"
                "## ❓ Likely Exam Questions\n[5 questions with brief answers]"
            ),
            "flashcards": (
                "## 🃏 Flashcards\n\n"
                "**Card 1**\nQ: [question]\nA: [answer]\n\n"
                "[continue for 10-15 cards covering the most important content]"
            ),
            "mindmap": (
                "## 🗺️ Mind Map\n\n"
                "CENTRAL TOPIC: [main subject]\n"
                "├── [Branch 1]\n│   ├── [Sub-point]\n│   └── [Sub-point]\n"
                "├── [Branch 2]\n[cover all major themes]"
            ),
            "detailed": (
                "## 📖 Detailed Study Notes\n\n"
                "### [Section Title]\n[thorough explanation]\n**Key point:** [highlight]\n\n"
                "[continue section by section]"
            ),
        }

        instruction = style_instructions.get(style, style_instructions["bullets"])
        prompt = (
            "You are an expert study assistant. Create comprehensive study material.\n"
            f"Use this format:\n{instruction}\n\n"
            f"Document:\n{all_text}"
        )
        return self._llm.complete(prompt)

    def extract_structured(self, what_to_extract: str) -> str:
        all_text = "\n\n".join(self._vs.get_all_chunks())
        prompt = (
            f"Extract the following from the document: {what_to_extract}\n\n"
            "Present results in clean structured markdown.\n"
            "If something is not found, write 'Not found'.\n"
            "Do not add information that isn't in the document.\n\n"
            f"Document:\n{all_text}"
        )
        return self._llm.complete(prompt)


# ============================================================
# TOOL REGISTRY
# ============================================================

class ToolRegistry:

    def __init__(self, vector_store: VectorStore, analyser: DocumentAnalyser):
        self._vs       = vector_store
        self._analyser = analyser

        self._tools: Dict[str, Dict] = {
            "search_document": {
                "fn": self.search_document,
                "description": (
                    "Search the PDF for specific information. "
                    "Best for targeted factual questions. "
                    "Input: search query string."
                ),
            },
            "critique_document": {
                "fn": self.critique_document,
                "description": (
                    "Perform a full expert critique of the entire document — finds problems, "
                    "weaknesses, and provides specific actionable fixes. "
                    "Use for 'what's wrong', 'how to improve', 'review this' questions. "
                    "Input: optional focus area e.g. 'skills section', or empty string for full critique."
                ),
            },
            "study_summary": {
                "fn": self.study_summary,
                "description": (
                    "Generate study-optimised material from the full document. "
                    "Use for exam prep, summarization, key concepts, flashcards. "
                    "Input: one of 'bullets' | 'flashcards' | 'mindmap' | 'detailed'."
                ),
            },
            "extract_data": {
                "fn": self.extract_data,
                "description": (
                    "Extract specific structured data from the document. "
                    "Use when user wants specific items pulled out: dates, names, numbers, skills, etc. "
                    "Input: description of what to extract."
                ),
            },
            "calculate": {
                "fn": self.calculate,
                "description": (
                    "Perform mathematical calculations. "
                    "Input: valid Python arithmetic expression e.g. '365 * 24'."
                ),
            },
            "get_current_date": {
                "fn": self.get_current_date,
                "description": "Return current date and time. No input needed.",
            },
            "finish": {
                "fn": None,
                "description": (
                    "Use when you have a complete answer ready. "
                    "Input: the full, well-formatted final answer in markdown."
                ),
            },
        }

    def search_document(self, query: str) -> str:
        if not self._vs.is_ready():
            return "ERROR: No document loaded."
        chunks = self._vs.search(query)
        return "\n\n---\n\n".join(chunks) if chunks else "No relevant information found."

    def critique_document(self, focus: str = "") -> str:
        return self._analyser.critique_document(focus)

    def study_summary(self, style: str = "bullets") -> str:
        style = style.strip().lower()
        if style not in {"bullets", "flashcards", "mindmap", "detailed"}:
            style = "bullets"
        return self._analyser.study_summary(style)

    def extract_data(self, what: str) -> str:
        return self._analyser.extract_structured(what)

    def calculate(self, expression: str) -> str:
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return str(result)
        except Exception as exc:
            return f"ERROR: {exc}"

    def get_current_date(self, *_) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def execute(self, tool_name: str, tool_input: str) -> str:
        if tool_name not in self._tools:
            return f"ERROR: Unknown tool '{tool_name}'."
        fn = self._tools[tool_name]["fn"]
        if fn is None:
            return ""
        return fn(tool_input)

    def descriptions(self) -> str:
        return "\n".join(
            f"- {name}: {info['description']}"
            for name, info in self._tools.items()
        )

    def names(self) -> List[str]:
        return list(self._tools.keys())


# ============================================================
# CONVERSATION MEMORY
# ============================================================

class ConversationMemory:

    def __init__(self, max_turns: int = 10):
        self._max_turns = max_turns
        self._turns: List[Dict[str, str]] = []

    def add(self, question: str, answer: str) -> None:
        self._turns.append({"question": question, "answer": answer})
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns:]

    def format_for_prompt(self) -> str:
        if not self._turns:
            return "No prior conversation."
        lines = []
        for i, t in enumerate(self._turns, 1):
            lines.append(f"Turn {i}:")
            lines.append(f"  User:      {t['question']}")
            lines.append(f"  Assistant: {t['answer'][:400]}...")
        return "\n".join(lines)

    def clear(self) -> None:
        self._turns.clear()

    @property
    def turns(self) -> List[Dict[str, str]]:
        return self._turns


# ============================================================
# PROMPT BUILDER
# ============================================================

class PromptBuilder:

    MODE_INSTRUCTIONS: Dict[str, str] = {
        TaskMode.CRITIC: (
            "You are in CRITIC MODE. Your job is to find problems, weaknesses, and issues "
            "and provide specific actionable fixes. Use the 'critique_document' tool. "
            "Output must be structured markdown with clear sections."
        ),
        TaskMode.STUDY: (
            "You are in STUDY MODE. Create useful study material. "
            "Use 'study_summary' with style: bullets/flashcards/mindmap/detailed "
            "based on what the user asked. Default to 'bullets'."
        ),
        TaskMode.EXTRACT: (
            "You are in EXTRACT MODE. Pull out specific structured data. "
            "Use 'extract_data' with a clear description of what to find."
        ),
        TaskMode.EXPLAIN: (
            "You are in EXPLAIN MODE. Use 'search_document' to find content, "
            "then explain it clearly and simply. Use analogies where helpful."
        ),
        TaskMode.GENERAL: (
            "You are in GENERAL Q&A MODE. Use 'search_document' to find relevant content "
            "and answer the question directly and accurately."
        ),
    }

    @staticmethod
    def react_step(
        question:    str,
        tools:       ToolRegistry,
        steps:       List[AgentStep],
        memory:      ConversationMemory,
        task_mode:   TaskMode,
        doc_type:    DocType,
        doc_summary: str,
    ) -> str:
        history_text     = PromptBuilder._format_steps(steps)
        conv_text        = memory.format_for_prompt()
        tool_names       = ", ".join(tools.names())
        mode_instruction = PromptBuilder.MODE_INSTRUCTIONS.get(
            task_mode, PromptBuilder.MODE_INSTRUCTIONS[TaskMode.GENERAL]
        )

        return f"""You are an advanced AI document analysis agent.

=== DOCUMENT CONTEXT ===
Type: {doc_type}
Summary: {doc_summary}

=== YOUR CURRENT MODE ===
{mode_instruction}

=== AVAILABLE TOOLS ===
{tools.descriptions()}

=== CONVERSATION HISTORY ===
{conv_text}

=== STEPS TAKEN FOR THIS QUESTION ===
{history_text}

=== USER QUESTION ===
{question}

=== RULES ===
- Match the tool to your current mode (critic -> critique_document, study -> study_summary, etc.)
- Never repeat a tool call with the same input.
- When you have a complete answer, call "finish" with well-formatted markdown.
- Your final answer must be genuinely useful, specific, and structured.

Respond ONLY with valid JSON:
{{
    "thought": "your reasoning about what to do next",
    "action": "one of [{tool_names}]",
    "action_input": "input for the tool"
}}"""

    @staticmethod
    def _format_steps(steps: List[AgentStep]) -> str:
        if not steps:
            return "No steps taken yet."
        lines = []
        for s in steps:
            lines += [
                f"Step {s.iteration}:",
                f"  Thought:     {s.thought}",
                f"  Action:      {s.action}",
                f"  Input:       {s.action_input[:100]}",
                f"  Observation: {s.observation[:400]}...",
            ]
        return "\n".join(lines)


# ============================================================
# REACT AGENT
# ============================================================

class ReActAgent:

    def __init__(
        self,
        llm:            GeminiClient,
        tools:          ToolRegistry,
        memory:         ConversationMemory,
        analyser:       DocumentAnalyser,
        max_iterations: int = MAX_ITERATIONS,
    ):
        self._llm            = llm
        self._tools          = tools
        self._memory         = memory
        self._analyser       = analyser
        self._max_iterations = max_iterations
        self.doc_type:    DocType = DocType.UNKNOWN
        self.doc_summary: str     = ""

    def run(
        self,
        question:      str,
        mode_override: Optional[TaskMode] = None,
    ) -> AgentResponse:
        task_mode = self._resolve_mode(question, mode_override)
        steps: List[AgentStep] = []

        for iteration in range(1, self._max_iterations + 1):
            prompt   = PromptBuilder.react_step(
                question, self._tools, steps, self._memory,
                task_mode, self.doc_type, self.doc_summary,
            )
            raw      = self._llm.complete(prompt)
            decision = self._parse_decision(raw)

            action       = decision.get("action", "finish")
            action_input = decision.get("action_input", "")
            thought      = decision.get("thought", "")

            if action == "finish":
                self._memory.add(question, action_input)
                return AgentResponse(
                    answer      = action_input,
                    steps       = steps,
                    total_steps = iteration,
                    success     = True,
                    task_mode   = task_mode,
                    doc_type    = self.doc_type,
                )

            observation = self._tools.execute(action, action_input)
            steps.append(AgentStep(
                iteration    = iteration,
                thought      = thought,
                action       = action,
                action_input = action_input,
                observation  = observation,
            ))

        fallback = "Could not complete within max steps. Please try rephrasing."
        self._memory.add(question, fallback)
        return AgentResponse(
            answer      = fallback,
            steps       = steps,
            total_steps = self._max_iterations,
            success     = False,
            task_mode   = task_mode,
            doc_type    = self.doc_type,
        )

    def run_streaming(
        self,
        question:      str,
        mode_override: Optional[TaskMode] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        task_mode = self._resolve_mode(question, mode_override)
        yield {"type": "task_detected", "mode": task_mode, "doc_type": self.doc_type}

        steps: List[AgentStep] = []

        for iteration in range(1, self._max_iterations + 1):
            prompt   = PromptBuilder.react_step(
                question, self._tools, steps, self._memory,
                task_mode, self.doc_type, self.doc_summary,
            )
            raw      = self._llm.complete(prompt)
            decision = self._parse_decision(raw)

            action       = decision.get("action", "finish")
            action_input = decision.get("action_input", "")
            thought      = decision.get("thought", "")

            yield {
                "type":         "step",
                "iteration":    iteration,
                "thought":      thought,
                "action":       action,
                "action_input": action_input[:150],
            }

            if action == "finish":
                self._memory.add(question, action_input)
                yield {
                    "type":        "answer",
                    "answer":      action_input,
                    "total_steps": iteration,
                    "task_mode":   task_mode,
                    "doc_type":    self.doc_type,
                }
                return

            observation = self._tools.execute(action, action_input)
            steps.append(AgentStep(
                iteration    = iteration,
                thought      = thought,
                action       = action,
                action_input = action_input,
                observation  = observation,
            ))
            yield {
                "type":        "observation",
                "iteration":   iteration,
                "tool":        action,
                "observation": observation[:600],
            }

        fallback = "Could not complete within max steps. Please try rephrasing."
        self._memory.add(question, fallback)
        yield {
            "type":        "answer",
            "answer":      fallback,
            "total_steps": self._max_iterations,
            "task_mode":   task_mode,
            "doc_type":    self.doc_type,
        }

    def _resolve_mode(
        self,
        question: str,
        override: Optional[TaskMode],
    ) -> TaskMode:
        if override and override != TaskMode.AUTO:
            return override
        return self._analyser.detect_task(question, self.doc_type)

    @staticmethod
    def _parse_decision(raw: str) -> Dict[str, Any]:
        text  = raw.strip()
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "thought":      "Parse error.",
                "action":       "finish",
                "action_input": raw,
            }


# ============================================================
# AGENTIC RAG  — public facade
# ============================================================

class AgenticRAG:
    """
    Top-level interface. FastAPI and CLI both use only this class.

    Usage:
        rag  = AgenticRAG()
        meta = rag.load_pdf("resume.pdf")

        # Auto-detect mode from the question
        response = rag.ask("Find problems in this resume and suggest fixes")

        # Force a specific mode
        response = rag.ask("Give me key points", mode_override=TaskMode.STUDY)

        # Streaming (for FastAPI SSE)
        for event in rag.ask_streaming("Summarise this for my exam"):
            print(event)
    """

    def __init__(self):
        self._embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self._llm             = GeminiClient()
        self._memory          = ConversationMemory()
        self._vector_store    = VectorStore(self._embedding_model)
        self._analyser        = DocumentAnalyser(self._llm, self._vector_store)
        self._tools           = ToolRegistry(self._vector_store, self._analyser)
        self._agent           = ReActAgent(
            self._llm, self._tools, self._memory, self._analyser
        )
        self._doc_meta: Optional[DocumentMeta] = None

    # ── document management ───────────────────────────────────

    def load_pdf(self, pdf_path: str) -> DocumentMeta:
        """
        Load PDF → chunk → embed → detect doc type → generate summary.
        Everything needed to answer questions is set up here.
        """
        text, pages = PDFProcessor.extract_text(pdf_path)
        chunks      = PDFProcessor.chunk_text(text)

        # Sanitize collection name so ChromaDB accepts it
        collection_name = PDFProcessor.sanitize_collection_name(pdf_path)
        self._vector_store.build(chunks, collection_name)
        self._memory.clear()

        print("🔍 Detecting document type and generating summary (1 combined call)...")
        doc_type, doc_summary = self._analyser.detect_all_at_once()

        # Inject into agent so every prompt is document-aware
        self._agent.doc_type    = doc_type
        self._agent.doc_summary = doc_summary

        self._doc_meta = DocumentMeta(
            filename    = Path(pdf_path).name,
            num_pages   = pages,
            num_chunks  = len(chunks),
            loaded_at   = datetime.now().isoformat(),
            doc_type    = doc_type,
            doc_summary = doc_summary,
        )

        print(f"✅ '{self._doc_meta.filename}' | {doc_type} | {pages} pages | {len(chunks)} chunks")
        return self._doc_meta

    def reset(self) -> None:
        """Clear current document and conversation — ready for a new PDF."""
        self._vector_store = VectorStore(self._embedding_model)
        self._analyser     = DocumentAnalyser(self._llm, self._vector_store)
        self._tools        = ToolRegistry(self._vector_store, self._analyser)
        self._agent        = ReActAgent(
            self._llm, self._tools, self._memory, self._analyser
        )
        self._memory.clear()
        self._doc_meta = None

    # ── querying ──────────────────────────────────────────────

    def ask(
        self,
        question:      str,
        mode_override: Optional[TaskMode] = None,
    ) -> AgentResponse:
        """Synchronous. mode_override=None means auto-detect from question."""
        self._ensure_ready()
        return self._agent.run(question, mode_override)

    def ask_streaming(
        self,
        question:      str,
        mode_override: Optional[TaskMode] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Streaming. Yields SSE-ready dicts."""
        self._ensure_ready()
        yield from self._agent.run_streaming(question, mode_override)

    # ── status ────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._vector_store.is_ready()

    @property
    def doc_meta(self) -> Optional[DocumentMeta]:
        return self._doc_meta

    @property
    def conversation_history(self) -> List[Dict[str, str]]:
        return self._memory.turns

    def _ensure_ready(self) -> None:
        if not self.is_ready:
            raise RuntimeError("No document loaded. Call load_pdf() first.")


# ============================================================
# CLI — local testing
# ============================================================

def _run_cli():
    print("\n" + "=" * 60)
    print("  ADVANCED AGENTIC RAG — CLI")
    print("=" * 60)
    print("\nOptional mode prefix before your question:")
    print("  [critic]  [study]  [extract]  [explain]  [auto]")
    print("  Example:  [study] give me flashcards\n")

    rag       = AgenticRAG()
    pdf_files = list(Path(".").glob("*.pdf"))
    if not pdf_files:
        print("❌ No PDF found in the current directory.")
        return

    print(f"📚 Found: {[p.name for p in pdf_files]}")
    meta = rag.load_pdf(str(pdf_files[0]))
    print(f"\n📄 Type    : {meta.doc_type}")
    print(f"📝 Summary : {meta.doc_summary}\n")

    MODE_MAP = {m.value: m for m in TaskMode}

    while True:
        try:
            raw_input = input("❓ Question (or 'quit'): ").strip()
            if raw_input.lower() in {"quit", "exit", "q"}:
                print("\n👋 Goodbye!")
                break
            if not raw_input:
                continue

            mode_override = None
            question      = raw_input
            match = re.match(r"^\[(\w+)\]\s*(.*)", raw_input, re.IGNORECASE)
            if match:
                mode_key      = match.group(1).lower()
                question      = match.group(2).strip()
                mode_override = MODE_MAP.get(mode_key)

            response = rag.ask(question, mode_override)
            print(f"\n🎯 Mode  : {response.task_mode}")
            print(f"🔢 Steps : {response.total_steps}")
            print(f"\n{'─'*60}")
            print(response.answer)
            print(f"{'─'*60}\n")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as exc:
            print(f"\n❌ Error: {exc}")


if __name__ == "__main__":
    _run_cli()