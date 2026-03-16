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

### Example Commands

| Command | Action |
|---|---|
| "What's the weather in Addis Ababa?" | Fetches current weather |
| "Tell me about artificial intelligence" | Wikipedia summary |
| "How are you today?" | AI-generated response |
| "Bye" / "Goodbye" | Exit the assistant |

---

## Project Structure

```
Voice-Assistant/
├── src/voice_assistant/       # Main package
│   ├── __init__.py            # Package metadata
│   ├── assistant.py           # Main orchestrator & interaction loop
│   ├── commands.py            # Command registry & routing
│   ├── config.py              # Configuration management
│   ├── logging_config.py      # Structured logging setup
│   ├── speech.py              # Speech recognition module
│   ├── tts.py                 # Text-to-speech module
│   ├── ai_engine.py           # AI response generation (GPT-Neo)
│   ├── weather.py             # OpenWeather API integration
│   └── wiki.py                # Wikipedia integration
├── tests/                     # Unit tests
│   ├── test_config.py
│   ├── test_weather.py
│   ├── test_wiki.py
│   ├── test_ai_engine.py
│   └── test_commands.py
├── config/default.yaml        # Default configuration values
├── scripts/run.py             # Entry point script
├── sounds/                    # Audio feedback files
├── .env.example               # Environment variable template
├── requirements.txt           # Python dependencies
├── pyproject.toml             # Package build configuration
├── IMPROVEMENT_PLAN.md        # Detailed audit & improvement plan
├── IMPLEMENTATION_ROADMAP.md  # Phased implementation schedule
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
| `OPENWEATHER_API_KEY` | *(required)* | Your OpenWeather API key |
| `LOG_LEVEL` | `INFO` | Logging level |
| `TTS_ENGINE` | `auto` | TTS engine (`auto` or `pyttsx3`) |
| `AI_MODEL` | `EleutherAI/gpt-neo-125M` | HuggingFace model name |
| `LISTEN_TIMEOUT` | `8` | Speech recognition timeout (seconds) |

See `.env.example` for the full list of configurable options.

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

- Built with [SpeechRecognition](https://pypi.org/project/SpeechRecognition/), [pyttsx3](https://pypi.org/project/pyttsx3/), and [HuggingFace Transformers](https://huggingface.co/transformers/)
- Weather data by [OpenWeather](https://openweathermap.org/)
- Summaries by [Wikipedia](https://www.wikipedia.org/)

> **Note:** Ensure your microphone and speakers are properly configured. API keys must be stored in environment variables — never commit them to source control.
