"""Web frontend backend for the Voice Assistant (Miehab).

Serves a browser UI and exposes a chat API so users can operate the
assistant with typed or spoken input.
"""

from contextlib import asynccontextmanager
import base64
import binascii
from pathlib import Path
import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from voice_assistant.ai_engine import generate_response
from voice_assistant.calculator import calculate
from voice_assistant.config import Config
from voice_assistant.conversation import memory
from voice_assistant.datetime_cmd import (
    get_current_date,
    get_current_time,
    get_full_datetime,
)
from voice_assistant.dictionary import get_definition
from voice_assistant.jokes import get_joke
from voice_assistant.logging_config import get_logger, setup_logging
from voice_assistant.news import get_top_headlines
from voice_assistant.system_info import get_battery_status, get_platform_summary
from voice_assistant.weather import get_weather
from voice_assistant.wiki import get_summary

logger = get_logger("web")

_FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

app = FastAPI(title="Miehab Web Assistant", version="1.0.0")
app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

_pending_weather_city: bool = False
_last_weather_city: str = ""
_last_news_topic: str = ""
_last_news_headline_response: str = ""
_groq_audio_client = None
_CITY_STOPWORDS = {
    "weather",
    "temperature",
    "city",
    "location",
    "where",
    "what",
    "is",
    "the",
    "in",
    "for",
    "of",
    "at",
    "to",
    "now",
    "today",
    "please",
    "kindly",
    "check",
    "tell",
    "me",
    "show",
    "give",
    "right",
    "current",
    "currently",
    "moment",
    "its",
    "it",
    "detail",
    "details",
}
_NEWS_TOPIC_STOPWORDS = {
    "news",
    "headlines",
    "headline",
    "tell",
    "me",
    "your",
    "the",
    "a",
    "an",
    "and",
    "or",
    "about",
    "on",
    "for",
    "of",
    "in",
    "with",
    "latest",
    "current",
    "today",
    "show",
    "give",
    "get",
    "please",
    "what",
    "how",
    "whats",
    "what's",
    "who",
    "is",
    "happening",
    "happenings",
    "update",
    "updates",
    "any",
    "new",
    "based",
    "case",
    "situation",
    "story",
    "world",
    "going",
    "especially",
    "look",
    "other",
    "such",
    "as",
    "more",
    "between",
    "our",
    "common",
    "terms",
    "term",
    "include",
    "includes",
    "may",
    "world-news",
    "worldnews",
}
_NON_CITY_FOLLOWUP_TOKENS = {
    "i",
    "im",
    "i'm",
    "ive",
    "i've",
    "me",
    "my",
    "you",
    "your",
    "we",
    "they",
    "he",
    "she",
    "it",
    "kinda",
    "kind",
    "feeling",
    "feel",
    "too",
    "very",
    "really",
    "quite",
    "just",
    "hot",
    "cold",
    "fine",
    "okay",
    "ok",
    "good",
    "bad",
    "better",
    "worse",
    "sorry",
    "thanks",
    "thank",
}
_NEWS_DIRECT_HINTS = {"news", "headline", "headlines", "happening"}
_NEWS_UPDATE_HINTS = {"update", "updates", "latest", "current", "new", "developments"}
_NON_NEWS_UPDATE_CONTEXT_WORDS = {
    "weather",
    "temperature",
    "time",
    "date",
    "battery",
    "system",
    "joke",
    "dictionary",
    "define",
    "calculate",
    "math",
    "wikipedia",
}
_NEWS_SUMMARY_HINTS = {
    "update",
    "updates",
    "happening",
    "situation",
    "details",
    "detailed",
    "deep",
    "deep dive",
    "dip",
    "brief",
    "breakdown",
    "explain",
    "summary",
    "going on",
}
_NEWS_LIST_HINTS = {"headline", "headlines", "list"}
_NEWS_CONFLICT_HINTS = {
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
_NEWS_ENTITY_HINTS = {
    "iran",
    "israel",
    "us",
    "usa",
    "u.s",
    "u.s.",
    "tehran",
    "gaza",
    "hamas",
    "russia",
    "ukraine",
}
_GENERAL_NEWS_TOPIC = "general"


class ChatRequest(BaseModel):
    """Incoming chat message payload."""

    message: str


class ChatResponse(BaseModel):
    """Outgoing chat message payload."""

    response: str
    should_exit: bool = False


class SpeechTranscribeRequest(BaseModel):
    """Incoming audio payload for server-side transcription."""

    audio_base64: str
    mime_type: Optional[str] = None
    file_name: Optional[str] = None


class SpeechTranscribeResponse(BaseModel):
    """Outgoing transcription payload."""

    transcript: str


class SpeechSynthesizeRequest(BaseModel):
    """Incoming text payload for server-side speech synthesis."""

    text: str


class SpeechSynthesizeResponse(BaseModel):
    """Outgoing synthesized speech payload."""

    audio_base64: str
    mime_type: str = "audio/mpeg"
    engine: str = "edge-tts"


def _decode_audio_base64(audio_base64: str) -> bytes:
    """Decode a base64 (or data URL) audio payload into bytes."""
    payload = (audio_base64 or "").strip()
    if not payload:
        raise ValueError("Audio payload is empty.")
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1].strip()
    try:
        return base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Audio payload is not valid base64 data.") from exc


