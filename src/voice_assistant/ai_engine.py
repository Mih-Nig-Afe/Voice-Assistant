"""
AI Response Generation module for Voice Assistant.

Provides text generation using HuggingFace transformers (GPT-Neo).
Supports lazy loading to avoid blocking startup.
"""

from typing import Optional

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger

logger = get_logger("ai_engine")

# Lazy-loaded generator
_generator = None
_initialized: bool = False


def _load_model() -> None:
    """Load the text generation model on first use."""
    global _generator, _initialized

    if _initialized:
        return

    _initialized = True
    try:
        from transformers import pipeline
        from transformers.utils.logging import set_verbosity_error

        set_verbosity_error()
        logger.info("Loading AI model: %s (this may take a moment)...", Config.AI_MODEL)
        _generator = pipeline("text-generation", model=Config.AI_MODEL)
        logger.info("AI model loaded successfully.")
    except Exception as e:
        logger.error("Failed to load AI model: %s", e)
        _generator = None


def generate_response(prompt: str) -> str:
    """
    Generate an AI-powered text response for the given prompt.

    Args:
        prompt: User's input text to generate a response for.

    Returns:
        Generated text response, or a fallback message on failure.
    """
    _load_model()

    if _generator is None:
        return "AI generation isn't available at the moment."

    try:
        response = _generator(
            prompt,
            max_length=Config.AI_MAX_LENGTH,
            num_return_sequences=1,
        )
        generated_text: str = response[0]["generated_text"].strip()
        logger.debug("AI response generated (%d chars)", len(generated_text))
        return generated_text
    except Exception as e:
        logger.error("Error generating AI response: %s", e)
        return "I couldn't think of a response. Let me try again later."


def is_available() -> bool:
    """Check if the AI engine is loaded and ready."""
    _load_model()
    return _generator is not None

