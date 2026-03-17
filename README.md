# AI-Powered Voice Assistant — Miehab

Miehab is an interactive AI-driven voice assistant that combines speech recognition, text-to-speech, and AI-based natural language processing for hands-free interaction. It provides dynamic responses, weather updates, Wikipedia summaries, and more.

---

## Features

- **Voice Interaction** — Listens and responds to user queries using speech recognition
- **Text-to-Speech** — Cross-platform TTS with automatic engine selection
- **AI-Powered Responses** — Intelligent replies via GPT-Neo (HuggingFace Transformers)
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

# Docker Compose service mode (logs/daemon style, not ideal for live typing)
docker compose up --build

# Note: docker-compose.yml forces INTERACTION_MODE=text to prevent voice-mode startup failures in containers.
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

### Docker Input Troubleshooting

- If you only see startup logs and no command prompt, your container likely has no interactive stdin attached.
- Use `docker run -it ...` or `docker compose run --rm miehab` for live command typing.
- Use piped input for scripted tests: `printf "help\nbye\n" | docker run --rm -i --env-file .env miehab`.
- Avoid relying on `docker compose up` for manual conversation input.
- On macOS/Windows, Docker sessions are text-first; voice mode should be run on the host machine.
- Docker Compose now overrides `INTERACTION_MODE=text` even if your local `.env` uses `INTERACTION_MODE=voice`.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for upgrade notes, fixes, and release history.

## Security

See [SECURITY.md](SECURITY.md) for secret handling policy, rotation steps, and public-repo hygiene.

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
|---|---|
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
| "How are you today?" | AI conversation (Groq/Llama 3.3) |
| "Bye" / "Goodbye" | Exit the assistant |

---

## Project Structure

```
Voice-Assistant/
├── src/voice_assistant/       # Main package (13 modules)
│   ├── __init__.py            # Package metadata
│   ├── assistant.py           # Main orchestrator & command registration
│   ├── commands.py            # Command registry & routing engine
│   ├── config.py              # Configuration management
│   ├── logging_config.py      # Structured logging setup
│   ├── conversation.py        # Multi-turn conversation memory
│   ├── speech.py              # Speech recognition module
│   ├── tts.py                 # Cross-platform text-to-speech
│   ├── ai_engine.py           # AI backend (Groq + HuggingFace fallback)
│   ├── weather.py             # OpenWeather API integration
│   ├── wiki.py                # Wikipedia integration
│   ├── news.py                # News headlines (GNews + RSS fallback)
│   ├── jokes.py               # Joke fetching (JokeAPI)
│   ├── dictionary.py          # Word definitions (Free Dictionary API)
│   ├── calculator.py          # Safe math expression evaluator
│   ├── datetime_cmd.py        # Date/time commands
│   └── system_info.py         # System information reporter
├── tests/                     # Comprehensive unit tests (12 test files)
├── config/default.yaml        # Default configuration values
├── scripts/run.py             # Entry point script
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
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Groq API key for AI conversations |
| `OPENWEATHER_API_KEY` | *(optional)* | OpenWeather API key for weather |
| `GNEWS_API_KEY` | *(optional)* | GNews API key for news (falls back to RSS) |
| `AI_BACKEND` | `groq` | AI backend (`groq` or `huggingface`) |
| `AI_MODEL` | `llama-3.3-70b-versatile` | Model name for the AI backend |
| `LOG_LEVEL` | `INFO` | Logging level |
| `TTS_ENGINE` | `auto` | TTS engine (`auto` or `pyttsx3`) |
| `LISTEN_TIMEOUT` | `8` | Speech recognition timeout (seconds) |

See `.env.example` for the full list of configurable options.

---

## API Setup Guide (All Free — No Credit Card Required)

### 1. Groq API (AI Conversations) — **Recommended, Required for best experience**
- **URL:** [https://console.groq.com](https://console.groq.com)
- **What it does:** Powers intelligent AI conversations using Llama 3.3 70B
- **How to get a key:**
  1. Go to [console.groq.com](https://console.groq.com) and sign up (Google/GitHub login)
  2. Click "API Keys" in the left sidebar
  3. Click "Create API Key", give it a name, and copy the key
  4. Add to your `.env`: `GROQ_API_KEY=gsk_your_key_here`
- **Free tier limits:** 30 requests/min, 14,400 requests/day, 6,000 tokens/min
- **Why Groq?** Fastest free LLM API available; runs Llama 3.3 70B with sub-second latency

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

### 3. GNews API (News Headlines) — *Optional*
- **URL:** [https://gnews.io](https://gnews.io)
- **What it does:** Fetches latest news headlines and topic-based news
- **How to get a key:**
  1. Sign up at [gnews.io/register](https://gnews.io/register)
  2. Your API key appears on the dashboard after login
  3. Add to your `.env`: `GNEWS_API_KEY=your_key_here`
- **Free tier limits:** 100 requests/day
- **Fallback:** If no key is set, Miehab uses Google News RSS feed (unlimited, no key needed)

### 4. Free APIs That Need No Key
These APIs are used by Miehab and require **no signup or API key**:

| Service | API | Used For |
|---|---|---|
| **JokeAPI** | [v2.jokeapi.dev](https://v2.jokeapi.dev) | Random jokes (120 req/min) |
| **Free Dictionary** | [dictionaryapi.dev](https://dictionaryapi.dev) | Word definitions (unlimited) |
| **Google News RSS** | news.google.com/rss | News fallback (unlimited) |

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

- AI powered by [Groq](https://groq.com/) (Llama 3.3 70B) with [HuggingFace](https://huggingface.co/) fallback
- Speech via [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) and [pyttsx3](https://pypi.org/project/pyttsx3/)
- Weather by [OpenWeather](https://openweathermap.org/) · News by [GNews](https://gnews.io/)
- Jokes by [JokeAPI](https://jokeapi.dev/) · Definitions by [Free Dictionary API](https://dictionaryapi.dev/)
- Summaries by [Wikipedia](https://www.wikipedia.org/)

> **Note:** Ensure your microphone and speakers are properly configured. API keys must be stored in environment variables — never commit them to source control.
