# core/prompt_builder.py
# ── Builds all prompts sent to the LLM ──
# Centralised here so prompt changes never require touching agent logic.

from typing import Dict, List

from core.models import AgentStep, DocType, TaskMode
from core.memory import ConversationMemory
from core.tool_registry import ToolRegistry


class PromptBuilder:

    # ── Mode-specific instructions injected into every ReAct prompt ──
    MODE_INSTRUCTIONS: Dict[str, str] = {
        TaskMode.CRITIC: (
            "You are in CRITIC MODE. Your job is to find problems, weaknesses, and issues "
            "and provide specific actionable fixes. Use the 'critique_document' tool. "
            "You may also use 'search_web' to compare against industry standards. "
            "Output must be structured markdown with clear sections."
        ),
        TaskMode.STUDY: (
            "You are in STUDY MODE. Create useful, comprehensive study material. "
            "Use 'study_summary' with style: bullets / flashcards / mindmap / detailed "
            "based on what the user asked. Default to 'bullets'."
        ),
        TaskMode.EXTRACT: (
            "You are in EXTRACT MODE. Pull out specific structured data from the document. "
            "Use 'extract_data' with a clear description of what to find."
        ),
        TaskMode.EXPLAIN: (
            "You are in EXPLAIN MODE. Use 'search_document' to find relevant content, "
            "then explain it clearly and simply. Use analogies where helpful. "
            "Use 'search_web' if additional external context would improve the explanation."
        ),
        TaskMode.GENERAL: (
            "You are in GENERAL Q&A MODE. Use 'search_document' to find relevant content "
            "and answer the question directly and accurately. "
            "Use 'search_web' if the question needs current or external information."
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

        return f"""You are an advanced AI document analysis agent with web search capability.

=== DOCUMENT CONTEXT ===
Type: {doc_type}
Summary: {doc_summary}

=== YOUR CURRENT MODE ===
{mode_instruction}

=== AVAILABLE TOOLS ===
{tools.descriptions()}

=== CONVERSATION HISTORY ===
{conv_text}

=== STEPS TAKEN SO FAR ===
{history_text}

=== USER QUESTION ===
{question}

=== SOURCE DECISION RULES ===
You are NOT limited to the document. You have three sources available — use the best one:

1. DOCUMENT QUESTIONS — anything about the uploaded PDF content:
   → use search_document / critique_document / study_summary / extract_data

2. CURRENT / EXTERNAL QUESTIONS — trends, news, market data, recent events, industry standards,
   "latest", "2024", "2025", comparisons with the outside world:
   → use search_web — ALWAYS search, never refuse these questions

3. COMBINED — question needs both document content AND external context:
   → use search_document first, then search_web, finish with combined answer

4. SIMPLE FACTS — basic definitions or concepts you already know with certainty:
   → call "finish" directly, no tools needed

CRITICAL: Never refuse a question by saying you can only answer about the document.
If it's a general knowledge or current events question → use search_web.
If it needs the document → use search_document.
You can always answer — you have tools for everything.

=== OTHER RULES ===
- Match tool to mode: critic→critique_document, study→study_summary, extract→extract_data
- Never repeat a tool call with the same input.
- When you have a complete answer, call "finish" with well-formatted markdown.
- If you used search_web, cite the sources in your final answer.
- Your final answer must be genuinely useful, specific, and well structured.

Respond ONLY with valid JSON — no extra text, no markdown fences:
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