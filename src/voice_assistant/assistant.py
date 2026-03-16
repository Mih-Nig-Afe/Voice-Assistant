"""
Main Assistant orchestrator for Voice Assistant (Miehab).

Ties together all modules: speech recognition, TTS, AI generation,
weather, Wikipedia, and command routing into the main interaction loop.
"""

from voice_assistant import commands
from voice_assistant.ai_engine import generate_response
from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger, setup_logging
from voice_assistant.speech import listen
from voice_assistant.tts import initialize_tts, speak
from voice_assistant.weather import get_weather
from voice_assistant.wiki import get_summary

logger = get_logger("assistant")


# ── Register built-in commands ──────────────────────────────────────


@commands.register(["bye", "goodbye", "exit", "quit"], "Exit the assistant")
def _cmd_exit(user_input: str) -> str:
    """Handle exit commands."""
    return "__EXIT__"


@commands.register(["weather"], "Get current weather for a city")
def _cmd_weather(user_input: str) -> str:
    """Handle weather queries."""
    speak("Which city should I check?")
    city = listen()
    if city:
        return get_weather(city)
    return "I couldn't understand the city name. Please try again."


@commands.register(
    ["wikipedia", "tell me about", "who is", "what is"],
    "Search Wikipedia for a topic",
)
def _cmd_wikipedia(user_input: str) -> str:
    """Handle Wikipedia queries."""
    # Strip known trigger phrases to extract the topic
    topic = user_input.lower()
    for phrase in ["wikipedia", "tell me about", "who is", "what is"]:
        topic = topic.replace(phrase, "")
    topic = topic.strip()

    if not topic:
        return "Please specify a topic for me to search."

    speak(f"Searching Wikipedia for {topic}...")
    return get_summary(topic)


# ── Main loop ───────────────────────────────────────────────────────


def run() -> None:
    """Run the main assistant interaction loop."""
    # Startup
    setup_logging()
    initialize_tts()

    # Validate config
    warnings = Config.validate()
    for warning in warnings:
        logger.warning(warning)

    name = Config.ASSISTANT_NAME
    greeting = f"Hi, I'm {name}, your personal voice assistant. How can I help you today?"
    logger.info(greeting)
    speak(greeting)

    while True:
        user_query = listen()

        if not user_query:
            continue

        # Try to route to a registered command
        handler, keyword = commands.route(user_query)

        if handler is not None:
            response = handler(user_query)
            if response == "__EXIT__":
                farewell = "Goodbye! Talk to you soon!"
                logger.info(farewell)
                speak(farewell)
                break
            logger.info("Response: %s", response[:100] if response else "")
            speak(response)
        else:
            # Default: AI-generated response
            speak("Thinking...")
            response = generate_response(user_query)
            logger.info("AI response: %s", response[:100])
            speak(response)

        # Prompt for continued interaction
        speak("Do you need help with anything else?")


def main() -> None:
    """Entry point for the voice assistant."""
    try:
        run()
    except KeyboardInterrupt:
        logger.info("Assistant interrupted by user.")
        speak("Goodbye!")
    except Exception as e:
        logger.critical("Unexpected error: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    main()

