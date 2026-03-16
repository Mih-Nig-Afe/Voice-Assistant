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

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # TTS
    TTS_ENGINE: str = os.getenv("TTS_ENGINE", "auto")
    TTS_RATE: int = int(os.getenv("TTS_RATE", "160"))
    TTS_VOLUME: float = float(os.getenv("TTS_VOLUME", "1.0"))

    # Speech recognition
    LISTEN_TIMEOUT: int = int(os.getenv("LISTEN_TIMEOUT", "8"))
    PHRASE_TIME_LIMIT: int = int(os.getenv("PHRASE_TIME_LIMIT", "12"))

    # AI
    AI_MODEL: str = os.getenv("AI_MODEL", "EleutherAI/gpt-neo-125M")
    AI_MAX_LENGTH: int = int(os.getenv("AI_MAX_LENGTH", "100"))

    # Weather
    WEATHER_API_URL: str = "https://api.openweathermap.org/data/2.5/weather"
    WEATHER_UNITS: str = os.getenv("WEATHER_UNITS", "metric")

    # Wikipedia
    WIKI_LANGUAGE: str = os.getenv("WIKI_LANGUAGE", "en")
    WIKI_SENTENCES: int = int(os.getenv("WIKI_SENTENCES", "7"))

    # Assistant
    ASSISTANT_NAME: str = os.getenv("ASSISTANT_NAME", "Miehab")

    @classmethod
    def validate(cls) -> list[str]:
        """Validate configuration and return list of warnings."""
        warnings: list[str] = []
        if not cls.OPENWEATHER_API_KEY:
            warnings.append(
                "OPENWEATHER_API_KEY not set. Weather feature will be unavailable."
            )
        if not cls.START_BEEP.exists():
            warnings.append(f"Start beep file not found: {cls.START_BEEP}")
        if not cls.STOP_BEEP.exists():
            warnings.append(f"Stop beep file not found: {cls.STOP_BEEP}")
        return warnings

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Return API key or None if not configured."""
        key = cls.OPENWEATHER_API_KEY
        return key if key and key != "your_api_key_here" else None

