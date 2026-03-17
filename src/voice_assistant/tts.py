"""
Text-to-Speech module for Voice Assistant.

Provides cross-platform TTS with automatic engine selection:
- Windows: SAPI via win32com (if available)
- All platforms: pyttsx3 fallback
- Headless/Docker: print-only mode (no audio hardware needed)
"""

import sys
import threading
from typing import Optional

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger

logger = get_logger("tts")

# Lock to manage TTS engine concurrency
_engine_lock = threading.Lock()

# TTS backend state
_tts_backend: str = "print"  # "win32" | "pyttsx3" | "print"
_speaker: Optional[object] = None
_voice_id: Optional[str] = None


def _is_text_mode() -> bool:
    """Check if we should use text-only mode (no audio)."""
    mode = Config.INTERACTION_MODE.lower()
    if mode == "text":
        return True
    if mode == "voice":
        return False
    # auto — detect audio availability
    try:
        import pyaudio

        pa = pyaudio.PyAudio()
        count = pa.get_device_count()
        pa.terminate()
        return count == 0
    except Exception:
        return True


def initialize_tts() -> None:
    """
    Initialize the TTS engine based on platform and configuration.

    Order: Windows SAPI → pyttsx3 → print-only fallback.
    """
    global _tts_backend, _speaker, _voice_id

    if _is_text_mode():
        _tts_backend = "print"
        logger.info("TTS initialized: text-only mode (no audio output)")
        return

    # Try Windows SAPI
    if Config.TTS_ENGINE == "auto" and sys.platform == "win32":
        try:
            import win32com.client

            _speaker = win32com.client.Dispatch("SAPI.SpVoice")
            _speaker.Rate = 1
            _speaker.Volume = 100
            _tts_backend = "win32"
            logger.info("TTS initialized: Windows SAPI")
            return
        except Exception as e:
            logger.warning("Windows SAPI unavailable: %s", e)

    # Try pyttsx3
    try:
        import pyttsx3

        driver = "sapi5" if sys.platform == "win32" else None
        temp_engine = pyttsx3.init(driver)
        voices = temp_engine.getProperty("voices")
        if voices:
            male_voice = next(
                (v for v in voices if "david" in v.name.lower()),
                voices[0],
            )
            _voice_id = male_voice.id
            logger.info("TTS voice selected: %s", male_voice.name)
        temp_engine.stop()
        del temp_engine
        _tts_backend = "pyttsx3"
        logger.info("TTS initialized: pyttsx3")
        return
    except Exception as e:
        logger.warning("pyttsx3 unavailable: %s. Using print-only mode.", e)

    # Final fallback: print only
    _tts_backend = "print"
    logger.info("TTS initialized: text-only mode (audio engines unavailable)")


def speak(text: str) -> None:
    """
    Output text — via TTS engine (voice mode) or print (text mode).

    Args:
        text: The text to speak/display.
    """
    if _tts_backend == "print":
        print(f"🤖 Miehab: {text}")
        return

    logger.debug("Speaking: %s", text[:80])

    with _engine_lock:
        try:
            if _tts_backend == "win32" and _speaker is not None:
                _speaker.Speak(text, 0)
            elif _tts_backend == "pyttsx3":
                _speak_pyttsx3(text)
        except Exception as e:
            logger.warning("TTS engine failed, falling back to print: %s", e)
            print(f"🤖 Miehab: {text}")


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
