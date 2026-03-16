"""
Conversation memory module for Voice Assistant.

Maintains a sliding window of conversation history to provide
context for multi-turn AI interactions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from voice_assistant.logging_config import get_logger

logger = get_logger("conversation")

# Default maximum history length
_DEFAULT_MAX_HISTORY = 20


@dataclass
class Message:
    """A single conversation message."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class ConversationMemory:
    """
    Manages conversation history with a sliding window.

    Keeps the last N exchanges to provide context without
    unbounded memory growth.
    """

    def __init__(self, max_history: int = _DEFAULT_MAX_HISTORY) -> None:
        """
        Initialize conversation memory.

        Args:
            max_history: Maximum number of messages to retain.
        """
        self._history: list[Message] = []
        self._max_history = max_history
        logger.debug("Conversation memory initialized (max=%d)", max_history)

    def add_user_message(self, content: str) -> None:
        """Record a user message."""
        self._history.append(Message(role="user", content=content))
        self._trim()
        logger.debug("User message recorded (%d total)", len(self._history))

    def add_assistant_message(self, content: str) -> None:
        """Record an assistant response."""
        self._history.append(Message(role="assistant", content=content))
        self._trim()

    def get_context_string(self, last_n: int = 6) -> str:
        """
        Build a context string from recent conversation history.

        Args:
            last_n: Number of recent messages to include.

        Returns:
            Formatted conversation context string.
        """
        recent = self._history[-last_n:] if len(self._history) > last_n else self._history
        if not recent:
            return ""
        lines = []
        for msg in recent:
            prefix = "User" if msg.role == "user" else "Miehab"
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)

    def get_messages_for_api(self, last_n: int = 10) -> list[dict[str, str]]:
        """
        Get conversation history formatted for chat API calls.

        Args:
            last_n: Number of recent messages to include.

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """
        recent = self._history[-last_n:] if len(self._history) > last_n else self._history
        return [{"role": msg.role, "content": msg.content} for msg in recent]

    def clear(self) -> None:
        """Clear all conversation history."""
        self._history.clear()
        logger.info("Conversation history cleared.")

    @property
    def message_count(self) -> int:
        """Return the number of messages in history."""
        return len(self._history)

    def _trim(self) -> None:
        """Trim history to max length."""
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]


# Global conversation memory instance
memory = ConversationMemory()

