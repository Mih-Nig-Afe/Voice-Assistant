"""
Command routing module for Voice Assistant.

Maps user speech input to the appropriate handler function.
Provides an extensible command registry pattern.
"""

from typing import Callable, Optional

from voice_assistant.logging_config import get_logger

logger = get_logger("commands")

# Type alias for command handlers
CommandHandler = Callable[[str], Optional[str]]

# Registry of commands: (keyword(s), handler, description)
_commands: list[tuple[list[str], CommandHandler, str]] = []


def register(keywords: list[str], description: str = "") -> Callable:
    """
    Decorator to register a command handler.

    Args:
        keywords: List of trigger phrases (matched against lowercased input).
        description: Human-readable description of the command.

    Returns:
        Decorator function.
    """
    def decorator(func: CommandHandler) -> CommandHandler:
        _commands.append((keywords, func, description))
        logger.debug("Registered command: %s -> %s", keywords, func.__name__)
        return func
    return decorator


def route(user_input: str) -> tuple[Optional[CommandHandler], str]:
    """
    Find the appropriate command handler for user input.

    Args:
        user_input: The user's speech input text.

    Returns:
        Tuple of (handler function or None, matched keyword or empty string).
    """
    lower_input = user_input.lower()
    for keywords, handler, _ in _commands:
        for keyword in keywords:
            if keyword in lower_input:
                logger.info("Command matched: '%s' -> %s", keyword, handler.__name__)
                return handler, keyword
    return None, ""


def list_commands() -> list[tuple[list[str], str]]:
    """Return list of registered commands with their descriptions."""
    return [(kw, desc) for kw, _, desc in _commands]

