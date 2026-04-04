"""
Main Assistant orchestrator for Voice Assistant (Miehab).

Ties together all modules: speech recognition, TTS, AI generation,
weather, Wikipedia, news, jokes, dictionary, calculator, datetime,
system info, and command routing into the main interaction loop.

Includes graceful shutdown via signal handlers and conversation memory.
"""

import signal
from contextlib import suppress

from voice_assistant import commands
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
from voice_assistant.runtime import close_http_session, detect_interaction_capabilities
from voice_assistant.speech import (
    initialize_input,
    is_text_mode,
    listen,
    shutdown_input,
)
from voice_assistant.system_info import (
    get_battery_status,
    get_platform_summary,
)
from voice_assistant.tts import initialize_tts, shutdown_tts, speak
from voice_assistant.weather import get_weather
from voice_assistant.wiki import get_summary

logger = get_logger("assistant")

# Flag for graceful shutdown
_running: bool = True


# ── Signal Handlers ─────────────────────────────────────────────────


def _handle_shutdown(signum: int, frame: object) -> None:
    """Handle shutdown signals (SIGINT, SIGTERM) gracefully."""
    global _running
    sig_name = signal.Signals(signum).name
    logger.info("Received %s — shutting down gracefully...", sig_name)
    _running = False


# ── Register built-in commands ──────────────────────────────────────


@commands.register(["bye", "goodbye", "exit", "quit", "stop"], "Exit the assistant")
def _cmd_exit(user_input: str) -> str:
    """Handle exit commands."""
    return "__EXIT__"


@commands.register(["weather", "temperature"], "Get current weather for a city")
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
    topic = user_input.lower()
    for phrase in ["wikipedia", "tell me about", "who is", "what is"]:
        topic = topic.replace(phrase, "")
    topic = topic.strip()
    if not topic:
        return "Please specify a topic for me to search."
    speak(f"Searching Wikipedia for {topic}...")
    return get_summary(topic)


@commands.register(
    ["latest news", "what's happening", "headlines", "news"],
    "Get latest news headlines",
)
def _cmd_news(user_input: str) -> str:
    """Handle news queries."""
    topic = user_input.lower()
    for phrase in [
        "news about",
        "news on",
        "headlines about",
        "latest news about",
        "what's happening in",
        "what's happening with",
        "news",
        "headlines",
        "latest news",
        "what's happening",
    ]:
        topic = topic.replace(phrase, "")
    topic = topic.strip()
    return get_top_headlines(topic if topic else None)


@commands.register(
    ["joke", "tell me a joke", "make me laugh", "funny"],
    "Tell a random joke",
)
def _cmd_joke(user_input: str) -> str:
    """Handle joke requests."""
    return get_joke()


@commands.register(
    ["define", "definition", "meaning of", "what does", "dictionary"],
    "Look up a word definition",
)
def _cmd_dictionary(user_input: str) -> str:
    """Handle dictionary lookups."""
    word = user_input.lower()
    for phrase in [
        "define the word",
        "define",
        "definition of",
        "meaning of",
        "what does",
        "mean",
        "dictionary",
        "look up",
    ]:
        word = word.replace(phrase, "")
    word = word.strip().split()[0] if word.strip() else ""
    if not word:
        speak("Which word should I define?")
        word = listen()
        if not word:
            return "I couldn't hear the word. Please try again."
    return get_definition(word)


@commands.register(
    [
        "calculate",
        "math",
        "plus",
        "minus",
        "times",
        "divided by",
        "multiply",
        "add",
        "subtract",
    ],
    "Calculate a math expression",
)
def _cmd_calculate(user_input: str) -> str:
    """Handle math calculations."""
    expr = user_input.lower()
    for phrase in ["calculate", "what is", "what's", "compute", "solve", "math"]:
        expr = expr.replace(phrase, "")
    expr = expr.strip()
    if not expr:
        speak("What would you like me to calculate?")
        expr = listen()
        if not expr:
            return "I couldn't hear the expression. Please try again."
    return calculate(expr)


@commands.register(
    ["what time", "current time", "time now", "time is it"],
    "Tell the current time",
)
def _cmd_time(user_input: str) -> str:
    """Handle time queries."""
    return get_current_time()


@commands.register(
    ["what date", "today's date", "current date", "what day"],
    "Tell the current date",
)
def _cmd_date(user_input: str) -> str:
    """Handle date queries."""
    if "time" in user_input.lower():
        return get_full_datetime()
    return get_current_date()


@commands.register(
    ["system info", "system information", "my system", "my computer"],
    "Show system information",
)
def _cmd_system_info(user_input: str) -> str:
    """Handle system info queries."""
    if "battery" in user_input.lower():
        return get_battery_status()
    return get_platform_summary()


