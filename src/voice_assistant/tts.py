"""
Text-to-Speech module for Voice Assistant.

Provides cross-platform TTS with automatic engine selection:
- Windows: SAPI via win32com (if available)
- All platforms: pyttsx3 fallback
"""

import sys
import threading
from typing import Optional

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger

logger = get_logger("tts")

# Lock to manage TTS engine concurrency
_engine_lock = threading.Lock()

# Platform-specific TTS state
_use_win32: bool = False
_speaker: Optional[object] = None
_voice_id: Optional[str] = None


def initialize_tts() -> None:
    """
    Initialize the TTS engine based on platform and configuration.

    Tries Windows SAPI first (on Windows), then falls back to pyttsx3.
    """
    global _use_win32, _speaker, _voice_id

    if Config.TTS_ENGINE == "auto" and sys.platform == "win32":
        try:
            import win32com.client
            _speaker = win32com.client.Dispatch("SAPI.SpVoice")
            _speaker.Rate = 1
            _speaker.Volume = 100
            _use_win32 = True
            logger.info("TTS initialized: Windows SAPI")
            return
        except Exception as e:
            logger.warning("Windows SAPI unavailable: %s. Falling back to pyttsx3.", e)

    # Fallback: pyttsx3
    try:
        import pyttsx3
        driver = "sapi5" if sys.platform == "win32" else None
        temp_engine = pyttsx3.init(driver)
        voices = temp_engine.getProperty("voices")
        if voices:
            # Prefer a male voice if available
            male_voice = next(
                (v for v in voices if "david" in v.name.lower()),
                voices[0],
            )
            _voice_id = male_voice.id
            logger.info("TTS voice selected: %s", male_voice.name)
        del temp_engine
    except Exception as e:
        logger.error("Failed to initialize pyttsx3: %s", e)
        _voice_id = None

    _use_win32 = False
    logger.info("TTS initialized: pyttsx3")


def speak(text: str) -> None:
    """
    Convert text to speech using the initialized TTS engine.

    Args:
        text: The text to speak aloud.
    """
    logger.debug("Speaking: %s", text[:80])

    with _engine_lock:
        try:
            if _use_win32 and _speaker is not None:
                _speaker.Speak(text, 0)
                logger.debug("Speech completed (WIN32 SAPI)")
            else:
                _speak_pyttsx3(text)
        except Exception as e:
            logger.error("TTS error: %s", e, exc_info=True)


def _speak_pyttsx3(text: str) -> None:
    """Speak text using pyttsx3 engine."""
    import pyttsx3

    driver = "sapi5" if sys.platform == "win32" else None
    engine = pyttsx3.init(driver)
    engine.setProperty("rate", Config.TTS_RATE)
    engine.setProperty("volume", Config.TTS_VOLUME)
    if _voice_id:
        engine.setProperty("voice", _voice_id)
    engine.say(text)
    engine.runAndWait()
    engine.stop()
    logger.debug("Speech completed (pyttsx3)")

