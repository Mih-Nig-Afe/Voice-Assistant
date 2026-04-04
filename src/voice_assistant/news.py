"""
News integration module for Voice Assistant.

Fetches latest headlines using the GNews API (free, no key required for basic use)
and NewsAPI.org as fallback.
"""

import time
from typing import Optional
from email.utils import parsedate_to_datetime

import requests
import re

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger
from voice_assistant.runtime import sanitize_query

logger = get_logger("news")

# GNews free API (no key required for basic use)
_GNEWS_BASE_URL = "https://gnews.io/api/v4"
_TOPIC_TOKEN_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "on",
    "in",
    "for",
    "with",
    "about",
    "regarding",
    "latest",
    "current",
    "update",
    "updates",
    "news",
    "headlines",
    "case",
    "situation",
}
_GENERIC_CONFLICT_KEYWORDS = {
    "war",
    "conflict",
    "attack",
    "attacking",
    "attacked",
    "strike",
    "strikes",
    "fighting",
    "fight",
    "missile",
    "ceasefire",
}
_WEAK_TOPIC_KEYWORDS = {"us"}
_NASA_BREAKING_NEWS_RSS = "https://www.nasa.gov/rss/dyn/breaking_news.rss"
_NASA_TOPIC_HINTS = {"nasa", "artemis", "orion", "sls", "moon", "lunar", "apollo"}


def _topic_keywords(topic: str) -> list[str]:
    """Extract meaningful keywords from a topic string."""
    raw_tokens = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-\.'#+]*", (topic or "").lower())
    keywords: list[str] = []
    for raw in raw_tokens:
        token = raw.strip(" .,'!?\"")
        if token in {"u.s", "u.s.", "usa"}:
            token = "us"
        if not token or token in _TOPIC_TOKEN_STOPWORDS:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:8]


def _keyword_pattern(keyword: str) -> str:
    """Return regex pattern for one topic keyword."""
    if keyword == "us":
        return r"\b(?:u\.s\.?|united states|american)\b"
    return rf"\b{re.escape(keyword)}\b"


def _matched_topic_keywords(text: str, keywords: list[str]) -> set[str]:
    """Return set of keywords matched in text using exact+light stem checks."""
    lowered = (text or "").lower()
    if not lowered or not keywords:
        return set()

    text_tokens = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-']*", lowered)
    matched: set[str] = set()
    for keyword in keywords:
        pattern = _keyword_pattern(keyword)
        if re.search(pattern, lowered):
            matched.add(keyword)
            continue
        if len(keyword) >= 5:
            stem = keyword[:4]
            if any(token.startswith(stem) for token in text_tokens):
                matched.add(keyword)
    return matched


def _score_news_text_relevance(text: str, keywords: list[str]) -> int:
    """Score relevance of text against topic keywords."""
    if not text or not keywords:
        return 0

    matched = _matched_topic_keywords(text, keywords)
    score = 0
    for keyword in matched:
        if keyword in _WEAK_TOPIC_KEYWORDS:
            score += 1
        elif keyword in _GENERIC_CONFLICT_KEYWORDS:
            score += 2
        else:
            score += 3
    return score


def _is_topic_match_sufficient(matched_keywords: set[str], keywords: list[str]) -> bool:
    """Gate noisy matches so entity-heavy topics stay on-topic."""
    if not keywords:
        return True
    if not matched_keywords:
        return False

    specific_keywords = {
        keyword
        for keyword in keywords
        if keyword not in _WEAK_TOPIC_KEYWORDS and keyword not in _GENERIC_CONFLICT_KEYWORDS
    }
    if specific_keywords and not matched_keywords.intersection(specific_keywords):
        return False

    min_keyword_matches = 2 if len(keywords) >= 3 else 1
    return len(matched_keywords) >= min_keyword_matches


def _rank_articles_for_topic(articles: list[dict], topic: str) -> list[dict]:
    """Rank/filter articles by topic relevance."""
    keywords = _topic_keywords(topic)
    if not keywords:
        return articles

    scored: list[tuple[int, dict]] = []
    for article in articles:
        title = str(article.get("title", ""))
        description = str(article.get("description", ""))
        content = str(article.get("content", ""))
        matched = _matched_topic_keywords(f"{title} {description} {content}", keywords)
        if not _is_topic_match_sufficient(matched, keywords):
            continue
        title_score = _score_news_text_relevance(title, keywords)
        body_score = _score_news_text_relevance(f"{description} {content}", keywords)
        specificity_bonus = len(
            {
                keyword
                for keyword in matched
                if keyword not in _WEAK_TOPIC_KEYWORDS
                and keyword not in _GENERIC_CONFLICT_KEYWORDS
            }
        )
        total = (title_score * 3) + body_score + (specificity_bonus * 2)
        scored.append((total, article))

    ranked = [article for score, article in sorted(scored, key=lambda item: item[0], reverse=True) if score > 0]
    return ranked


def _format_topic_label(topic: Optional[str]) -> str:
    """Format topic text for human-friendly response headers."""
    clean = (topic or "").strip()
    if not clean:
        return ""
    tokens = clean.split()
    mapped = []
    for token in tokens:
        lower = token.lower()
        if lower in {"us", "usa"}:
            mapped.append("US")
        elif lower == "uk":
            mapped.append("UK")
        elif lower == "eu":
            mapped.append("EU")
        else:
            mapped.append(token)
    return " ".join(mapped)