def _audio_extension_from_mime(mime_type: Optional[str]) -> str:
    """Best-effort extension mapping for incoming browser audio."""
    if not mime_type:
        return "webm"
    lowered = mime_type.lower()
    if "webm" in lowered:
        return "webm"
    if "ogg" in lowered:
        return "ogg"
    if "wav" in lowered:
        return "wav"
    if "mp4" in lowered or "m4a" in lowered:
        return "m4a"
    if "mpeg" in lowered or "mp3" in lowered:
        return "mp3"
    return "webm"


def _safe_audio_filename(file_name: Optional[str], mime_type: Optional[str]) -> str:
    """Create a conservative filename accepted by transcription APIs."""
    if file_name:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]", "", file_name).strip("._")
        if cleaned:
            return cleaned
    return f"browser-mic.{_audio_extension_from_mime(mime_type)}"


def _extract_transcript_text(response: object) -> str:
    """Extract text from Groq transcription response object/dict."""
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text.strip()
    if isinstance(response, dict):
        raw = response.get("text", "")
        return str(raw).strip() if raw is not None else ""
    return ""


def _transcribe_audio_bytes(audio_bytes: bytes, file_name: str) -> str:
    """Transcribe audio bytes using Groq whisper API."""
    global _groq_audio_client

    if not audio_bytes:
        return ""

    api_key = Config.get_groq_key()
    if not api_key:
        raise RuntimeError(
            "Speech transcription is unavailable: GROQ_API_KEY is missing."
        )

    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError(
            "Speech transcription is unavailable: groq package is not installed."
        ) from exc

    if _groq_audio_client is None:
        _groq_audio_client = Groq(api_key=api_key)

    model = Config.STT_MODEL.strip() or "whisper-large-v3"
    language = Config.STT_LANGUAGE.strip() or "en"
    prompt = Config.STT_PROMPT.strip()
    request_payload = {
        "model": model,
        "file": (file_name, audio_bytes),
        "language": language,
        "temperature": 0.0,
        "response_format": "json",
    }
    if prompt:
        request_payload["prompt"] = prompt

    response = _groq_audio_client.audio.transcriptions.create(**request_payload)
    return _extract_transcript_text(response)


def _normalize_tts_text(text: str) -> str:
    """Normalize text before sending it to neural TTS."""
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    cleaned = cleaned.replace("*", "").replace("`", "")
    return cleaned


def _split_tts_segments(text: str, max_chars: int = 260) -> list[str]:
    """Split long text into sentence-like segments for stable TTS generation."""
    if not text:
        return []
    parts = re.findall(r"[^.!?]+[.!?]?", text) or [text]
    segments: list[str] = []
    current = ""
    for raw in parts:
        sentence = raw.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            segments.append(current)
        if len(sentence) <= max_chars:
            current = sentence
            continue
        for idx in range(0, len(sentence), max_chars):
            chunk = sentence[idx : idx + max_chars].strip()
            if chunk:
                segments.append(chunk)
        current = ""
    if current:
        segments.append(current)
    return segments


async def _synthesize_edge_tts_segment(segment: str) -> bytes:
    """Synthesize one text segment using edge-tts."""
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError(
            "Speech synthesis backend is unavailable: edge-tts is not installed."
        ) from exc

    communicate = edge_tts.Communicate(
        text=segment,
        voice=Config.WEB_TTS_VOICE,
        rate=Config.WEB_TTS_RATE,
        pitch=Config.WEB_TTS_PITCH,
    )
    chunks: list[bytes] = []
    async for packet in communicate.stream():
        if packet.get("type") != "audio":
            continue
        data = packet.get("data")
        if isinstance(data, (bytes, bytearray)):
            chunks.append(bytes(data))
    return b"".join(chunks)


async def _synthesize_text_audio_bytes(text: str) -> bytes:
    """Synthesize normalized text into MP3 bytes."""
    backend = Config.WEB_TTS_BACKEND.strip().lower()
    if backend == "browser":
        raise RuntimeError(
            "Server speech synthesis is disabled by WEB_TTS_BACKEND=browser."
        )

    segments = _split_tts_segments(text)
    if not segments:
        return b""

    audio_parts: list[bytes] = []
    for segment in segments:
        audio = await _synthesize_edge_tts_segment(segment)
        if audio:
            audio_parts.append(audio)
    return b"".join(audio_parts)


def _server_tts_backend_name() -> str:
    """Return user-facing server TTS backend name for health/status APIs."""
    backend = Config.WEB_TTS_BACKEND.strip().lower()
    if backend == "browser":
        return "browser"
    return "edge-tts"


def _strip_phrases(text: str, phrases: list[str]) -> str:
    lowered = text.lower()
    for phrase in phrases:
        lowered = lowered.replace(phrase, "")
    return lowered.strip()


