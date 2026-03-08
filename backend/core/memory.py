# core/memory.py
# ── Multi-turn conversation memory ──
# Keeps the last N question/answer pairs and formats them for prompts.

from typing import Dict, List


class ConversationMemory:

    def __init__(self, max_turns: int = 10):
        self._max_turns = max_turns
        self._turns: List[Dict[str, str]] = []

    def add(self, question: str, answer: str) -> None:
        """Store a completed turn. Trims oldest if over max."""
        self._turns.append({"question": question, "answer": answer})
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns:]

    def format_for_prompt(self) -> str:
        """Return a readable conversation history string for the LLM prompt."""
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