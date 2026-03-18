"""
News integration module for Voice Assistant.

Fetches latest headlines using the GNews API (free, no key required for basic use)
and NewsAPI.org as fallback.
"""

import time
from typing import Optional

import requests

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger
from voice_assistant.runtime import sanitize_query

logger = get_logger("news")

# GNews free API (no key required for basic use)
_GNEWS_BASE_URL = "https://gnews.io/api/v4"


def get_top_headlines(topic: Optional[str] = None, count: int = 5) -> str:
    """
    Fetch top news headlines, optionally filtered by topic.

    Uses GNews API (free tier: 100 requests/day, no credit card).

    Args:
        topic: Optional topic to filter news (e.g., "technology", "sports").
        count: Number of headlines to return (max 10 on free tier).

    Returns:
        Formatted string of news headlines.
    """
    api_key = Config.GNEWS_API_KEY
    topic = sanitize_query(topic or "", max_length=80) or None
    if not api_key:
        return _get_headlines_fallback(topic, count)

    try:
        if topic:
            endpoint = f"{_GNEWS_BASE_URL}/search"
            params = {"q": topic, "token": api_key, "max": min(count, 10), "lang": "en"}
        else:
            endpoint = f"{_GNEWS_BASE_URL}/top-headlines"
            params = {"token": api_key, "max": min(count, 10), "lang": "en"}

        start = time.perf_counter()
        response = requests.get(endpoint, params=params, timeout=Config.HTTP_TIMEOUT)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "GNews request completed in %.1fms (status=%s)",
            elapsed_ms,
            response.status_code,
        )
        data = response.json()

        if response.status_code == 429:
            return "News service rate limit reached. Please try again later."

        articles = data.get("articles", [])
        if not articles:
            if topic:
                logger.info(
                    "No topic-filtered news for '%s'; retrying with general top headlines.",
                    topic,
                )
                return get_top_headlines(topic=None, count=count)
            return "No news articles found right now."

        lines = []
        for i, article in enumerate(articles[:count], 1):
            title = article.get("title", "No title")
            source = article.get("source", {}).get("name", "Unknown")
            lines.append(f"{i}. {title} — {source}")

        header = f"Top news{' about ' + topic if topic else ''}:"
        return header + "\n" + "\n".join(lines)

    except requests.exceptions.Timeout:
        logger.error("News API request timed out")
        return "The news service is taking too long. Please try again."
    except requests.exceptions.RequestException as exc:
        logger.error("News API request failed: %s", exc)
        return "I couldn't fetch the news right now. Please try later."
    except Exception as e:
        logger.error("Error fetching news: %s", e)
        return "I couldn't fetch the news right now. Please try later."


def _get_headlines_fallback(topic: Optional[str] = None, count: int = 5) -> str:
    """
    Fallback: Use a free RSS-based approach when no API key is set.

    Uses the free Google News RSS feed (no API key needed).
    """
    try:
        if topic:
            url = f"https://news.google.com/rss/search?q={topic}&hl=en-US&gl=US&ceid=US:en"
        else:
            url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"

        start = time.perf_counter()
        response = requests.get(url, timeout=Config.HTTP_TIMEOUT)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "Google News RSS request completed in %.1fms (status=%s)",
            elapsed_ms,
            response.status_code,
        )
        response.raise_for_status()

        # Simple XML parsing without extra dependency
        import re

        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", response.text)
        if not titles:
            titles = re.findall(r"<title>(.*?)</title>", response.text)

        # Skip the feed title (first item)
        headlines = titles[1 : count + 1] if len(titles) > 1 else titles[:count]

        if not headlines and topic:
            logger.info(
                "No RSS topic headlines for '%s'; retrying with general headlines.",
                topic,
            )
            return _get_headlines_fallback(topic=None, count=count)
        if not headlines:
            return "No news headlines available right now."

        lines = [f"{i}. {h}" for i, h in enumerate(headlines, 1)]
        header = f"Top news{' about ' + topic if topic else ''}:"
        return header + "\n" + "\n".join(lines)

    except Exception as e:
        logger.error("News fallback error: %s", e)
        return "I couldn't fetch the news right now. No news API key is configured."