def _contains_any_phrase(text: str, phrases: list[str]) -> bool:
    """Check if any phrase appears in text (case-insensitive)."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _contains_any_word(text: str, words: list[str]) -> bool:
    """Check if any word appears as a full token in text."""
    return any(
        re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE)
        for word in words
    )


def _extract_weather_city(text: str) -> str:
    """Extract likely city name from natural weather phrasing."""
    query = text.lower().strip()
    query = re.sub(r"^(hey|hi|hello)\s+", "", query)

    patterns = [
        r"(?:what(?:'s| is)\s+the\s+)?(?:weather|temperature)(?:\s+like)?\s+(?:in|for|of)\s+(.+)$",
        r"(?:tell me|show me|give me|check)\s+(?:the\s+)?(?:weather|temperature)\s+(?:in|for|of)\s+(.+)$",
        r"(?:weather|temperature)\s+(?:in|for|of)\s+(.+)$",
        r"(?:weather|temperature)\s+(.+)$",
        r"(.+)\s+(?:weather|temperature)$",
    ]

    city = ""
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            city = match.group(1).strip()
            break

    if not city:
        return ""

    return _normalize_city_candidate(city)


def _normalize_city_candidate(text: str) -> str:
    """Normalize noisy city fragments from speech/typed input."""
    tokens = re.findall(r"[a-zA-Z][a-zA-Z\-\.' ]*", (text or "").lower())
    if not tokens:
        return ""

    city_tokens: list[str] = []
    for raw in tokens:
        for token in raw.strip().split():
            clean = token.strip(" .,'")
            if not clean or clean in _CITY_STOPWORDS:
                continue
            city_tokens.append(clean)

    if not city_tokens:
        return ""

    return " ".join(city_tokens[:4]).strip()


def _is_likely_city_candidate(raw_text: str, city_candidate: str) -> bool:
    """Heuristic to reject conversational noise as weather city input."""
    city = (city_candidate or "").strip().lower()
    if not city:
        return False

    tokens = [token.strip(" .,'") for token in city.split() if token.strip(" .,'")]
    if not tokens or len(tokens) > 4:
        return False
    if any(token in _NON_CITY_FOLLOWUP_TOKENS for token in tokens):
        return False
    if len(tokens) == 1 and len(tokens[0]) < 3:
        return False

    raw_tokens = [
        token.strip(" .,'")
        for token in re.findall(r"[a-zA-Z][a-zA-Z\-\.' ]*", (raw_text or "").lower())
    ]
    flattened: list[str] = []
    for part in raw_tokens:
        flattened.extend([word for word in part.split() if word])
    if flattened and all(token in _NON_CITY_FOLLOWUP_TOKENS for token in flattened):
        return False
    return True


def _normalize_news_topic_candidate(text: str) -> str:
    """Normalize possible topic text from natural-language news requests."""
    normalized = re.sub(r"\bbased on\b", " ", (text or "").lower())
    raw_tokens = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-\.'#+]*", normalized)
    tokens = [tok.strip(" .,'!?\"") for tok in raw_tokens]
    if not tokens:
        return ""

    mapped_tokens: list[str] = []
    for token in tokens:
        if token in {"u.s", "u.s.", "usa"}:
            mapped_tokens.append("us")
            continue
        mapped_tokens.append(token)

    topic_tokens: list[str] = []
    for token in mapped_tokens:
        if token.isdigit():
            continue
        if not token or token in _NEWS_TOPIC_STOPWORDS:
            continue
        if token not in topic_tokens:
            topic_tokens.append(token)
    if not topic_tokens:
        return ""
    return " ".join(topic_tokens[:6]).strip()


def _extract_news_topic(text: str) -> str:
    """Extract an optional topic from natural-language news queries."""
    query = (text or "").strip().lower()
    if not query:
        return ""

    patterns = [
        r"(?:news|headlines)\s+(?:about|on|for|regarding)\s+(.+)$",
        r"(?:what(?:'s| is)\s+happening)\s+(?:in|with|on)\s+(.+)$",
        (
            r"(?:give me|tell me|show me)\s+(?:an?\s+)?"
            r"(?:update|updates|latest|current)\s+"
            r"(?:on|about|for|regarding|with)\s+(.+)$"
        ),
        r"(?:update)\s+me\s+(?:on|about|for|regarding|with)\s+(.+)$",
        r"(?:update|updates|latest|current|developments?)\s+(?:on|about|for|regarding|with)\s+(.+)$",
        r"(?:what(?:'s| is)\s+(?:the\s+)?)?(?:latest|current|new)\s+(?:on|about|with)\s+(.+)$",
        (
            r"(?:tell me|show me|give me|get me)\s+(?:the\s+)?"
            r"(?:latest\s+|current\s+)?(?:news|headlines)\s+"
            r"(?:about|on|for|regarding)\s+(.+)$"
        ),
        (
            r"(?:what(?:'s| is)\s+(?:the\s+)?)?"
            r"(?:latest\s+|current\s+)?(?:news|headlines)\s+"
            r"(?:about|on|for|regarding)\s+(.+)$"
        ),
    ]

    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return _normalize_news_topic_candidate(match.group(1))

    if "news" in query or "headlines" in query or "what's happening" in query:
        return _normalize_news_topic_candidate(query)

    return ""


def _is_news_intent(query: str) -> bool:
    """Decide whether a free-form request should route to the news service."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return False

    if _contains_any_word(normalized, list(_NEWS_DIRECT_HINTS)):
        return True

    if _contains_any_word(normalized, list(_NON_NEWS_UPDATE_CONTEXT_WORDS)):
        return False

    update_like = _contains_any_word(normalized, list(_NEWS_UPDATE_HINTS))
    if not update_like:
        return False

    if re.search(
        r"\b(?:update|updates|latest|current|developments?|new)\b.*\b(?:on|about|with|regarding|for)\b",
        normalized,
    ):
        return True

    topic = _extract_news_topic(query)
    return bool(topic)


def _extract_news_followup_topic(query: str) -> str:
    """Extract topic from follow-up conflict questions."""
    direct = _extract_news_topic(query)
    if direct:
        return direct

    candidate = _normalize_news_topic_candidate(query)
    if not candidate:
        return ""

    normalized = query.lower()
    has_conflict_hint = _contains_any_word(normalized, list(_NEWS_CONFLICT_HINTS))
    has_entity_hint = _contains_any_word(normalized, list(_NEWS_ENTITY_HINTS))
    if has_conflict_hint or has_entity_hint:
        return candidate
    return ""


