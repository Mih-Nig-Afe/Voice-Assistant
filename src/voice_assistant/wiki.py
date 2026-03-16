"""
Wikipedia integration module for Voice Assistant.

Fetches article summaries from Wikipedia with error handling
for disambiguation and missing pages.
"""

import wikipedia

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger

logger = get_logger("wiki")


def get_summary(query: str) -> str:
    """
    Fetch a Wikipedia summary for the given query.

    Args:
        query: Topic to search for on Wikipedia.

    Returns:
        Summary text (up to configured sentence count), or an error message.
    """
    if not query or not query.strip():
        return "Please specify a topic for me to search."

    query = query.strip()
    logger.info("Searching Wikipedia for: %s", query)

    try:
        wikipedia.set_lang(Config.WIKI_LANGUAGE)
        summary: str = wikipedia.summary(query, sentences=Config.WIKI_SENTENCES)
        logger.debug("Wikipedia result: %d chars", len(summary))
        return summary

    except wikipedia.exceptions.DisambiguationError as e:
        options = e.options[:3]
        logger.info("Wikipedia disambiguation for '%s': %s", query, options)
        return f"Your query is too broad. Did you mean: {', '.join(options)}?"

    except wikipedia.exceptions.PageError:
        logger.warning("Wikipedia page not found: '%s'", query)
        return "I couldn't find any information on that topic. Please try rephrasing."

    except Exception as e:
        logger.error("Wikipedia error for '%s': %s", query, e)
        return "I encountered an issue accessing Wikipedia. Please try again later."