@commands.register(["battery", "battery status", "power"], "Check battery status")
def _cmd_battery(user_input: str) -> str:
    """Handle battery status queries."""
    return get_battery_status()


@commands.register(
    ["clear history", "forget", "reset conversation"],
    "Clear conversation memory",
)
def _cmd_clear_memory(user_input: str) -> str:
    """Clear conversation history."""
    memory.clear()
    return "I've cleared our conversation history. What would you like to talk about?"


@commands.register(["help", "what can you do", "commands"], "List available commands")
def _cmd_help(user_input: str) -> str:
    """List all available commands."""
    cmd_list = commands.list_commands()
    lines = ["Here's what I can do:"]
    for keywords, description in cmd_list:
        trigger = keywords[0]
        lines.append(f"  - Say '{trigger}' — {description}")
    return "\n".join(lines)


# ── Main loop ───────────────────────────────────────────────────────


def run() -> None:
    """Run the main assistant interaction loop."""
    global _running

    # Startup
    setup_logging()
    mode = initialize_input()
    initialize_tts()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    # Validate config
    warnings = Config.validate()
    for warning in warnings:
        logger.warning(warning)

    blocking_errors = Config.validate_required_secrets()
    if blocking_errors:
        for err in blocking_errors:
            logger.error(err)
        raise RuntimeError(
            "Startup blocked due to invalid required secrets in .env. "
            "Rotate keys and set real values before running."
        )

    logger.info("Assistant startup complete (interaction_mode=%s)", mode)
    if mode == "voice":
        logger.info(
            "Voice mode active. If this is first run, grant microphone permission when prompted by your OS."
        )
    elif is_text_mode():
        caps = detect_interaction_capabilities()
        logger.info("Text mode active. Waiting for keyboard input from stdin.")
        if caps.in_docker:
            logger.warning(
                "Running in Docker text mode: microphone capture and speaker playback are disabled in this session."
            )
            logger.warning(
                "Use local host execution for full voice mode: python scripts/run.py"
            )
            if not caps.has_tty_stdin:
                raise RuntimeError(
                    "Non-interactive Docker text session detected. "
                    "Use `docker run -it ...` or `docker compose run --rm miehab` for keyboard input."
                )
        if not caps.has_tty_stdin:
            logger.warning(
                "No interactive TTY detected. For live typing use 'docker run -it ...' or 'docker compose run --rm miehab'."
            )

    name = Config.ASSISTANT_NAME
    greeting = (
        f"Hi, I'm {name}, your personal voice assistant. How can I help you today?"
    )
    logger.info(greeting)
    speak(greeting)

    while _running:
        try:
            user_query = listen()
        except KeyboardInterrupt:
            logger.info("Input interrupted by user; preparing shutdown.")
            break

        if not user_query or not _running:
            continue

        # Record user message in conversation memory
        memory.add_user_message(user_query)

        # Try to route to a registered command
        handler, keyword = commands.route(user_query)

        if handler is not None:
            try:
                response = handler(user_query)
            except Exception as exc:
                logger.error(
                    "Command handler failed for '%s': %s", keyword, exc, exc_info=True
                )
                response = "I hit an internal error while handling that command."
            if response == "__EXIT__":
                farewell = "Goodbye! Talk to you soon!"
                logger.info(farewell)
                speak(farewell)
                break
            logger.info("Response: %s", response[:100] if response else "")
            speak(response)
            memory.add_assistant_message(response)
        else:
            # Default: AI-generated response with conversation context
            speak("Let me think...")
            history = memory.get_messages_for_api()
            response = generate_response(user_query, conversation_history=history)
            logger.info("AI response: %s", response[:100])
            speak(response)
            memory.add_assistant_message(response)

        # Prompt for continued interaction
        if _running:
            speak("Do you need help with anything else?")

    logger.info("Assistant shutting down...")
    shutdown()


def shutdown() -> None:
    """Cleanly release application resources."""
    with suppress(Exception):
        shutdown_input()
    with suppress(Exception):
        shutdown_tts()
    with suppress(Exception):
        close_http_session()
    logger.info("Assistant shut down cleanly.")


def main() -> None:
    """Entry point for the voice assistant."""
    try:
        run()
    except KeyboardInterrupt:
        logger.info("Assistant interrupted by user.")
        with suppress(Exception):
            speak("Goodbye!")
        shutdown()
    except Exception as e:
        logger.critical("Unexpected error: %s", e, exc_info=True)
        shutdown()
        raise


if __name__ == "__main__":
    main()
