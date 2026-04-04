"""
AI Response Generation module for Voice Assistant.

Primary backend: Groq API (free tier — GPT OSS 120B default, fast inference).
Fallback backend: HuggingFace transformers (local GPT-Neo 125M).

Why Groq?
- Free tier: 30 requests/minute, 14,400 requests/day (no credit card)
- Runs strong hosted LLMs (GPT OSS/Llama/Qwen) — vastly superior to GPT-Neo 125M
- Supports multi-turn conversation via chat completions API
- Sub-second inference (LPU hardware)
"""

import re
from typing import Optional

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger
from voice_assistant.runtime import sanitize_query

logger = get_logger("ai_engine")

# Lazy-loaded backends
_groq_client = None
_hf_generator = None
_initialized: bool = False
_backend: str = "none"

# System prompt for conversational AI
_SYSTEM_PROMPT = (
    "You are Miehab, a helpful and practical voice assistant. "
    "Understand imperfect speech transcripts and infer intent from context. "
    "When a request is clear, answer directly without unnecessary follow-up questions. "
    "If the user is mistaken, politely correct them with a brief explanation. "
    "Keep responses concise (2-3 sentences) since they may be spoken aloud. "
    "Be accurate, conversational, and honest when uncertain."
)
_AI_MODEL_HARD_FALLBACK = "llama-3.3-70b-versatile"
_MODEL_FAILURE_COUNTS: dict[str, int] = {}
_MODEL_EMPTY_COUNTS: dict[str, int] = {}
_MODEL_BLOCKLIST: set[str] = set()


def _clean_generated_text(text: str) -> str:
    """Normalize model output for cleaner spoken responses."""
    clean = (text or "").strip()
    if not clean:
        return ""

    # Remove hidden reasoning tags some models may emit.
    clean = re.sub(r"<think>.*?</think>", "", clean, flags=re.IGNORECASE | re.DOTALL)
    clean = re.sub(r"</?analysis>", "", clean, flags=re.IGNORECASE)
    clean = clean.strip()
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _is_tool_mismatch_error(exc: Exception) -> bool:
    """Return True if model tried unsupported tool-calling behavior."""
    message = str(exc).lower()
    return "tool_use_failed" in message or "tool choice is none, but model called a tool" in message


def _record_model_error(model_name: str, exc: Exception) -> None:
    """Track model errors and block unstable models after repeated failures."""
    if model_name == _AI_MODEL_HARD_FALLBACK:
        return
    _MODEL_FAILURE_COUNTS[model_name] = _MODEL_FAILURE_COUNTS.get(model_name, 0) + 1
    if _is_tool_mismatch_error(exc):
        _MODEL_BLOCKLIST.add(model_name)
        logger.warning(
            "Model '%s' disabled for this runtime due to incompatible tool-calling behavior.",
            model_name,
        )
        return
    if _MODEL_FAILURE_COUNTS[model_name] >= 3:
        _MODEL_BLOCKLIST.add(model_name)
        logger.warning(
            "Model '%s' disabled for this runtime after repeated API failures.",
            model_name,
        )


def _record_model_empty(model_name: str) -> None:
    """Track empty responses and block models that repeatedly return blanks."""
    if model_name == _AI_MODEL_HARD_FALLBACK:
        return
    _MODEL_EMPTY_COUNTS[model_name] = _MODEL_EMPTY_COUNTS.get(model_name, 0) + 1
    if _MODEL_EMPTY_COUNTS[model_name] >= 3:
        _MODEL_BLOCKLIST.add(model_name)
        logger.warning(
            "Model '%s' disabled for this runtime after repeated empty responses.",
            model_name,
        )


def _record_model_success(model_name: str) -> None:
    """Clear transient failure counters after a successful response."""
    _MODEL_FAILURE_COUNTS.pop(model_name, None)
    _MODEL_EMPTY_COUNTS.pop(model_name, None)


def _get_model_candidates() -> list[str]:
    """Build ordered unique model candidate list honoring configured fallbacks."""
    candidates: list[str] = []
    primary = (Config.AI_MODEL or "").strip()
    if primary:
        candidates.append(primary)
    configured_fallbacks = [
        model.strip()
        for model in (Config.AI_MODEL_FALLBACKS or "").split(",")
        if model.strip()
    ]
    for model in configured_fallbacks:
        if model not in candidates:
            candidates.append(model)
    if _AI_MODEL_HARD_FALLBACK not in candidates:
        candidates.append(_AI_MODEL_HARD_FALLBACK)
    return [model for model in candidates if model and model not in _MODEL_BLOCKLIST]


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
    prompt = sanitize_query(prompt, max_length=500)
    if not prompt:
        return "I didn't catch that clearly. Please ask again."

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
        if _groq_client is None:
            return "AI service is not ready yet."

        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-Config.AI_MAX_HISTORY :])
        messages.append({"role": "user", "content": prompt})

        model_candidates = _get_model_candidates()
        if not model_candidates:
            model_candidates = [_AI_MODEL_HARD_FALLBACK]

        last_error = None
        for model_name in model_candidates:
            try:
                response = _groq_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=Config.AI_MAX_LENGTH,
                    temperature=0.4,
                )
                content = response.choices[0].message.content if response.choices else ""
                text = _clean_generated_text(content or "")
                if text:
                    _record_model_success(model_name)
                    if model_name != Config.AI_MODEL:
                        logger.warning(
                            "Primary model '%s' failed/empty; using fallback '%s'.",
                            Config.AI_MODEL,
                            model_name,
                        )
                    logger.debug("Groq response (%d chars) [model=%s]", len(text), model_name)
                    return text
                last_error = RuntimeError("empty response body")
                _record_model_empty(model_name)
                logger.warning(
                    "Groq model '%s' returned empty response. Trying fallback model if available.",
                    model_name,
                )
            except Exception as model_exc:
                last_error = model_exc
                _record_model_error(model_name, model_exc)
                logger.error("Groq model '%s' error: %s", model_name, model_exc)

        logger.warning("Groq failed across candidate models. Last error: %s", last_error)
        return "I don't have a response right now. Please try once more."
    except Exception as e:
        msg = str(e).lower()
        if "rate" in msg or "429" in msg:
            logger.warning("Groq rate limit reached: %s", e)
            return (
                "I'm getting too many requests right now. Please try again in a moment."
            )
        if "timeout" in msg:
            logger.error("Groq timeout: %s", e)
            return "The AI service timed out. Please try again."
        logger.error("Groq API error: %s", e, exc_info=True)
        return "I had trouble thinking of a response. Please try again."


def _generate_huggingface(prompt: str) -> str:
    """Generate response via local HuggingFace model."""
    try:
        if _hf_generator is None:
            return "Local AI model is not loaded yet."
        response = _hf_generator(
            prompt, max_length=Config.AI_MAX_LENGTH, num_return_sequences=1
        )
        text: str = _clean_generated_text(response[0].get("generated_text", ""))
        if not text:
            return "I couldn't generate a response just now."
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
