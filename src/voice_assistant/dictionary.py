"""
Dictionary module for Voice Assistant.

Provides word definitions using the Free Dictionary API
(no API key required, completely free).
"""

import requests
import time

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger
from voice_assistant.runtime import sanitize_query

logger = get_logger("dictionary")

# Free Dictionary API - no key, no signup
_DICT_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"


def get_definition(word: str) -> str:
    """
    Look up the definition of a word using the Free Dictionary API.

    API: https://dictionaryapi.dev/ (free, no key, no signup, unlimited)

    Args:
        word: The word to define.

    Returns:
        Formatted definition string with part of speech and meanings.
    """
    word = sanitize_query(word.strip().lower(), max_length=48)
    if not word:
        return "Please tell me a word to define."

    # Basic validation: single word or hyphenated
    if not all(c.isalpha() or c in "-'" for c in word):
        return "That doesn't seem like a valid word. Please try a single English word."

    try:
        start = time.perf_counter()
        response = requests.get(f"{_DICT_API_URL}/{word}", timeout=Config.HTTP_TIMEOUT)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "Dictionary API request completed in %.1fms (status=%s)",
            elapsed_ms,
            response.status_code,
        )

        if response.status_code == 404:
            return (
                f"I couldn't find a definition for '{word}'. Please check the spelling."
            )

        response.raise_for_status()
        data = response.json()

        if not data or not isinstance(data, list):
            return f"No definitions found for '{word}'."

        entry = data[0]
        word_name = entry.get("word", word)
        phonetic = entry.get("phonetic", "")

        meanings = entry.get("meanings", [])
        if not meanings:
            return f"No definitions available for '{word_name}'."

        result_parts = [f"Definition of '{word_name}'"]
        if phonetic:
            result_parts[0] += f" ({phonetic})"
        result_parts[0] += ":"

        for meaning in meanings[:3]:  # Limit to 3 parts of speech
            pos = meaning.get("partOfSpeech", "unknown")
            definitions = meaning.get("definitions", [])
            if definitions:
                defn = definitions[0].get("definition", "")
                result_parts.append(f"  {pos}: {defn}")
                example = definitions[0].get("example")
                if example:
                    result_parts.append(f"    Example: {example}")

        return "\n".join(result_parts)

    except requests.exceptions.Timeout:
        logger.error("Dictionary API request timed out for '%s'", word)
        return "The dictionary service is taking too long. Please try again."
    except requests.exceptions.RequestException as exc:
        logger.error("Dictionary API request failed for '%s': %s", word, exc)
        return "Dictionary service is unavailable right now. Please try again later."
    except Exception as e:
        logger.error("Error looking up '%s': %s", word, e)
        return "I had trouble looking that up. Please try again later."
