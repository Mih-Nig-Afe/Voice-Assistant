"""
Configuration management for Voice Assistant.

Loads settings from environment variables (.env file) and YAML config,
with sensible defaults for all values.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Config:
    """Centralized configuration with environment variable overrides."""

    # Project paths
    PROJECT_ROOT: Path = _PROJECT_ROOT
    SOUNDS_DIR: Path = _PROJECT_ROOT / "sounds"

    # Sound files
    START_BEEP: Path = SOUNDS_DIR / "start_beep.wav"
    STOP_BEEP: Path = SOUNDS_DIR / "stop_beep.wav"

    # API Keys
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GNEWS_API_KEY: str = os.getenv("GNEWS_API_KEY", "")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Networking
    HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "10"))
    HTTP_CONNECT_TIMEOUT: float = float(os.getenv("HTTP_CONNECT_TIMEOUT", "5"))

    # TTS
    TTS_ENGINE: str = os.getenv("TTS_ENGINE", "auto")
    TTS_RATE: int = int(os.getenv("TTS_RATE", "160"))
    TTS_VOLUME: float = float(os.getenv("TTS_VOLUME", "1.0"))
    WEB_TTS_BACKEND: str = os.getenv("WEB_TTS_BACKEND", "edge")
    WEB_TTS_VOICE: str = os.getenv("WEB_TTS_VOICE", "en-US-AvaMultilingualNeural")
    WEB_TTS_RATE: str = os.getenv("WEB_TTS_RATE", "+0%")
    WEB_TTS_PITCH: str = os.getenv("WEB_TTS_PITCH", "+0Hz")
    WEB_TTS_MAX_CHARS: int = int(os.getenv("WEB_TTS_MAX_CHARS", "900"))

    # Speech recognition
    LISTEN_TIMEOUT: int = int(os.getenv("LISTEN_TIMEOUT", "8"))
    PHRASE_TIME_LIMIT: int = int(os.getenv("PHRASE_TIME_LIMIT", "12"))
    STT_MODEL: str = os.getenv("STT_MODEL", "whisper-large-v3")
    STT_LANGUAGE: str = os.getenv("STT_LANGUAGE", "en")
    STT_PROMPT: str = os.getenv(
        "STT_PROMPT",
        (
            "Transcribe spoken assistant requests clearly. "
            "Common city names may include Addis Ababa, Hawassa, Shashamane, "
            "Adama, Dire Dawa, Bahir Dar, Gode, and Jijiga. "
            "Common world-news terms may include Iran, Israel, US, and USA."
        ),
    )

    # AI — Groq free API (primary), HuggingFace GPT-Neo (fallback)
    AI_BACKEND: str = os.getenv("AI_BACKEND", "groq")  # groq | huggingface
    AI_MODEL: str = os.getenv("AI_MODEL", "openai/gpt-oss-120b")
    AI_MODEL_FALLBACKS: str = os.getenv(
        "AI_MODEL_FALLBACKS",
        "openai/gpt-oss-20b,llama-3.3-70b-versatile,qwen/qwen3-32b",
    )
    AI_MAX_LENGTH: int = int(os.getenv("AI_MAX_LENGTH", "150"))
    AI_MAX_HISTORY: int = int(os.getenv("AI_MAX_HISTORY", "20"))

    # Weather
    WEATHER_API_URL: str = "https://api.openweathermap.org/data/2.5/weather"
    WEATHER_UNITS: str = os.getenv("WEATHER_UNITS", "metric")

    # Wikipedia
    WIKI_LANGUAGE: str = os.getenv("WIKI_LANGUAGE", "en")
    WIKI_SENTENCES: int = int(os.getenv("WIKI_SENTENCES", "7"))

    # Assistant
    ASSISTANT_NAME: str = os.getenv("ASSISTANT_NAME", "Miehab")

    # Interaction mode: voice (mic+speaker), text (stdin/stdout)
    # Auto-detected if not set: uses "text" when no audio device is available
    INTERACTION_MODE: str = os.getenv("INTERACTION_MODE", "auto")

    # Runtime behavior
    REQUIRE_GROQ_API_KEY: bool = (
        os.getenv("REQUIRE_GROQ_API_KEY", "false").strip().lower() == "true"
    )
    FAIL_IF_VOICE_UNAVAILABLE: bool = (
        os.getenv("FAIL_IF_VOICE_UNAVAILABLE", "true").strip().lower() == "true"
    )

    _PLACEHOLDER_MARKERS: tuple[str, ...] = (
        "your_",
        "rotate_me",
        "replace_me",
        "changeme",
        "paste_new",
        "example",
    )

    @classmethod
    def _is_valid_secret(cls, value: str) -> bool:
        """Return True when a secret looks configured and not placeholder text."""
        if not value:
            return False
        clean = value.strip()
        if not clean:
            return False
        lower = clean.lower()
        if any(marker in lower for marker in cls._PLACEHOLDER_MARKERS):
            return False
        return True

    @classmethod
    def validate_required_secrets(cls) -> list[str]:
        """Return blocking configuration errors for required secrets."""
        errors: list[str] = []
        groq_required = cls.AI_BACKEND == "groq" or cls.REQUIRE_GROQ_API_KEY
        if groq_required and not cls._is_valid_secret(cls.GROQ_API_KEY):
            errors.append(
                "GROQ_API_KEY is required but missing/placeholder. Rotate and set a real key in .env."
            )
        return errors

    @classmethod
    def validate(cls) -> list[str]:
        """Validate configuration and return list of warnings."""
        warnings: list[str] = []

        if cls.INTERACTION_MODE.lower() not in {"auto", "voice", "text"}:
            warnings.append(
                "INTERACTION_MODE must be one of: auto, voice, text. Falling back to auto."
            )

        web_tts_backend = cls.WEB_TTS_BACKEND.strip().lower()
        if web_tts_backend not in {"edge", "browser", "auto"}:
            warnings.append(
                "WEB_TTS_BACKEND must be one of: edge, browser, auto. Falling back to edge."
            )
            cls.WEB_TTS_BACKEND = "edge"
        if cls.WEB_TTS_MAX_CHARS < 200:
            warnings.append(
                "WEB_TTS_MAX_CHARS must be at least 200. Falling back to 900."
            )
            cls.WEB_TTS_MAX_CHARS = 900

        if cls.HTTP_TIMEOUT <= 0:
            warnings.append("HTTP_TIMEOUT must be > 0. Falling back to 10 seconds.")
            cls.HTTP_TIMEOUT = 10.0
        if cls.HTTP_CONNECT_TIMEOUT <= 0:
            warnings.append(
                "HTTP_CONNECT_TIMEOUT must be > 0. Falling back to 5 seconds."
            )
            cls.HTTP_CONNECT_TIMEOUT = 5.0

        if cls.LISTEN_TIMEOUT <= 0:
            warnings.append("LISTEN_TIMEOUT must be > 0. Falling back to 8 seconds.")
            cls.LISTEN_TIMEOUT = 8
        if cls.PHRASE_TIME_LIMIT <= 0:
            warnings.append(
                "PHRASE_TIME_LIMIT must be > 0. Falling back to 12 seconds."
            )
            cls.PHRASE_TIME_LIMIT = 12
        if cls.STT_MODEL.strip() not in {"whisper-large-v3", "whisper-large-v3-turbo"}:
            warnings.append(
                "STT_MODEL must be whisper-large-v3 or whisper-large-v3-turbo. Falling back to whisper-large-v3."
            )
            cls.STT_MODEL = "whisper-large-v3"
        if not cls.STT_LANGUAGE.strip():
            warnings.append("STT_LANGUAGE is empty. Falling back to 'en'.")
            cls.STT_LANGUAGE = "en"

        if not cls._is_valid_secret(cls.OPENWEATHER_API_KEY):
            warnings.append(
                "OPENWEATHER_API_KEY not set. Weather feature will be unavailable."
            )
        if not cls._is_valid_secret(cls.GROQ_API_KEY) and cls.AI_BACKEND == "groq":
            if cls.REQUIRE_GROQ_API_KEY:
                warnings.append(
                    "GROQ_API_KEY is required but missing. AI conversation will be unavailable."
                )
            else:
                warnings.append(
                    "GROQ_API_KEY not set. AI will fall back to local HuggingFace model."
                )
        if not cls._is_valid_secret(cls.GNEWS_API_KEY):
            warnings.append(
                "GNEWS_API_KEY not set. News will use Google News RSS fallback."
            )
        if not cls.START_BEEP.exists():
            warnings.append(f"Start beep file not found: {cls.START_BEEP}")
        if not cls.STOP_BEEP.exists():
            warnings.append(f"Stop beep file not found: {cls.STOP_BEEP}")
        return warnings

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Return OpenWeather API key or None if not configured."""
        key = cls.OPENWEATHER_API_KEY
        return key if cls._is_valid_secret(key) else None

    @classmethod
    def get_groq_key(cls) -> Optional[str]:
        """Return Groq API key or None if not configured."""
        key = cls.GROQ_API_KEY
        return key if cls._is_valid_secret(key) else None
