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
_groq_audio_client = None


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
        raise RuntimeError("Speech transcription is unavailable: GROQ_API_KEY is missing.")

    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError(
            "Speech transcription is unavailable: groq package is not installed."
        ) from exc

    if _groq_audio_client is None:
        _groq_audio_client = Groq(api_key=api_key)

    response = _groq_audio_client.audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=(file_name, audio_bytes),
        language="en",
        temperature=0.0,
        response_format="json",
    )
    return _extract_transcript_text(response)


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

    city = re.sub(
        r"^(please|kindly|the|a|an|city of|city)\s+",
        "",
        city,
    )
    city = re.sub(r"^(is\s+)?(in|for|of)\s+", "", city)
    city = re.sub(
        r"\s+(today|now|right now|currently|please|for today|at the moment)$",
        "",
        city,
    )
    city = re.sub(r"[^a-zA-Z\s\-\.' ]", "", city).strip()
    return city


def process_user_query(user_input: str) -> ChatResponse:
    """Process one user message and return assistant output for web mode."""
    global _pending_weather_city

    query = (user_input or "").strip()
    if not query:
        return ChatResponse(response="Please say or type something so I can help.")

    normalized = query.lower()
    memory.add_user_message(query)

    if any(word in normalized for word in ["bye", "goodbye", "exit", "quit", "stop"]):
        _pending_weather_city = False
        response = "Goodbye! Talk to you soon!"
        memory.add_assistant_message(response)
        return ChatResponse(response=response, should_exit=True)

    if _pending_weather_city and not any(
        token in normalized
        for token in [
            "weather",
            "temperature",
            "news",
            "wikipedia",
            "joke",
            "define",
            "calculate",
            "time",
            "date",
            "battery",
            "system",
            "help",
        ]
    ):
        _pending_weather_city = False
        response = get_weather(query)
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if _contains_any_word(normalized, ["weather", "temperature"]):
        city = _extract_weather_city(query)
        if not city:
            _pending_weather_city = True
            response = (
                "Sure, which city should I check? For example: Hawassa or Addis Ababa."
            )
        else:
            _pending_weather_city = False
            response = get_weather(city)
        memory.add_assistant_message(response)
        return ChatResponse(response=response)

    if any(
        p in normalized for p in ["wikipedia", "tell me about", "who is", "what is"]
    ):
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

    if (
        "news" in normalized
        or "headlines" in normalized
        or "what's happening" in normalized
    ):
        topic = _strip_phrases(
            normalized,
            [
                "news about",
                "news on",
                "headlines about",
                "latest news about",
                "what's happening in",
                "what's happening with",
                "latest news",
                "what's happening",
                "news",
                "headlines",
            ],
        )
        response = get_top_headlines(topic if topic else None)
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
    return await call_next(request)


@app.get("/")
def index() -> FileResponse:
    """Serve the main web UI."""
    return FileResponse(_FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Health endpoint for runtime checks."""
    return {"status": "ok", "assistant": Config.ASSISTANT_NAME}


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
