"""
News integration module for Voice Assistant.

Fetches latest headlines using the GNews API (free, no key required for basic use)
and NewsAPI.org as fallback.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import html
import time
from typing import Optional
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

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
_CONFLICT_TOPIC_HINTS = {
    "war",
    "conflict",
    "iran",
    "israel",
    "ukraine",
    "russia",
    "gaza",
    "hamas",
    "lebanon",
    "beirut",
    "syria",
    "yemen",
    "sudan",
    "missile",
    "strike",
    "strikes",
    "attack",
    "attacking",
    "ceasefire",
}
_MIDDLE_EAST_TOPIC_HINTS = {
    "iran",
    "israel",
    "gaza",
    "hamas",
    "lebanon",
    "beirut",
    "syria",
    "yemen",
    "middle",
    "east",
}
_CONFLICT_NEWS_RSS_SOURCES = [
    ("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NPR", "https://feeds.npr.org/1004/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("DW", "https://rss.dw.com/rdf/rss-en-world"),
]
_MIDDLE_EAST_CONFLICT_RSS_SOURCES = [
    ("BBC News", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
]
_RECENT_HEADLINE_ITEMS: list[dict] = []
_ARTICLE_DETAIL_CACHE: dict[str, dict] = {}
_ARTICLE_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
_ARTICLE_BOILERPLATE_PHRASES = {
    "all rights reserved",
    "sign up for",
    "newsletter",
    "advertisement",
    "cookie policy",
    "privacy policy",
    "terms of use",
    "watch live",
    "read more",
}


def _safe_timeout(default: float = 5.0, cap: Optional[float] = None) -> float:
    """Return a safe numeric timeout from config."""
    try:
        timeout = float(getattr(Config, "HTTP_TIMEOUT", default) or default)
    except Exception:
        timeout = default
    if cap is not None:
        timeout = min(timeout, cap)
    return max(timeout, 1.0)


def _headline_match_key(title: str) -> str:
    """Normalize a headline title for cache matching."""
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def _source_base(source: str) -> str:
    """Normalize a source label by stripping appended date metadata."""
    return (source or "").split(",", 1)[0].strip().lower()


def _normalize_snippet(text: str, *, max_chars: int = 700) -> str:
    """Normalize text snippets from APIs or scraped pages."""
    clean = html.unescape(text or "")
    clean = re.sub(r"\[\+\d+\s+chars\]", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return ""
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."


def _dedupe_snippets(snippets: list[str]) -> list[str]:
    """Deduplicate text snippets while preserving order."""
    deduped: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        clean = _normalize_snippet(snippet)
        if not clean:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", clean.lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(clean)
    return deduped


def _cache_recent_headline_items(items: list[dict]) -> None:
    """Replace the in-memory recent headline cache."""
    global _RECENT_HEADLINE_ITEMS
    cached: list[dict] = []
    for item in items:
        title = _normalize_snippet(str(item.get("title", "")), max_chars=240)
        if not title:
            continue
        cached.append(
            {
                "title": title,
                "source": _normalize_snippet(str(item.get("source", "")), max_chars=80),
                "date_label": _normalize_snippet(
                    str(item.get("date_label", "")), max_chars=32
                ),
                "summary": _normalize_snippet(
                    str(item.get("summary", "")), max_chars=320
                ),
                "content": _normalize_snippet(
                    str(item.get("content", "")), max_chars=800
                ),
                "url": str(item.get("url", "")).strip(),
            }
        )
    _RECENT_HEADLINE_ITEMS = cached


def _find_recent_headline_item(title: str, source: str = "") -> Optional[dict]:
    """Find the most recent cached headline matching title/source."""
    title_key = _headline_match_key(title)
    if not title_key:
        return None

    source_key = _source_base(source)
    fallback_match = None
    for item in _RECENT_HEADLINE_ITEMS:
        if _headline_match_key(str(item.get("title", ""))) != title_key:
            continue
        item_source = _source_base(str(item.get("source", "")))
        if source_key and item_source == source_key:
            return item
        if fallback_match is None:
            fallback_match = item
    return fallback_match


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
        if keyword not in _WEAK_TOPIC_KEYWORDS
        and keyword not in _GENERIC_CONFLICT_KEYWORDS
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

    ranked = [
        article
        for score, article in sorted(scored, key=lambda item: item[0], reverse=True)
        if score > 0
    ]
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


def _is_conflict_topic(topic: Optional[str]) -> bool:
    """Return True when a topic likely refers to war/conflict coverage."""
    keywords = set(_topic_keywords(topic or ""))
    if not keywords:
        return False
    if keywords.intersection(_CONFLICT_TOPIC_HINTS):
        return True
    return bool(
        keywords.intersection(_GENERIC_CONFLICT_KEYWORDS) and len(keywords) >= 2
    )


def _conflict_feed_sources(topic: str) -> list[tuple[str, str]]:
    """Return curated RSS feeds for conflict-heavy topics."""
    keywords = set(_topic_keywords(topic))
    ordered_sources: list[tuple[str, str]] = []
    if keywords.intersection(_MIDDLE_EAST_TOPIC_HINTS):
        ordered_sources.extend(_MIDDLE_EAST_CONFLICT_RSS_SOURCES)
    ordered_sources.extend(_CONFLICT_NEWS_RSS_SOURCES)

    deduped: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for source_name, url in ordered_sources:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append((source_name, url))
    return deduped


def _xml_local_name(tag: str) -> str:
    """Return an XML tag name without namespace."""
    raw = str(tag or "")
    if "}" in raw:
        raw = raw.rsplit("}", 1)[-1]
    if ":" in raw:
        raw = raw.rsplit(":", 1)[-1]
    return raw.lower()


def _element_text(element: ET.Element) -> str:
    """Return normalized text content for an XML element."""
    text = " ".join(
        part.strip() for part in element.itertext() if part and part.strip()
    )
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _parse_feed_datetime(raw_value: str) -> Optional[datetime]:
    """Parse common RSS/Atom datetime values into UTC datetimes."""
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_feed_title(title: str, source_name: str) -> str:
    """Clean common feed-specific suffixes from RSS titles."""
    clean = re.sub(r"\s+", " ", html.unescape(title or "")).strip()
    suffix_patterns = {
        "BBC News": [r"\s*-\s*BBC News\s*$"],
        "DW": [r"\s*\|\s*DW\s*$"],
    }
    for pattern in suffix_patterns.get(source_name, []):
        clean = re.sub(pattern, "", clean, flags=re.IGNORECASE).strip()
    return clean


def _extract_feed_link(child: ET.Element) -> str:
    """Extract an RSS/Atom link value from a feed child element."""
    href = str(child.attrib.get("href", "")).strip()
    if href:
        return href
    return _element_text(child)


def _parse_rss_entries(xml_text: str, source_name: str) -> list[dict]:
    """Parse RSS/Atom XML into normalized feed entries."""
    try:
        root = ET.fromstring(xml_text or "")
    except ET.ParseError:
        return []

    entries: list[dict] = []
    for element in root.iter():
        if _xml_local_name(element.tag) not in {"item", "entry"}:
            continue

        title = ""
        link = ""
        published_raw = ""
        summary = ""
        for child in list(element):
            child_name = _xml_local_name(child.tag)
            if child_name == "title" and not title:
                title = _element_text(child)
            elif child_name == "link" and not link:
                link = _extract_feed_link(child)
            elif (
                child_name in {"pubdate", "published", "updated", "date"}
                and not published_raw
            ):
                published_raw = _element_text(child)
            elif child_name in {"description", "summary", "content"} and not summary:
                summary = _element_text(child)

        clean_title = _normalize_feed_title(title, source_name)
        if not clean_title:
            continue

        published_at = _parse_feed_datetime(published_raw)
        entries.append(
            {
                "title": clean_title,
                "summary": summary,
                "source": source_name,
                "published_at": published_at,
                "published_sort": published_at.timestamp() if published_at else 0.0,
                "date_label": published_at.strftime("%Y-%m-%d") if published_at else "",
                "url": link,
            }
        )
    return entries


def _fetch_rss_entries(source_name: str, url: str) -> list[dict]:
    """Fetch and parse one RSS source."""
    try:
        start = time.perf_counter()
        response = requests.get(url, timeout=min(Config.HTTP_TIMEOUT, 4))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "%s RSS request completed in %.1fms (status=%s)",
            source_name,
            elapsed_ms,
            response.status_code,
        )
        response.raise_for_status()
        return _parse_rss_entries(response.text or "", source_name)
    except Exception as exc:
        logger.warning("%s RSS fetch failed: %s", source_name, exc)
        return []


def _dedupe_feed_title_key(title: str) -> str:
    """Build a stable dedupe key for cross-source headline titles."""
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def _extract_meta_description(html_text: str) -> str:
    """Extract a useful meta description from article HTML."""
    patterns = [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\'](.*?)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _normalize_snippet(match.group(1), max_chars=320)
    return ""


def _strip_html_tags(fragment: str) -> str:
    """Remove tags from a small HTML fragment."""
    clean = re.sub(r"<[^>]+>", " ", fragment or "")
    return _normalize_snippet(clean, max_chars=900)


def _extract_article_paragraphs(html_text: str) -> list[str]:
    """Extract usable article paragraphs from HTML."""
    working = re.sub(
        r"<(?:script|style|noscript)[^>]*>.*?</(?:script|style|noscript)>",
        " ",
        html_text or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    article_match = re.search(
        r"<article\b[^>]*>(.*?)</article>", working, flags=re.IGNORECASE | re.DOTALL
    )
    if article_match:
        working = article_match.group(1)

    paragraphs = re.findall(
        r"<p\b[^>]*>(.*?)</p>", working, flags=re.IGNORECASE | re.DOTALL
    )
    extracted: list[str] = []
    for paragraph in paragraphs:
        clean = _strip_html_tags(paragraph)
        if len(clean) < 60:
            continue
        lowered = clean.lower()
        if any(phrase in lowered for phrase in _ARTICLE_BOILERPLATE_PHRASES):
            continue
        extracted.append(clean)
    return _dedupe_snippets(extracted)[:4]


def _fetch_article_detail(url: str) -> dict:
    """Fetch article HTML and extract lightweight detail text."""
    target = (url or "").strip()
    if not target:
        return {}
    if target in _ARTICLE_DETAIL_CACHE:
        return dict(_ARTICLE_DETAIL_CACHE[target])

    try:
        start = time.perf_counter()
        response = requests.get(
            target,
            headers=_ARTICLE_FETCH_HEADERS,
            timeout=_safe_timeout(cap=5.0),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "Article fetch completed in %.1fms (status=%s, url=%s)",
            elapsed_ms,
            response.status_code,
            target,
        )
        response.raise_for_status()
        html_text = response.text or ""
        paragraphs = _extract_article_paragraphs(html_text)
        detail = {
            "url": getattr(response, "url", target) or target,
            "meta_description": _extract_meta_description(html_text),
            "excerpt": " ".join(paragraphs[:3]).strip(),
        }
        _ARTICLE_DETAIL_CACHE[target] = detail
        return dict(detail)
    except Exception as exc:
        logger.warning("Article fetch failed for %s: %s", target, exc)
        _ARTICLE_DETAIL_CACHE[target] = {}
        return {}


def get_cached_article_context(title: str, source: str = "") -> dict:
    """Return cached article context for a displayed headline title."""
    item = _find_recent_headline_item(title, source)
    if not item:
        return {}

    article_detail = _fetch_article_detail(str(item.get("url", "")))
    source_name = str(item.get("source", "")).strip()
    date_label = str(item.get("date_label", "")).strip()
    source_label = source_name
    if source_name and date_label:
        source_label = f"{source_name}, {date_label}"
    elif date_label:
        source_label = date_label

    # Prefer scraped article metadata when available because it is often
    # fresher/more specific than API summary snippets.
    summary_candidates = _dedupe_snippets(
        [
            str(article_detail.get("meta_description", "")),
            str(item.get("summary", "")),
            str(item.get("content", "")),
        ]
    )
    detail_candidates = _dedupe_snippets(
        [
            str(item.get("content", "")),
            str(article_detail.get("excerpt", "")),
            str(item.get("summary", "")),
            str(article_detail.get("meta_description", "")),
        ]
    )

    return {
        "title": str(item.get("title", "")).strip(),
        "source": source_name,
        "source_label": source_label,
        "date_label": date_label,
        "url": str(article_detail.get("url", "") or item.get("url", "")).strip(),
        "summary": summary_candidates[0] if summary_candidates else "",
        "excerpt": " ".join(detail_candidates[:3]).strip(),
    }


def _get_conflict_headlines(topic: str, count: int = 5) -> str:
    """
    Fetch curated conflict headlines from free official RSS feeds.

    Returns empty string when no relevant curated items are available.
    """
    keywords = _topic_keywords(topic)
    if not keywords:
        return ""

    feed_sources = _conflict_feed_sources(topic)
    if not feed_sources:
        return ""

    candidates: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(4, len(feed_sources))) as executor:
        future_map = {
            executor.submit(_fetch_rss_entries, source_name, url): (
                source_index,
                source_name,
            )
            for source_index, (source_name, url) in enumerate(feed_sources)
        }
        for future in as_completed(future_map):
            source_index, source_name = future_map[future]
            entries = future.result() or []
            for entry in entries:
                text = f"{entry['title']} {entry.get('summary', '')}".strip()
                matched = _matched_topic_keywords(text, keywords)
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
                score = _score_news_text_relevance(text, keywords) + (
                    specificity_bonus * 2
                )
                if score <= 0:
                    continue
                candidates.append(
                    {
                        **entry,
                        "score": score,
                        "source_index": source_index,
                        "source_name": source_name,
                    }
                )

    if not candidates:
        return ""

    ranked = sorted(
        candidates,
        key=lambda item: (
            item["score"],
            item["published_sort"],
            -item["source_index"],
        ),
        reverse=True,
    )

    selected: list[dict] = []
    seen_titles: set[str] = set()
    for candidate in ranked:
        dedupe_key = _dedupe_feed_title_key(candidate["title"])
        if not dedupe_key or dedupe_key in seen_titles:
            continue
        seen_titles.add(dedupe_key)
        selected.append(candidate)
        if len(selected) >= count:
            break

    if not selected:
        return ""

    _cache_recent_headline_items(selected[:count])

    pretty_topic = _format_topic_label(topic)
    header = (
        f"Here are the latest curated conflict headlines on {pretty_topic}:"
        if pretty_topic
        else "Here are the latest curated conflict headlines:"
    )
    lines = []
    for idx, item in enumerate(selected[:count], 1):
        source = item["source"]
        if item["date_label"]:
            source = f"{source}, {item['date_label']}"
        lines.append(f"{idx}. {item['title']} ({source})")
    return header + "\n" + "\n".join(lines)


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

        entries = _parse_rss_entries(response.text or "", "NASA")
        if not entries:
            return ""

        keywords = _topic_keywords(topic)
        selected: list[dict] = []
        for entry in entries:
            title = str(entry.get("title", "")).strip()
            if keywords:
                matched = _matched_topic_keywords(title, keywords)
                if not _is_topic_match_sufficient(matched, keywords):
                    continue

            selected.append(entry)
            if len(selected) >= count:
                break

        if not selected:
            return ""

        _cache_recent_headline_items(selected[:count])

        lines = []
        for idx, item in enumerate(selected[:count], 1):
            title = str(item.get("title", "")).strip()
            date_label = str(item.get("date_label", "")).strip()
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
    if topic and _is_conflict_topic(topic):
        curated_conflict = _get_conflict_headlines(topic=topic, count=count)
        if curated_conflict:
            return curated_conflict

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

        selected_items: list[dict] = []
        lines = []
        for i, article in enumerate(articles[:count], 1):
            title = str(article.get("title", "No title")).strip()
            source = str(article.get("source", {}).get("name", "Unknown")).strip()
            published_raw = str(article.get("publishedAt", "")).strip()
            published_at = _parse_feed_datetime(published_raw)
            selected_items.append(
                {
                    "title": title,
                    "source": source,
                    "date_label": (
                        published_at.strftime("%Y-%m-%d") if published_at else ""
                    ),
                    "summary": str(article.get("description", "")).strip(),
                    "content": str(article.get("content", "")).strip(),
                    "url": str(article.get("url", "")).strip(),
                }
            )
            lines.append(f"{i}. {title} ({source})")

        _cache_recent_headline_items(selected_items)

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

        entries = _parse_rss_entries(response.text or "", "Google News")
        headlines = entries[:]

        if topic and headlines:
            keywords = _topic_keywords(topic)
            if keywords:
                scored = []
                for entry in headlines:
                    headline = str(entry.get("title", "")).strip()
                    summary = str(entry.get("summary", "")).strip()
                    matched = _matched_topic_keywords(f"{headline} {summary}", keywords)
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
                    score = _score_news_text_relevance(
                        f"{headline} {summary}", keywords
                    ) + (specificity_bonus * 2)
                    scored.append((score, entry))
                ranked_entries = [
                    entry
                    for score, entry in sorted(
                        scored, key=lambda item: item[0], reverse=True
                    )
                    if score > 0
                ]
                if ranked_entries:
                    headlines = ranked_entries[:count]
                else:
                    logger.info(
                        "No relevant RSS topic headlines for '%s'; retrying with general headlines.",
                        topic,
                    )
                    return _get_headlines_fallback(topic=None, count=count)

        if headlines:
            headlines = headlines[:count]

        if not headlines and topic:
            logger.info(
                "No RSS topic headlines for '%s'; retrying with general headlines.",
                topic,
            )
            return _get_headlines_fallback(topic=None, count=count)
        if not headlines:
            return "No news headlines available right now."

        _cache_recent_headline_items(headlines)

        lines = [f"{i}. {item.get('title', '')}" for i, item in enumerate(headlines, 1)]
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
