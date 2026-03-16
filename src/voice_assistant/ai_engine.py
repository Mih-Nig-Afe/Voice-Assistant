"""
AI Response Generation module for Voice Assistant.

Primary backend: Groq API (free tier — Llama 3.3 70B, fast inference).
Fallback backend: HuggingFace transformers (local GPT-Neo 125M).

Why Groq?
- Free tier: 30 requests/minute, 14,400 requests/day (no credit card)
- Runs Llama 3.3 70B — vastly superior to GPT-Neo 125M
- Supports multi-turn conversation via chat completions API
- Sub-second inference (LPU hardware)
"""

from typing import Optional

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger

logger = get_logger("ai_engine")

# Lazy-loaded backends
_groq_client = None
_hf_generator = None
_initialized: bool = False
_backend: str = "none"

# System prompt for conversational AI
_SYSTEM_PROMPT = (
    "You are Miehab, a friendly and helpful voice assistant. "
    "Keep responses concise (2-3 sentences) since they will be spoken aloud. "
    "Be warm, accurate, and conversational. If you don't know something, say so honestly."
)


def _init_groq() -> bool:
    """Try to initialize the Groq client."""
    global _groq_client
    api_key = Config.get_groq_key()
    if not api_key:
        logger.info("No Groq API key configured.")
        return False
    try:
        from groq import Groq

        _groq_client = Groq(api_key=api_key)
        logger.info("Groq AI backend initialized (model: %s)", Config.AI_MODEL)
        return True
    except ImportError:
        logger.warning("groq package not installed. pip install groq")
        return False
    except Exception as e:
        logger.error("Failed to initialize Groq: %s", e)
        return False


def _init_huggingface() -> bool:
    """Try to initialize the HuggingFace local model."""
    global _hf_generator
    try:
        from transformers import pipeline
        from transformers.utils.logging import set_verbosity_error

        set_verbosity_error()
        model = "EleutherAI/gpt-neo-125M"
        logger.info("Loading local AI model: %s (this may take a moment)...", model)
        _hf_generator = pipeline("text-generation", model=model)
        logger.info("Local AI model loaded.")
        return True
    except Exception as e:
        logger.error("Failed to load HuggingFace model: %s", e)
        return False


def _load_backend() -> None:
    """Initialize the best available AI backend (lazy, once)."""
    global _initialized, _backend
    if _initialized:
        return
    _initialized = True

    if Config.AI_BACKEND == "groq" and _init_groq():
        _backend = "groq"
    elif _init_huggingface():
        _backend = "huggingface"
    else:
        _backend = "none"
        logger.warning("No AI backend available.")


def generate_response(
    prompt: str,
    conversation_history: Optional[list[dict[str, str]]] = None,
) -> str:
    """
    Generate an AI response using the best available backend.

    Args:
        prompt: User's input text.
        conversation_history: Optional list of prior messages for context.

    Returns:
        Generated response text, or a fallback message on failure.
    """
    _load_backend()

    if _backend == "groq":
        return _generate_groq(prompt, conversation_history)
    elif _backend == "huggingface":
        return _generate_huggingface(prompt)
    else:
        return (
            "AI generation isn't available at the moment. Please set up a GROQ_API_KEY."
        )


def _generate_groq(
    prompt: str,
    history: Optional[list[dict[str, str]]] = None,
) -> str:
    """Generate response via Groq API with conversation context."""
    try:
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-Config.AI_MAX_HISTORY :])
        messages.append({"role": "user", "content": prompt})

        response = _groq_client.chat.completions.create(
            model=Config.AI_MODEL,
            messages=messages,
            max_tokens=Config.AI_MAX_LENGTH,
            temperature=0.7,
        )
        text = response.choices[0].message.content.strip()
        logger.debug("Groq response (%d chars)", len(text))
        return text
    except Exception as e:
        logger.error("Groq API error: %s", e)
        return "I had trouble thinking of a response. Please try again."


def _generate_huggingface(prompt: str) -> str:
    """Generate response via local HuggingFace model."""
    try:
        response = _hf_generator(
            prompt, max_length=Config.AI_MAX_LENGTH, num_return_sequences=1
        )
        text: str = response[0]["generated_text"].strip()
        logger.debug("HuggingFace response (%d chars)", len(text))
        return text
    except Exception as e:
        logger.error("HuggingFace error: %s", e)
        return "I couldn't think of a response. Let me try again later."


def is_available() -> bool:
    """Check if any AI backend is ready."""
    _load_backend()
    return _backend != "none"


def get_backend_name() -> str:
    """Return the name of the active AI backend."""
    _load_backend()
    return _backend
