# core/agent.py
# ── ReAct (Reason + Act) Agent loop ──
# Drives the think → act → observe cycle until "finish" is called.
# Supports both synchronous (run) and streaming (run_streaming) modes.

import json
import re
from typing import Any, Dict, Generator, List, Optional

from core.models import AgentResponse, AgentStep, DocType, TaskMode
from core.llm_clients import GeminiClient
from core.tool_registry import ToolRegistry
from core.memory import ConversationMemory
from core.document_analyser import DocumentAnalyser
from core.prompt_builder import PromptBuilder


MAX_ITERATIONS = 10


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

        # Injected after PDF load so every prompt is document-aware
        self.doc_type:    DocType = DocType.UNKNOWN
        self.doc_summary: str     = ""

    # ── Synchronous run ───────────────────────────────────────

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

        fallback = "Could not complete within the maximum steps. Please try rephrasing."
        self._memory.add(question, fallback)
        return AgentResponse(
            answer      = fallback,
            steps       = steps,
            total_steps = self._max_iterations,
            success     = False,
            task_mode   = task_mode,
            doc_type    = self.doc_type,
        )

    # ── Streaming run (SSE) ───────────────────────────────────

    def run_streaming(
        self,
        question:      str,
        mode_override: Optional[TaskMode] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Yields SSE-ready dicts:
          {type: 'task_detected', mode, doc_type}
          {type: 'step',         iteration, thought, action, action_input}
          {type: 'observation',  iteration, tool, observation}
          {type: 'answer',       answer, total_steps, task_mode, doc_type}
          {type: 'error',        message}
        """
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

        # Exceeded max iterations
        fallback = "Could not complete within the maximum steps. Please try rephrasing."
        self._memory.add(question, fallback)
        yield {
            "type":        "answer",
            "answer":      fallback,
            "total_steps": self._max_iterations,
            "task_mode":   task_mode,
            "doc_type":    self.doc_type,
        }

    # ── Private helpers ───────────────────────────────────────

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
        """
        Parse the LLM's JSON response.
        Falls back to 'finish' with the raw text if JSON is malformed.
        """
        text  = raw.strip()
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "thought":      "JSON parse error — finishing with raw output.",
                "action":       "finish",
                "action_input": raw,
            }