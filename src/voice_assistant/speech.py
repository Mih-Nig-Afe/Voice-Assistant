"""
Speech Recognition module for Voice Assistant.

Handles microphone input, ambient noise adjustment, and speech-to-text
conversion using Google's speech recognition API.

Supports text mode (stdin) for headless/Docker environments.
"""

import os
import sys
from typing import Optional

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger

logger = get_logger("speech")

# Whether we're in text input mode (set during first call)
_text_mode: Optional[bool] = None


def _is_text_mode() -> bool:
    """Determine if we should use text input instead of microphone."""
    global _text_mode
    if _text_mode is not None:
        return _text_mode

    mode = Config.INTERACTION_MODE.lower()
    if mode == "text":
        _text_mode = True
    elif mode == "voice":
        _text_mode = False
    else:
        # Auto-detect: try to check for audio devices
        try:
            import pyaudio

            pa = pyaudio.PyAudio()
            count = pa.get_device_count()
            has_input = any(
                pa.get_device_info_by_index(i).get("maxInputChannels", 0) > 0
                for i in range(count)
            )
            pa.terminate()
            _text_mode = not has_input
        except Exception:
            _text_mode = True

    if _text_mode:
        logger.info("Input mode: text (keyboard)")
    else:
        logger.info("Input mode: voice (microphone)")
    return _text_mode


def play_beep(start: bool = True) -> None:
    """
    Play a beep sound to indicate listening state.

    Skipped in text mode.

    Args:
        start: If True, play the start-listening beep. Otherwise, play stop beep.
    """
    if _is_text_mode():
        return

    beep_file = str(Config.START_BEEP if start else Config.STOP_BEEP)
    if os.path.exists(beep_file):
        try:
            from playsound3 import playsound

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
        user_input = input("🎤 You: ").strip()
        if user_input:
            logger.info("Text input: %s", user_input)
            return user_input
        return None
    except EOFError:
        logger.info("EOF received — shutting down.")
        raise KeyboardInterrupt


def _listen_voice() -> Optional[str]:
    """Get input from microphone (voice mode)."""
    import speech_recognition as sr

    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source)
        logger.info("Listening...")
        play_beep(start=True)

        try:
            audio = recognizer.listen(
                source,
                timeout=Config.LISTEN_TIMEOUT,
                phrase_time_limit=Config.PHRASE_TIME_LIMIT,
            )
            play_beep(start=False)
            logger.info("Processing speech...")
            query = recognizer.recognize_google(audio)
            logger.info("Recognized: %s", query)
            return query

        except sr.UnknownValueError:
            play_beep(start=False)
            from voice_assistant.tts import speak

            msg = "Sorry, I didn't catch that. Could you repeat?"
            logger.warning(msg)
            speak(msg)
            return None

        except sr.RequestError:
            play_beep(start=False)
            from voice_assistant.tts import speak

            msg = "There seems to be an internet issue. Please check your connection."
            logger.error(msg)
            speak(msg)
            return None

        except sr.WaitTimeoutError:
            play_beep(start=False)
            logger.info("Listen timeout — no speech detected.")
            return None

        except Exception as e:
            play_beep(start=False)
            from voice_assistant.tts import speak

            logger.error("Speech recognition error: %s", e, exc_info=True)
            speak("Something went wrong. Could you try again?")
            return None


def listen() -> Optional[str]:
    """
    Get user input — via microphone (voice mode) or keyboard (text mode).

    Automatically selects the right input method based on config
    and hardware availability.

    Returns:
        User input as a string, or None if input failed.
    """
    if _is_text_mode():
        return _listen_text()
    return _listen_voice()