def _extract_headline_reference_index(query: str) -> Optional[int]:
    """Extract a 1-based headline index from follow-up text, if present."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return None

    patterns = [
        r"\bheadline(?:\s+number)?\s*(\d{1,2})\b",
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+headline\b",
        r"\bnumber\s+(\d{1,2})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if not match:
            continue
        try:
            index = int(match.group(1))
        except (TypeError, ValueError):
            continue
        if index >= 1:
            return index
    return None


def _resolve_headline_reference(query: str) -> Optional[tuple[int, str, str]]:
    """Resolve referenced cached headline as (index, title, source)."""
    index = _extract_headline_reference_index(query)
    if not index:
        return None
    items = _extract_headline_items(_last_news_headline_response)
    if not items or index > len(items):
        return None
    title, source = items[index - 1]
    return index, title, source


def _is_topic_specific_news_payload(news_response: str) -> bool:
    """Return True when headlines payload is topic-filtered (not generic fallback)."""
    normalized = (news_response or "").strip().lower()
    return "here are the latest headlines on " in normalized


def _choose_headline_followup_topic(query: str, selected_title: str) -> str:
    """Pick the cleanest topic for a headline-number follow-up."""
    title_topic = _normalize_news_topic_candidate(selected_title)
    explicit_topic = _extract_news_followup_topic(query)
    if not title_topic:
        return explicit_topic
    if not explicit_topic:
        return title_topic

    title_tokens = set(title_topic.split())
    explicit_tokens = set(explicit_topic.split())
    if explicit_tokens and explicit_tokens.issubset(title_tokens):
        return explicit_topic
    return title_topic


def _build_selected_headline_brief(index: int, title: str, source: str) -> str:
    """Generate a concise human brief anchored to one selected headline."""
    clean_title = (title or "").strip()
    clean_source = (source or "").strip()
    if not clean_title:
        return "I could not parse that headline clearly. Please ask again."
    if clean_source:
        return (
            f"Based on headline {index} from {clean_source}: {clean_title}. "
            "That is the key update from this item."
        )
    return f"Based on headline {index}: {clean_title}. That is the key update from this item."


def _wants_headline_deep_dive(query: str) -> bool:
    """Detect requests asking for a deeper explanation of one selected headline."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return False
    if any(
        phrase in normalized
        for phrase in [
            "deep dive",
            "dive deep",
            "more detail",
            "more details",
            "explain headline",
        ]
    ):
        return True
    return _contains_any_word(
        normalized,
        [
            "deep",
            "dip",
            "detail",
            "details",
            "brief",
            "breakdown",
            "summary",
            "summarize",
            "explain",
        ],
    )


def _build_selected_headline_deep_dive(
    query: str, index: int, title: str, source: str
) -> str:
    """Generate a short deep-dive answer grounded in one selected headline."""
    fallback = _build_selected_headline_brief(index, title, source)
    clean_title = (title or "").strip()
    if not clean_title:
        return fallback

    prompt = (
        "You are answering a user who asked for more detail on one specific headline.\n"
        "Use ONLY the headline text below. Do not invent facts or extra background.\n"
        "Write 1-2 plain, direct sentences.\n"
        "If the headline is too limited, say details are limited.\n"
        f"User request: {query}\n"
        f"Headline number: {index}\n"
        f"Headline: {clean_title}\n"
        f"Source: {source or 'unknown'}"
    )
    answer = generate_response(prompt, conversation_history=None).strip()
    return answer or fallback


def _wants_news_refresh(query: str) -> bool:
    """Whether user asks for fresh headlines instead of follow-up clarification."""
    normalized = (query or "").strip().lower()
    return _contains_any_word(
        normalized,
        ["latest", "update", "updates", "current", "news", "headlines", "today", "new"],
    )


