"""Web frontend backend for the Voice Assistant (Miehab).

Serves a browser UI and exposes a chat API so users can operate the
assistant with typed or spoken input.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
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


class ChatRequest(BaseModel):
    """Incoming chat message payload."""

    message: str


class ChatResponse(BaseModel):
    """Outgoing chat message payload."""

    response: str
    should_exit: bool = False


def _strip_phrases(text: str, phrases: list[str]) -> str:
    lowered = text.lower()
    for phrase in phrases:
        lowered = lowered.replace(phrase, "")
    return lowered.strip()


def process_user_query(user_input: str) -> ChatResponse:
    """Process one user message and return assistant output for web mode."""
    query = (user_input or "").strip()
    if not query:
        return ChatResponse(response="Please say or type something so I can help.")

    normalized = query.lower()
    memory.add_user_message(query)

    if any(word in normalized for word in ["bye", "goodbye", "exit", "quit", "stop"]):
        response = "Goodbye! Talk to you soon!"
        memory.add_assistant_message(response)
        return ChatResponse(response=response, should_exit=True)

    if "weather" in normalized or "temperature" in normalized:
        city = _strip_phrases(
            normalized,
            [
                "what's the weather in",
                "what is the weather in",
                "weather in",
                "temperature in",
                "weather",
                "temperature",
            ],
        )
        if not city:
            response = "Tell me the city, for example: weather in Addis Ababa."
        else:
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

    if any(
        p in normalized
        for p in [
            "calculate",
            "math",
            "plus",
            "minus",
            "times",
            "divided by",
            "multiply",
            "add",
            "subtract",
        ]
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


@app.get("/")
def index() -> FileResponse:
    """Serve the main web UI."""
    return FileResponse(_FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Health endpoint for runtime checks."""
    return {"status": "ok", "assistant": Config.ASSISTANT_NAME}


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
