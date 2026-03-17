"""Speech recognition and input-mode handling for the assistant."""

from __future__ import annotations

import os
import select
import sys
from typing import Optional

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger
from voice_assistant.runtime import choose_interaction_mode

logger = get_logger("speech")

_mode: Optional[str] = None
_recognizer = None
_microphone = None


def initialize_input() -> str:
    """Initialize input subsystem and return resolved mode (voice/text)."""
    global _mode, _recognizer, _microphone
    if _mode is not None:
        return _mode

    _mode = choose_interaction_mode()
    if _mode == "text":
        logger.info("Input mode initialized: text")
        return _mode

    try:
        import speech_recognition as sr  # type: ignore[import-not-found]

        _recognizer = sr.Recognizer()
        _microphone = sr.Microphone()
        logger.info("Input mode initialized: voice")
        return _mode
    except OSError as exc:
        logger.error(
            "Microphone unavailable. Please allow microphone access in OS privacy settings: %s",
            exc,
        )
        _mode = "text"
    except Exception as exc:
        logger.error("Voice input initialization failed: %s", exc, exc_info=True)
        _mode = "text"

    logger.info("Falling back to text input mode.")
    return _mode


def is_text_mode() -> bool:
    """Return True when runtime input mode is text."""
    return initialize_input() == "text"


def play_beep(start: bool = True) -> None:
    """
    Play a beep sound to indicate listening state.

    Skipped in text mode.

    Args:
        start: If True, play the start-listening beep. Otherwise, play stop beep.
    """
    if is_text_mode():
        return

    beep_file = str(Config.START_BEEP if start else Config.STOP_BEEP)
    if os.path.exists(beep_file):
        try:
            from playsound3 import playsound  # type: ignore[import-not-found]

            playsound(beep_file)
        except Exception as e:
            logger.warning("Could not play beep %s: %s", beep_file, e)
    else:
        logger.debug("Beep file not found: %s", beep_file)


def _listen_text() -> Optional[str]:
    """Get input from stdin (text mode).

    Raises KeyboardInterrupt on EOF to cleanly shut down the assistant.
    """
    try:
        if sys.stdin.closed:
            raise KeyboardInterrupt

        if not sys.stdin.isatty():
            readable, _, _ = select.select([sys.stdin], [], [], 0.2)
            if not readable:
                logger.error(
                    "No interactive stdin detected. Start with 'docker run -it ...' or 'docker compose run --rm miehab'."
                )
                raise KeyboardInterrupt

        user_input = input("You: ").strip()
        if user_input:
            logger.info("Text input: %s", user_input)
            return user_input
        return None
    except EOFError:
        logger.info("EOF received — shutting down.")
        raise KeyboardInterrupt


def _listen_voice() -> Optional[str]:
    """Get input from microphone (voice mode)."""
    import speech_recognition as sr  # type: ignore[import-not-found]

    if _recognizer is None or _microphone is None:
        initialize_input()
    if _recognizer is None or _microphone is None:
        return None

    with _microphone as source:
        _recognizer.adjust_for_ambient_noise(source, duration=0.8)
        logger.info("Listening for speech...")
        play_beep(start=True)

        try:
            audio = _recognizer.listen(
                source,
                timeout=Config.LISTEN_TIMEOUT,
                phrase_time_limit=Config.PHRASE_TIME_LIMIT,
            )
            play_beep(start=False)
            logger.info("Processing speech recognition request...")
            query = _recognizer.recognize_google(audio)
            logger.info("Recognized: %s", query)
            return query

        except sr.UnknownValueError:
            play_beep(start=False)
            from voice_assistant.tts import speak

            speak("I did not catch that. Please repeat.")
            return None
        except sr.RequestError as exc:
            play_beep(start=False)
            from voice_assistant.tts import speak

            logger.error("Speech recognition network issue: %s", exc)
            speak("Speech service is unavailable right now. Please check your network.")
            return None
        except sr.WaitTimeoutError:
            play_beep(start=False)
            logger.debug("Listen timeout with no detected speech.")
            return None
        except Exception as exc:
            play_beep(start=False)
            from voice_assistant.tts import speak

            logger.error("Speech recognition failed: %s", exc, exc_info=True)
            speak("There was a microphone problem. Please try again.")
            return None


def listen() -> Optional[str]:
    """
    Get user input — via microphone (voice mode) or keyboard (text mode).

    Automatically selects the right input method based on config
    and hardware availability.

    Returns:
        User input as a string, or None if input failed.
    """
    if is_text_mode():
        return _listen_text()
    return _listen_voice()


def shutdown_input() -> None:
    """Release speech resources during graceful shutdown."""
    global _microphone
    if _microphone is not None:
        logger.debug("Releasing microphone resources.")
    _microphone = None