def _news_topic_tokens(topic: str) -> set[str]:
    """Normalize a topic string into comparable keyword tokens."""
    normalized = _normalize_news_topic_candidate(topic or "")
    if not normalized:
        return set()
    generic_tokens = {
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
    return {
        token for token in normalized.split() if token and token not in generic_tokens
    }


def _topics_related(current_topic: str, cached_topic: str) -> bool:
    """Return True if two topic strings are likely referring to the same story cluster."""
    if not current_topic and not cached_topic:
        return True
    if current_topic and not cached_topic:
        return False
    if cached_topic and not current_topic:
        return True
    current_tokens = _news_topic_tokens(current_topic)
    cached_tokens = _news_topic_tokens(cached_topic)
    if current_tokens and not cached_tokens:
        return False
    if cached_tokens and not current_tokens:
        return False
    if not current_tokens and not cached_tokens:
        return current_topic.strip().lower() == cached_topic.strip().lower()
    return bool(current_tokens.intersection(cached_tokens))


def _is_news_followup_question(query: str) -> bool:
    """Detect follow-up questions about a recently discussed news topic."""
    if _is_news_intent(query):
        return False
    normalized = (query or "").strip().lower()
    if not normalized:
        return False
    if not (
        _contains_any_word(normalized, ["who", "what", "which", "how"])
        or "?" in normalized
    ):
        return False

    followup_topic = _extract_news_followup_topic(query)
    if followup_topic:
        return True

    if _last_news_headline_response and _contains_any_word(
        normalized,
        list(_NEWS_CONFLICT_HINTS) + ["attacker", "side", "sides", "now", "currently"],
    ):
        return True

    return False


def _extract_context_city_reference(text: str) -> str:
    """Extract a likely city from generic phrasing like 'in Hawassa'."""
    query = (text or "").strip().lower()
    if not query:
        return ""

    patterns = [
        r"\b(?:in|at|for|to)\s+([a-zA-Z][a-zA-Z\-\.' ]*?[a-zA-Z])(?=\s+(?:and|but|so|because|the|weather|temperature)\b|[?.!,]|$)",
        r"\bhere\s+in\s+([a-zA-Z][a-zA-Z\-\.' ]*?[a-zA-Z])(?=\s+(?:and|but|so|because|the|weather|temperature)\b|[?.!,]|$)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, query):
            candidate = _normalize_city_candidate(match.group(1))
            if _is_likely_city_candidate(query, candidate):
                return candidate
    return ""


def _is_weather_status_intent(query: str) -> bool:
    """Detect weather questions that do not explicitly say 'weather'."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return False

    if _contains_any_word(normalized, ["weather", "temperature"]):
        return True

    if any(
        phrase in normalized
        for phrase in [
            "how hot",
            "how cold",
            "how is it now",
            "how's it now",
            "how old is it",
        ]
    ):
        return True

    is_question_like = "?" in normalized or _contains_any_word(
        normalized, ["how", "what", "check", "tell", "can", "could", "please"]
    )
    if not is_question_like:
        return False

    descriptive_words = [
        "hot",
        "cold",
        "warm",
        "humid",
        "rainy",
        "raining",
        "sunny",
        "chilly",
        "comfortable",
        "uncomfortable",
        "uncomfy",
    ]
    if _contains_any_word(normalized, descriptive_words) and _contains_any_word(
        normalized,
        ["how", "is", "it", "that", "now", "today", "here", "feeling", "feel"],
    ):
        return True
    return False


def _resolve_weather_city(query: str, allow_last_city: bool = True) -> str:
    """Resolve the most likely city from weather-related input."""
    extracted = _extract_weather_city(query)
    if extracted and _is_likely_city_candidate(query, extracted):
        return extracted

    context_city = _extract_context_city_reference(query)
    if context_city and _is_likely_city_candidate(query, context_city):
        return context_city

    candidate = _normalize_city_candidate(query)
    if candidate and _is_likely_city_candidate(query, candidate):
        return candidate

    if allow_last_city and _last_weather_city:
        return _last_weather_city

    return ""


def _is_weather_error_response(weather_response: str) -> bool:
    """Return True when weather response is an error/status string."""
    normalized = (weather_response or "").strip().lower()
    if not normalized:
        return True
    return any(
        phrase in normalized
        for phrase in [
            "couldn't get weather",
            "weather feature is unavailable",
            "doesn't look like a valid city",
            "weather service rate limit reached",
            "the weather service is taking too long",
            "couldn't connect to the weather service",
            "i couldn't fetch the weather details",
        ]
    )


def _parse_weather_snapshot(weather_response: str) -> Optional[dict[str, object]]:
    """Parse standard weather response text into structured values."""
    match = re.match(
        (
            r"^\s*(?P<city>[a-zA-Z][a-zA-Z\-\.' ]*?)\s+weather:\s*"
            r"(?P<description>.+?),\s*"
            r"(?P<temp>-?\d+(?:\.\d+)?)°C,\s*"
            r"feels like\s*(?P<feels>-?\d+(?:\.\d+)?)°C\.\s*$"
        ),
        (weather_response or "").strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    city = (match.group("city") or "").strip()
    description = (match.group("description") or "").strip()
    if not city or not description:
        return None

    try:
        temp_c = float(match.group("temp"))
        feels_like_c = float(match.group("feels"))
    except (TypeError, ValueError):
        return None

    return {
        "city": city,
        "description": description,
        "temp_c": temp_c,
        "feels_like_c": feels_like_c,
    }


def _format_celsius(value: float) -> str:
    """Format celsius values compactly for speech output."""
    rounded = round(value, 1)
    if abs(rounded - int(rounded)) < 0.05:
        return str(int(round(rounded)))
    return f"{rounded:.1f}"


def _weather_feel_label(feels_like_c: float) -> str:
    """Convert feels-like temperature to a simple comfort label."""
    if feels_like_c >= 33:
        return "very hot"
    if feels_like_c >= 28:
        return "hot"
    if feels_like_c >= 23:
        return "warm"
    if feels_like_c >= 18:
        return "mild"
    if feels_like_c >= 12:
        return "cool"
    return "cold"


def _wants_weather_detail_response(query: str) -> bool:
    """Return True when user explicitly asks for weather details/numbers."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return False
    if _contains_any_word(
        normalized,
        [
            "detail",
            "details",
            "exact",
            "number",
            "numbers",
            "temperature",
            "temp",
            "degrees",
            "humidity",
            "wind",
            "breakdown",
        ],
    ):
        return True
    return "feels like" in normalized


def _is_weather_comfort_question(query: str) -> bool:
    """Return True for comfort/interpretation weather follow-up questions."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return False
    if _contains_any_word(
        normalized,
        [
            "hot",
            "cold",
            "warm",
            "mild",
            "moderate",
            "comfortable",
            "uncomfortable",
            "uncomfy",
            "sleep",
            "sweaty",
        ],
    ):
        return True
    return any(
        phrase in normalized
        for phrase in [
            "is that why",
            "why am i feeling",
            "why do i feel",
            "what is happening here",
            "what's happening here",
        ]
    )


def _build_human_weather_response(query: str, weather_response: str) -> str:
    """Turn raw weather text into a conversational, intent-aware answer."""
    if _is_weather_error_response(weather_response):
        return weather_response

    snapshot = _parse_weather_snapshot(weather_response)
    if not snapshot:
        return weather_response

    city = str(snapshot["city"]).title()
    description = str(snapshot["description"])
    temp_c = float(snapshot["temp_c"])
    feels_like_c = float(snapshot["feels_like_c"])
    temp_str = _format_celsius(temp_c)
    feels_str = _format_celsius(feels_like_c)
    normalized = (query or "").strip().lower()

    if _is_weather_comfort_question(normalized):
        label = _weather_feel_label(feels_like_c)
        if feels_like_c >= 28:
            comfort_line = "That is genuinely hot."
        elif feels_like_c >= 23:
            comfort_line = (
                "That is warm, and it can feel uncomfortable if the room is stuffy."
            )
        elif feels_like_c >= 18:
            comfort_line = "That is mild, so it is not truly hot."
        else:
            comfort_line = "That is cool, not hot."

        feels_delta = feels_like_c - temp_c
        if feels_delta >= 2:
            explanation = (
                "It feels warmer than the measured temperature, likely due to humidity."
            )
        elif feels_delta <= -2:
            explanation = "It feels cooler than the measured temperature, likely due to rain or wind."
        else:
            explanation = "If you still feel uncomfortable, humidity, poor airflow, or recent sun exposure can make it feel warmer."

        return (
            f"In {city}, it is {description} at {temp_str}°C and feels like {feels_str}°C ({label}). "
            f"{comfort_line} {explanation}"
        )

    if _wants_weather_detail_response(normalized):
        return (
            f"In {city} right now: {description}, {temp_str}°C, "
            f"feels like {feels_str}°C."
        )

    if "happening" in normalized:
        return (
            f"In {city} right now, it is {description} at {temp_str}°C "
            f"and feels like {feels_str}°C."
        )

    return f"{city} is currently {description}, around {temp_str}°C and feels like {feels_str}°C."


def _respond_with_weather(query: str, city: str) -> str:
    """Fetch weather and return a query-aware conversational response."""
    raw_response = get_weather(city)
    return _build_human_weather_response(query, raw_response)


def _wants_news_summary(query: str) -> bool:
    """Return True when the user asks for situational update over plain list."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return False
    if _contains_any_word(normalized, list(_NEWS_LIST_HINTS)):
        return False
    if any(phrase in normalized for phrase in _NEWS_SUMMARY_HINTS):
        return True
    return False


def _wants_news_meta_details(query: str) -> bool:
    """Whether user explicitly asks for confidence/sources transparency lines."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return False
    if _contains_any_word(
        normalized, ["source", "sources", "confidence", "certain", "certainty"]
    ):
        return True
    return "how sure" in normalized or "how reliable" in normalized


def _extract_headline_items(news_response: str) -> list[tuple[str, str]]:
    """Parse numbered headline lines into (title, source) tuples."""
    items: list[tuple[str, str]] = []
    for line in (news_response or "").splitlines():
        match = re.match(r"^\s*\d+\.\s*(.+?)\s*\(([^()]+)\)\s*$", line.strip())
        if not match:
            continue
        title = match.group(1).strip()
        source = match.group(2).strip()
        items.append((title, source))
    return items


def _build_news_confidence_line(headline_items: list[tuple[str, str]]) -> str:
    """Build a confidence+uncertainty line from headline/source coverage."""
    if not headline_items:
        return ""
    source_count = len({source for _, source in headline_items if source})
    headline_count = len(headline_items)

    if headline_count >= 4 and source_count >= 3:
        return (
            "Confidence: medium-high. Multiple outlets are reporting related events, "
            "but details can still change quickly."
        )
    if headline_count >= 3:
        return (
            "Confidence: medium. Coverage is broad enough for a directional update, "
            "but some details may still be uncertain."
        )
    return "Confidence: low-medium. Limited coverage right now, so treat this as an early update."


def _build_news_sources_line(headline_items: list[tuple[str, str]]) -> str:
    """Build a compact sources-used line from unique headline sources."""
    sources: list[str] = []
    for _, source in headline_items:
        clean = source.strip()
        if clean and clean not in sources:
            sources.append(clean)
    if not sources:
        return ""
    return f"Sources used: {'; '.join(sources[:5])}."


def _summarize_news_update(query: str, topic: Optional[str], news_response: str) -> str:
    """Generate a concise, human update grounded in fetched headlines."""
    if not news_response:
        return ""
    lower = news_response.lower()
    if any(
        phrase in lower
        for phrase in [
            "couldn't fetch",
            "no news",
            "rate limit",
            "taking too long",
        ]
    ):
        return news_response

    headline_items = _extract_headline_items(news_response)
    if not headline_items:
        return news_response

    headline_block = "\n".join(
        f"- {title} ({source})" for title, source in headline_items[:5]
    )
    prompt = (
        "You are summarizing live news headlines for a user.\n"
        "Use ONLY the headlines below. Do not invent facts.\n"
        "Give a natural 2-3 sentence update in plain language.\n"
        "If details are unclear or mixed, say so briefly.\n"
        f"User request: {query}\n"
        f"Topic: {topic or 'general'}\n"
        f"Headlines:\n{headline_block}"
    )
    summary = generate_response(prompt, conversation_history=None).strip()
    if not summary:
        return news_response

    if not _wants_news_meta_details(query):
        return summary

    confidence_line = _build_news_confidence_line(headline_items)
    sources_line = _build_news_sources_line(headline_items)
    extra_lines = [line for line in [confidence_line, sources_line] if line]
    if not extra_lines:
        return summary
    return summary + "\n" + "\n".join(extra_lines)


def _answer_news_followup(query: str, topic: Optional[str], news_response: str) -> str:
    """Answer follow-up questions using fetched headlines as the sole evidence."""
    if not news_response:
        return ""
    lower = news_response.lower()
    if any(
        phrase in lower
        for phrase in [
            "couldn't fetch",
            "no news",
            "rate limit",
            "taking too long",
        ]
    ):
        return news_response

    headline_items = _extract_headline_items(news_response)
    if not headline_items:
        return news_response

    headline_block = "\n".join(
        f"- {title} ({source})" for title, source in headline_items[:5]
    )
    prompt = (
        "You are answering a follow-up question about a live conflict update.\n"
        "Use ONLY the headlines provided. Do not invent facts.\n"
        "Answer directly in 1-3 sentences using plain, literal language.\n"
        "Do not use figurative wording or unusual expressions.\n"
        "If the headlines do not clearly identify a side, explicitly say it is unclear.\n"
        "If multiple sides are reported attacking, say that clearly.\n"
        f"User question: {query}\n"
        f"Topic context: {topic or 'general'}\n"
        f"Headlines:\n{headline_block}"
    )
    answer = generate_response(prompt, conversation_history=None).strip()
    if not answer:
        return news_response

    if not _wants_news_meta_details(query):
        return answer

    confidence_line = _build_news_confidence_line(headline_items)
    sources_line = _build_news_sources_line(headline_items)
    extra_lines = [line for line in [confidence_line, sources_line] if line]
    if not extra_lines:
        return answer
    return answer + "\n" + "\n".join(extra_lines)


def process_user_query(user_input: str) -> ChatResponse:
    """Process one user message and return assistant output for web mode."""
    global _pending_weather_city, _last_weather_city, _last_news_topic, _last_news_headline_response

    query = (user_input or "").strip()
    if not query:
        return ChatResponse(response="Please say or type something so I can help.")

    normalized = query.lower()
    memory.add_user_message(query)

    context_city = _extract_context_city_reference(query)
    if context_city and _contains_any_word(
        normalized,
        ["weather", "temperature", "hot", "cold", "humid", "rain", "sunny", "chilly"],
    ):
        _last_weather_city = context_city

    if any(word in normalized for word in ["bye", "goodbye", "exit", "quit", "stop"]):
        _pending_weather_city = False
        _last_weather_city = ""
        _last_news_topic = ""
        _last_news_headline_response = ""
        response = "Goodbye! Talk to you soon!"
        memory.add_assistant_message(response)
        return ChatResponse(response=response, should_exit=True)

    if _pending_weather_city and not any(
        token in normalized
        for token in [
            "weather",
            "temperature",
            "news",
            "headline",
            "latest",
            "update",
            "updates",
            "current",
            "happening",
            "wikipedia",
            "joke",
            "define",
            "calculate",
            "time",
            "date",
            "battery",
            "system",
            "help",
            "clear",
            "history",
            "forget",
            "reset",
            "conversation",
        ]
    ):
        city = _resolve_weather_city(query, allow_last_city=False)
        if city:
            _pending_weather_city = False
            _last_weather_city = city
            response = _respond_with_weather(query, city)
        else:
            response = "Please tell me the city name, for example: Addis Ababa."
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if _is_weather_status_intent(query):
        city = _resolve_weather_city(query, allow_last_city=True)
        if not city:
            _pending_weather_city = True
            response = (
                "Sure, which city should I check? For example: Hawassa or Addis Ababa."
            )
        else:
            _pending_weather_city = False
            _last_weather_city = city
            response = _respond_with_weather(query, city)
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    headline_reference = _resolve_headline_reference(query)
    if headline_reference:
        index, selected_title, selected_source = headline_reference
        topic = _choose_headline_followup_topic(query, selected_title)

        if _wants_headline_deep_dive(query):
            response = _build_selected_headline_deep_dive(
                query,
                index,
                selected_title,
                selected_source,
            )
            memory.add_assistant_message(response)
            return ChatResponse(response=response)

        headline_response = get_top_headlines(topic if topic else None)
        if topic and not _is_topic_specific_news_payload(headline_response):
            response = (
                f"I do not have enough new related headlines right now. "
                f"{_build_selected_headline_brief(index, selected_title, selected_source)}"
            )
        else:
            response = _summarize_news_update(
                query, topic if topic else None, headline_response
            )

        _last_news_topic = topic if topic else _GENERAL_NEWS_TOPIC
        _last_news_headline_response = headline_response
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if _is_news_followup_question(query):
        topic = _extract_news_followup_topic(query) or _last_news_topic
        can_reuse_cached = (
            bool(_last_news_headline_response)
            and not _wants_news_refresh(query)
            and _topics_related(topic, _last_news_topic)
        )
        if can_reuse_cached:
            headline_response = _last_news_headline_response
        else:
            headline_response = get_top_headlines(topic if topic else None)
        response = _answer_news_followup(
            query, topic if topic else None, headline_response
        )
        _last_news_topic = topic if topic else _GENERAL_NEWS_TOPIC
        _last_news_headline_response = headline_response
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(
        p in normalized for p in ["wikipedia", "tell me about", "who is", "what is"]
    ) and not _is_news_intent(query):
        topic = _strip_phrases(
            normalized, ["wikipedia", "tell me about", "who is", "what is"]
        )
        response = (
            get_summary(topic)
            if topic
            else "Please tell me the topic you want to explore."
        )
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if _is_news_intent(query):
        topic = _extract_news_topic(query)
        headline_response = get_top_headlines(topic if topic else None)
        if _wants_news_summary(query):
            response = _summarize_news_update(
                query, topic if topic else None, headline_response
            )
        else:
            response = headline_response
        _last_news_topic = topic if topic else _GENERAL_NEWS_TOPIC
        _last_news_headline_response = headline_response
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(p in normalized for p in ["joke", "make me laugh", "funny"]):
        response = get_joke()
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(
        p in normalized
        for p in ["define", "definition", "meaning of", "dictionary", "what does"]
    ):
        word = _strip_phrases(
            normalized,
            [
                "define the word",
                "definition of",
                "meaning of",
                "dictionary",
                "what does",
                "define",
                "mean",
                "look up",
            ],
        ).split()
        response = (
            get_definition(word[0])
            if word
            else "Tell me the word you want me to define."
        )
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if _contains_any_phrase(normalized, ["divided by"]) or _contains_any_word(
        normalized,
        [
            "calculate",
            "math",
            "plus",
            "minus",
            "times",
            "multiply",
            "add",
            "subtract",
        ],
    ):
        expression = _strip_phrases(
            normalized, ["calculate", "what is", "what's", "compute", "solve", "math"]
        )
        response = (
            calculate(expression)
            if expression
            else "Share the expression you want me to calculate."
        )
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(
        p in normalized for p in ["what time", "current time", "time now", "time is it"]
    ):
        response = get_current_time()
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(
        p in normalized
        for p in ["what date", "today's date", "current date", "what day"]
    ):
        response = get_full_datetime() if "time" in normalized else get_current_date()
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(p in normalized for p in ["battery", "battery status", "power"]):
        response = get_battery_status()
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(
        p in normalized
        for p in ["system info", "system information", "my system", "my computer"]
    ):
        response = get_platform_summary()
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(p in normalized for p in ["clear history", "forget", "reset conversation"]):
        _pending_weather_city = False
        _last_weather_city = ""
        _last_news_topic = ""
        _last_news_headline_response = ""
        memory.clear()
        response = "I cleared our conversation history."
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(p in normalized for p in ["help", "what can you do", "commands"]):
        response = (
            "I can help with weather, Wikipedia, news, jokes, dictionary definitions, "
            "calculations, date/time, system info, battery, and general AI chat."
        )
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    history = memory.get_messages_for_api()
    response = generate_response(query, conversation_history=history)
    memory.add_assistant_message(response)
    return ChatResponse(response=response)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    """Initialize app-wide services for web mode."""
    setup_logging()
    for warning in Config.validate():
        logger.warning(warning)
    logger.info("Miehab web assistant started.")
    yield


app.router.lifespan_context = _lifespan


@app.middleware("http")
async def redirect_unsafe_loopback_host(
    request: Request, call_next
):  # pragma: no cover - exercised via integration-style test
    """Redirect browser requests from 0.0.0.0 to 127.0.0.1 for mic-safe origin."""
    host = (request.url.hostname or "").strip().lower()
    if host == "0.0.0.0":
        port = request.url.port or 8000
        target = str(request.url.replace(netloc=f"127.0.0.1:{port}"))
        return RedirectResponse(url=target, status_code=307)
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.get("/")
def index() -> FileResponse:
    """Serve the main web UI."""
    return FileResponse(_FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Health endpoint for runtime checks."""
    return {
        "status": "ok",
        "assistant": Config.ASSISTANT_NAME,
        "tts_backend": _server_tts_backend_name(),
    }


@app.post("/api/speech/transcribe", response_model=SpeechTranscribeResponse)
def transcribe_audio(payload: SpeechTranscribeRequest) -> SpeechTranscribeResponse:
    """Transcribe browser-recorded audio through Groq whisper."""
    try:
        audio_bytes = _decode_audio_base64(payload.audio_base64)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if len(audio_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio payload too large.")
    if len(audio_bytes) < 1024:
        return SpeechTranscribeResponse(transcript="")

    file_name = _safe_audio_filename(payload.file_name, payload.mime_type)
    try:
        transcript = _transcribe_audio_bytes(audio_bytes, file_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Audio transcription failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail="Speech transcription failed. Please try again.",
        ) from exc

    return SpeechTranscribeResponse(transcript=transcript)


@app.post("/api/speech/synthesize", response_model=SpeechSynthesizeResponse)
async def synthesize_audio(
    payload: SpeechSynthesizeRequest,
) -> SpeechSynthesizeResponse:
    """Synthesize assistant text into speech for the browser to play."""
    text = _normalize_tts_text(payload.text)
    if not text:
        raise HTTPException(status_code=400, detail="Text payload is empty.")
    if len(text) > Config.WEB_TTS_MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Text payload exceeds WEB_TTS_MAX_CHARS ({Config.WEB_TTS_MAX_CHARS}).",
        )

    try:
        audio_bytes = await _synthesize_text_audio_bytes(text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Speech synthesis failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=502, detail="Speech synthesis failed. Please try again."
        ) from exc

    if not audio_bytes:
        raise HTTPException(
            status_code=502, detail="Speech synthesis returned empty audio."
        )

    encoded = base64.b64encode(audio_bytes).decode("ascii")
    return SpeechSynthesizeResponse(
        audio_base64=encoded,
        mime_type="audio/mpeg",
        engine=_server_tts_backend_name(),
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    """Main chat endpoint used by the browser frontend."""
    try:
        return process_user_query(payload.message)
    except Exception as exc:
        logger.error("Web chat failure: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal assistant error") from exc


def main() -> None:
    """Run the web assistant server with Uvicorn."""
    import uvicorn

    uvicorn.run(
        "voice_assistant.web:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