def _format_pub_date(pub_date: str) -> str:
    """Format RSS pubDate into a short, readable date."""
    raw = (pub_date or "").strip()
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return raw[:16]


def _is_nasa_space_topic(topic: Optional[str]) -> bool:
    """Return True when a topic is likely about NASA/space missions."""
    normalized = (topic or "").strip().lower()
    if not normalized:
        return False
    return any(hint in normalized for hint in _NASA_TOPIC_HINTS)


def _get_nasa_headlines(topic: str, count: int = 5) -> str:
    """
    Fetch NASA updates from NASA's free official RSS feed.

    Returns empty string when feed has no relevant entries, so caller can fallback.
    """
    try:
        start = time.perf_counter()
        response = requests.get(_NASA_BREAKING_NEWS_RSS, timeout=Config.HTTP_TIMEOUT)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "NASA RSS request completed in %.1fms (status=%s)",
            elapsed_ms,
            response.status_code,
        )
        response.raise_for_status()

        xml = response.text or ""
        items = re.findall(r"<item>(.*?)</item>", xml, flags=re.IGNORECASE | re.DOTALL)
        if not items:
            return ""

        keywords = _topic_keywords(topic)
        selected: list[tuple[str, str]] = []
        for raw_item in items:
            title_match = re.search(
                r"<title>\s*(?:<!\[CDATA\[(.*?)\]\]>|(.*?))\s*</title>",
                raw_item,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                continue
            title = (title_match.group(1) or title_match.group(2) or "").strip()
            if not title:
                continue

            if keywords:
                matched = _matched_topic_keywords(title, keywords)
                if not _is_topic_match_sufficient(matched, keywords):
                    continue

            date_match = re.search(
                r"<pubDate>\s*(.*?)\s*</pubDate>", raw_item, flags=re.IGNORECASE | re.DOTALL
            )
            date_label = _format_pub_date(date_match.group(1) if date_match else "")
            selected.append((title, date_label))
            if len(selected) >= count:
                break

        if not selected:
            return ""

        lines = []
        for idx, (title, date_label) in enumerate(selected[:count], 1):
            source = f"NASA, {date_label}" if date_label else "NASA"
            lines.append(f"{idx}. {title} ({source})")

        pretty_topic = _format_topic_label(topic)
        header = (
            f"Here are the latest official NASA updates on {pretty_topic}:"
            if pretty_topic
            else "Here are the latest official NASA updates:"
        )
        return header + "\n" + "\n".join(lines)
    except Exception as exc:
        logger.error("NASA RSS fetch failed: %s", exc)
        return ""


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

    if topic and _is_nasa_space_topic(topic):
        nasa_updates = _get_nasa_headlines(topic=topic, count=count)
        if nasa_updates:
            return nasa_updates

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

        if topic:
            ranked_articles = _rank_articles_for_topic(articles, topic)
            if not ranked_articles:
                logger.info(
                    "No strongly relevant topic headlines for '%s'; retrying with general top headlines.",
                    topic,
                )
                return get_top_headlines(topic=None, count=count)
            articles = ranked_articles

        lines = []
        for i, article in enumerate(articles[:count], 1):
            title = article.get("title", "No title")
            source = article.get("source", {}).get("name", "Unknown")
            lines.append(f"{i}. {title} ({source})")

        pretty_topic = _format_topic_label(topic)
        header = (
            f"Here are the latest headlines on {pretty_topic}:"
            if pretty_topic
            else "Here are the latest headlines:"
        )
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

        if topic and headlines:
            keywords = _topic_keywords(topic)
            if keywords:
                scored = []
                for headline in headlines:
                    matched = _matched_topic_keywords(headline, keywords)
                    if not _is_topic_match_sufficient(matched, keywords):
                        continue
                    specificity_bonus = len(
                        {
                            keyword
                            for keyword in matched
                            if keyword not in _WEAK_TOPIC_KEYWORDS
                            and keyword not in _GENERIC_CONFLICT_KEYWORDS
                        }
                    )
                    score = _score_news_text_relevance(headline, keywords) + (
                        specificity_bonus * 2
                    )
                    scored.append((score, headline))
                ranked = [
                    headline
                    for score, headline in sorted(
                        scored, key=lambda item: item[0], reverse=True
                    )
                    if score > 0
                ]
                if ranked:
                    headlines = ranked[:count]
                else:
                    logger.info(
                        "No relevant RSS topic headlines for '%s'; retrying with general headlines.",
                        topic,
                    )
                    return _get_headlines_fallback(topic=None, count=count)

        if not headlines and topic:
            logger.info(
                "No RSS topic headlines for '%s'; retrying with general headlines.",
                topic,
            )
            return _get_headlines_fallback(topic=None, count=count)
        if not headlines:
            return "No news headlines available right now."

        lines = [f"{i}. {h}" for i, h in enumerate(headlines, 1)]
        pretty_topic = _format_topic_label(topic)
        header = (
            f"Here are the latest headlines on {pretty_topic}:"
            if pretty_topic
            else "Here are the latest headlines:"
        )
        return header + "\n" + "\n".join(lines)

    except Exception as e:
        logger.error("News fallback error: %s", e)
        return "I couldn't fetch the news right now. No news API key is configured."
