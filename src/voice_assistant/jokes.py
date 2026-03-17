"""
Jokes module for Voice Assistant.

Fetches random jokes from the free JokeAPI (no API key required).
"""

import requests
import time

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger

logger = get_logger("jokes")

# JokeAPI - completely free, no key needed
_JOKE_API_URL = "https://v2.jokeapi.dev/joke/Any"


def get_joke(category: str = "Any") -> str:
    """
    Fetch a random joke from JokeAPI.

    Rate limit: 120 requests/minute.

    Args:
        category: Joke category (Any, Programming, Misc, Pun, Spooky, Christmas).

    Returns:
        A joke string (setup + delivery for twopart, or single joke).
    """
    try:
        params = {
            "type": "twopart,single",
            "blacklistFlags": "nsfw,racist,sexist",
        }

        valid_categories = {"any", "programming", "misc", "pun", "spooky", "christmas"}
        cat = category.strip().lower()
        url_category = cat.capitalize() if cat in valid_categories else "Any"

        url = f"https://v2.jokeapi.dev/joke/{url_category}"
        start = time.perf_counter()
        response = requests.get(url, params=params, timeout=Config.HTTP_TIMEOUT)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "JokeAPI request completed in %.1fms (status=%s)",
            elapsed_ms,
            response.status_code,
        )
        data = response.json()

        if response.status_code == 429:
            return "Too many joke requests right now. Please try again in a moment."

        if data.get("error"):
            logger.warning("JokeAPI error: %s", data.get("message"))
            return "I couldn't think of a joke right now. Maybe I need better material!"

        if data.get("type") == "twopart":
            setup = data.get("setup", "")
            delivery = data.get("delivery", "")
            return f"{setup} ... {delivery}"
        else:
            return data.get("joke", "I forgot the punchline!")

    except requests.exceptions.Timeout:
        logger.error("JokeAPI request timed out")
        return "The joke service is being slow. Try again?"
    except requests.exceptions.RequestException as exc:
        logger.error("JokeAPI request failed: %s", exc)
        return "I couldn't reach the joke service. Please try again later."
    except Exception as e:
        logger.error("Error fetching joke: %s", e)
        return "I'm having trouble being funny right now. Please try again later."
