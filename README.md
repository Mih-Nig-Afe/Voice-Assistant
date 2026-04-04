# AI-Powered Voice Assistant - Miehab

Miehab is an interactive AI-driven voice assistant that combines speech recognition, text-to-speech, and AI-based natural language processing for hands-free interaction. It provides dynamic responses, weather updates, Wikipedia summaries, and more.

---

## Features

- **Voice Interaction** — Listens and responds to user queries using speech recognition
- **Text-to-Speech** — Cross-platform TTS with automatic engine selection
- **AI-Powered Responses** — Intelligent replies via Groq-hosted models with HuggingFace fallback
- **Weather Updates** — Real-time weather data from OpenWeather API
- **Wikipedia Integration** — Topic summaries with disambiguation handling
- **Audio Feedback** — Customizable beep sounds for listening state indicators
- **Extensible Commands** — Plugin-style command registry for easy feature addition
- **Configuration Management** — Environment variables and YAML config support

---

## Getting Started

### Prerequisites

- Python 3.9 or above
- A working microphone and speakers
- An API key from [OpenWeather](https://openweathermap.org/) (for weather feature)

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Mih-Nig-Afe/Voice-Assistant.git
   cd Voice-Assistant
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env and add your OPENWEATHER_API_KEY
   ```

4. **Run the assistant:**

   ```bash
   python scripts/run.py
   ```

### Docker Setup (Alternative)

```bash
# Build the image
docker build -t miehab .

# Run interactively in text mode (default for Docker)
docker run --env-file .env -it miehab

# Non-interactive stdin test
printf "help\njoke\nwhat time\nbye\n" | docker run --env-file .env --rm -i miehab

# Optional voice-capable Docker image (Linux only)
docker build --build-arg ENABLE_AUDIO=true -t miehab-voice .
docker run --env-file .env -it --device /dev/snd -e INTERACTION_MODE=voice miehab-voice

# Docker Compose interactive session (recommended for typing commands)
docker compose run --rm miehab

# Docker Compose service mode (starts the web frontend)
docker compose up --build

# Open the web UI in your browser
open http://127.0.0.1:8000

# Note: docker-compose.yml now starts scripts/run_web.py by default.
```

> **Note:** Docker audio passthrough works on Linux. On macOS/Windows, use the native Python setup above for full microphone/speaker support.

### Interaction Mode Behavior

- `INTERACTION_MODE=auto` (default): prefers voice mode on local machines when a microphone is detected; falls back to text mode in Docker/headless environments.
- `INTERACTION_MODE=voice`: force microphone input and spoken output.
- `INTERACTION_MODE=text`: force keyboard input and printed output.

### Voice Mode Quick Start (Local Host)

If you want real microphone input and spoken output, run outside Docker:

```bash
export INTERACTION_MODE=voice
python scripts/run.py
```

Expected startup logs for voice mode:

- `interaction_mode=voice`
- `Input mode initialized: voice`
- `TTS initialized: pyttsx3` (or platform TTS backend)

If you still get text mode locally:

- Grant microphone permission to your terminal/Python app in OS privacy settings.
- Install/verify PyAudio in your local environment.
- Confirm your microphone is visible to the OS.

## Web Frontend (Beautiful Voice Console)

The project now includes a modern browser frontend to operate Miehab visually with:

- Live chat panel for text interaction
- Browser microphone input via Web Speech API
- Spoken assistant replies via server-side neural TTS (with browser voice fallback)
- Dynamic glowing assistant orb with listening/speaking motion effects

### Run the Web UI

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Start the web server:

   ```bash
   python scripts/run_web.py
   ```

3. Open in your browser:

   ```text
   http://127.0.0.1:8000
   ```

### Voice Notes for Web Mode

- Microphone capture uses browser support (`SpeechRecognition` / `webkitSpeechRecognition`).
- Spoken replies use server neural TTS first (`/api/speech/synthesize`), then fall back to browser `speechSynthesis` if needed.
- For best voice support, use current Chrome or Edge.
- If mic permission is blocked, you can still use full text chat.
- `http://0.0.0.0:8000` is not a microphone-safe browser origin; use `127.0.0.1` or `localhost`.
- If browser speech reports a `network` failure, Miehab now switches immediately to built-in recording mode and transcribes audio through the backend.
- In fallback mode, tap mic once to start recording and tap again (or wait ~7 seconds) to submit speech for transcription.
- News intent parsing now ignores filler phrasing (for example `tell me your news`) and falls back to general headlines when topic-specific results are empty.
- News/update phrasing (for example `give me an update on Iran and Israel`) now routes to live headlines instead of generic model guesses.
- NASA/Artemis mission topics now prefer NASA's official free RSS feed before general news sources.
- Conflict-heavy topics (for example `Iran Israel war`) now prefer a curated free RSS mix from BBC, NPR, Al Jazeera, and DW before generic news search results.
- Headline-number follow-ups (for example `more about headline 5`) now stay focused on that selected headline/topic.
- Weather follow-up mode now rejects conversational noise as a city (for example `i'm kinda feeling too`) and asks for the city again.
- Weather responses are now conversational and intent-aware: comfort questions (for example `is that hot?`) get interpreted guidance, while detail requests return explicit numbers.
- News update/follow-up responses are now deterministic and strictly grounded in fetched headlines to reduce hallucinations on live topics.
- News follow-ups about timing (for example `when is Artemis II launching`) now return only timing hints present in fetched headlines, or explicitly say no confirmed date is present.
- News follow-up questions (for example `who is attacking now?`) now stay in the news context and answer from recent headlines instead of falling into Wikipedia topic lookup.
- Date/time questions in flexible phrasing (for example `what is the date today`) now route directly to real local datetime responses instead of Wikipedia fallback.
- Weather context now remembers recent city mentions in hot/cold conversations, so follow-ups like `how hot is it now?` can reuse the same city.

### Docker Input Troubleshooting

- If you only see startup logs, wait for Uvicorn startup then open `http://127.0.0.1:8000`.
- `docker compose up --build` now runs the web UI server, not the terminal chat loop.
- Use `docker compose run --rm miehab python scripts/run.py` only when you specifically want terminal text mode.
- On macOS/Windows, browser voice features depend on browser mic permissions (Chrome/Edge recommended).
- Opening `http://0.0.0.0:8000` now redirects to `http://127.0.0.1:8000` automatically.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release notes, fixes, and test status.

## Security

See [SECURITY.md](SECURITY.md) for secret handling policy, rotation steps, and repository hygiene.

Quick rules:

- Keep real keys only in local `.env` and CI secret stores.
- Never commit `.env` or certificate/private key files.
- Rotate keys immediately if exposure is suspected.

## Documentation Policy

- Every behavior change or operational fix must update both README and CHANGELOG.
- Docker run-mode changes must include tested command examples.
- New configuration keys must be reflected in `.env.example` and README configuration tables.

### Example Commands

| Command | Action |
| --- | --- |
| "What's the weather in Addis Ababa?" | Fetches current weather |
| "Tell me about artificial intelligence" | Wikipedia summary |
| "What's the latest news?" | Top news headlines |
| "News about technology" | Topic-filtered news |
| "Tell me a joke" | Random joke |
| "Define serendipity" | Dictionary definition |
| "Calculate 15 times 4" | Math calculation |
| "What time is it?" | Current time |
| "What date is it?" | Current date |
| "System info" | System information |
| "Battery status" | Battery level |
| "Help" | List all commands |
| "Clear history" | Reset conversation memory |
| "How are you today?" | AI conversation (Groq GPT OSS with fallbacks) |
| "Bye" / "Goodbye" | Exit the assistant |

---

## Project Structure

```text
Voice-Assistant/
├── src/voice_assistant/       # Main package (19 Python modules + frontend assets)
│   ├── __init__.py            # Package metadata
│   ├── ai_engine.py           # AI backend (Groq + HuggingFace fallback)
│   ├── assistant.py           # Main orchestrator & command registration
│   ├── calculator.py          # Safe math expression evaluator
│   ├── commands.py            # Command registry & routing engine
│   ├── config.py              # Configuration management
│   ├── conversation.py        # Multi-turn conversation memory
│   ├── datetime_cmd.py        # Date/time commands
│   ├── dictionary.py          # Word definitions (Free Dictionary API)
│   ├── jokes.py               # Joke fetching (JokeAPI)
│   ├── logging_config.py      # Structured logging setup
│   ├── news.py                # News headlines (GNews + RSS fallback)
│   ├── runtime.py             # Runtime interaction mode detection
│   ├── speech.py              # Speech recognition module
│   ├── system_info.py         # System information reporter
│   ├── tts.py                 # Cross-platform text-to-speech
│   ├── weather.py             # OpenWeather API integration
│   ├── web.py                 # FastAPI web backend and API routes
│   ├── wiki.py                # Wikipedia integration
│   └── frontend/              # Browser UI assets (HTML/CSS/JS)
├── tests/                     # Comprehensive unit tests (13 test files)
├── config/default.yaml        # Default configuration values
├── scripts/run.py             # Entry point script
├── scripts/run_web.py         # Web server entry point script
├── sounds/                    # Audio feedback files
├── .env.example               # Environment variable template
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Package build configuration
├── LICENSE                    # MIT License
└── README.md                  # This file
```

---

## Development

### Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

### Linting

```bash
flake8 src/ tests/ --max-line-length=120
```

### Type Checking

```bash
mypy src/voice_assistant/ --ignore-missing-imports
```

---

## Configuration

Configuration is managed through environment variables (`.env` file) with sensible defaults.

| Variable | Default | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | *(required)* | Groq API key for AI conversations |
| `OPENWEATHER_API_KEY` | *(optional)* | OpenWeather API key for weather |
| `GNEWS_API_KEY` | *(optional)* | GNews API key for news (falls back to RSS) |
| `AI_BACKEND` | `groq` | AI backend (`groq` or `huggingface`) |
| `AI_MODEL` | `llama-3.3-70b-versatile` | Primary model name for the AI backend |
| `AI_MODEL_FALLBACKS` | `openai/gpt-oss-120b,qwen/qwen3-32b` | Comma-separated fallback model order if primary fails |
| `STT_MODEL` | `whisper-large-v3` | Speech-to-text model for web fallback (`whisper-large-v3` or `whisper-large-v3-turbo`) |
| `STT_LANGUAGE` | `en` | Language hint for fallback speech transcription |
| `STT_PROMPT` | *(preset city-bias prompt)* | Optional prompt to improve recognition of names and places |
| `WEB_TTS_BACKEND` | `edge` | Web speech output backend (`edge`, `browser`, or `auto`) |
| `WEB_TTS_VOICE` | `en-US-AvaMultilingualNeural` | Neural voice ID used when `WEB_TTS_BACKEND=edge` |
| `WEB_TTS_RATE` | `+0%` | Neural TTS speaking rate |
| `WEB_TTS_PITCH` | `+0Hz` | Neural TTS pitch |
| `WEB_TTS_MAX_CHARS` | `900` | Max response text length accepted by `/api/speech/synthesize` |
| `LOG_LEVEL` | `INFO` | Logging level |
| `TTS_ENGINE` | `auto` | TTS engine (`auto` or `pyttsx3`) |
| `LISTEN_TIMEOUT` | `8` | Speech recognition timeout (seconds) |

AI runtime note: `AI_BACKEND`, `AI_MODEL`, `AI_MODEL_FALLBACKS`, `AI_MAX_LENGTH`, and `AI_MAX_HISTORY` are reloaded from `.env` at request time, so model changes in `.env` are applied by the running assistant.
Docker note: `docker-compose.yml` mounts `.env` into the container, so AI model edits in `.env` are picked up on the next request. If you run plain `docker run --env-file`, restart the container after editing `.env`.

See `.env.example` for the full list of configurable options.

---

## API Setup Guide (All Free - No Credit Card Required)

### 1. Groq API (AI Conversations) - **Recommended, Required for Best Experience**

- **URL:** [https://console.groq.com](https://console.groq.com)
- **What it does:** Powers intelligent AI conversations using modern Groq-hosted large models (default: GPT OSS 120B)
- **How to get a key:**
  1. Go to [console.groq.com](https://console.groq.com) and sign up (Google/GitHub login)
  2. Click "API Keys" in the left sidebar
  3. Click "Create API Key", give it a name, and copy the key
  4. Add to your `.env`: `GROQ_API_KEY=gsk_your_key_here`
- **Free tier limits:** 30 requests/min, 14,400 requests/day, 6,000 tokens/min
- **Why Groq?** Fast low-latency LLM API with multiple strong model options and easy fallback chaining

### 2. OpenWeather API (Weather)

- **URL:** [https://openweathermap.org/api](https://openweathermap.org/api)
- **What it does:** Provides current weather data for any city worldwide
- **How to get a key:**
  1. Sign up at [openweathermap.org](https://home.openweathermap.org/users/sign_up)
  2. After email verification, go to "API keys" in your profile
  3. Copy your default key (auto-generated) or create a new one
  4. Add to your `.env`: `OPENWEATHER_API_KEY=your_key_here`
  5. **Note:** New keys take ~10 minutes to activate
- **Free tier limits:** 1,000 API calls/day, 60 calls/min

### 3. GNews API (News Headlines) - *Optional*

- **URL:** [https://gnews.io](https://gnews.io)
- **What it does:** Fetches latest news headlines and topic-based news
- **How to get a key:**
  1. Sign up at [gnews.io/register](https://gnews.io/register)
  2. Your API key appears on the dashboard after login
  3. Add to your `.env`: `GNEWS_API_KEY=your_key_here`
- **Free tier limits:** 100 requests/day
- **Fallback:** If no key is set, Miehab uses Google News RSS feed (unlimited, no key needed)
- **Conflict topics:** Even with a GNews key configured, conflict-heavy topics can use a curated free RSS mix first for better source quality.

### 4. Free APIs That Need No Key

These APIs are used by Miehab and require **no signup or API key**:

| Service | API | Used For |
| --- | --- | --- |
| **JokeAPI** | [v2.jokeapi.dev](https://v2.jokeapi.dev) | Random jokes (120 req/min) |
| **Free Dictionary** | [dictionaryapi.dev](https://dictionaryapi.dev) | Word definitions (unlimited) |
| **Google News RSS** | news.google.com/rss | News fallback (unlimited) |
| **NASA RSS** | nasa.gov/rss | Official NASA mission/news updates (no key) |
| **BBC / NPR / Al Jazeera / DW RSS** | official RSS feeds | Curated conflict/world-news mix (no key) |

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a pull request

---

## Acknowledgements

- AI powered by [Groq](https://groq.com/) (GPT OSS/Qwen/Llama model chain) with [HuggingFace](https://huggingface.co/) fallback
- Speech via [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) and [pyttsx3](https://pypi.org/project/pyttsx3/)
- Weather by [OpenWeather](https://openweathermap.org/) · News by [GNews](https://gnews.io/) plus curated official RSS feeds
- Jokes by [JokeAPI](https://jokeapi.dev/) · Definitions by [Free Dictionary API](https://dictionaryapi.dev/)
- Summaries by [Wikipedia](https://www.wikipedia.org/)

> **Note:** Ensure your microphone and speakers are properly configured. API keys must be stored in environment variables — never commit them to source control.
