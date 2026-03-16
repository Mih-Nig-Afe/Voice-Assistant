"""
Speech Recognition module for Voice Assistant.

Handles microphone input, ambient noise adjustment, and speech-to-text
conversion using Google's speech recognition API.
"""

import os
from typing import Optional

import speech_recognition as sr

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger
from voice_assistant.tts import speak

logger = get_logger("speech")


def play_beep(start: bool = True) -> None:
    """
    Play a beep sound to indicate listening state.

    Args:
        start: If True, play the start-listening beep. Otherwise, play stop beep.
    """
    beep_file = str(Config.START_BEEP if start else Config.STOP_BEEP)
    if os.path.exists(beep_file):
        try:
            from playsound3 import playsound
            playsound(beep_file)
        except Exception as e:
            logger.warning("Could not play beep %s: %s", beep_file, e)
    else:
        logger.debug("Beep file not found: %s", beep_file)


def listen() -> Optional[str]:
    """
    Listen for speech input from the microphone and return recognized text.

    Returns:
        Recognized speech as a string, or None if recognition failed.
    """
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
            msg = "Sorry, I didn't catch that. Could you repeat?"
            logger.warning(msg)
            speak(msg)
            return None

        except sr.RequestError:
            play_beep(start=False)
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
            logger.error("Speech recognition error: %s", e, exc_info=True)
            speak("Something went wrong. Could you try again?")
            return None

