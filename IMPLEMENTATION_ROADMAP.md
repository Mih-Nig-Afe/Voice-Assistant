# Implementation Roadmap — Voice Assistant (Miehab)

> **Created:** 2026-03-16
> **Target Completion:** Phase 1-3 implemented in this session

---

## Phase 1: Foundation & Security Fixes ✅
**Priority:** Critical | **Timeline:** Immediate

### Tasks
- [x] Revoke/externalize hardcoded API key → `.env` + `python-dotenv`
- [x] Fix hardcoded Windows file paths → relative `os.path` resolution
- [x] Create `.gitignore` with Python defaults
- [x] Create `.env.example` with required environment variables
- [x] Create `requirements.txt` with pinned dependency versions
- [x] Create `pyproject.toml` for proper packaging

### Validation
- `.env` is in `.gitignore`
- No secrets in tracked files
- `pip install -r requirements.txt` succeeds

---

## Phase 2: Project Restructuring ✅
**Priority:** High | **Timeline:** Immediate (depends on Phase 1)

### New Directory Structure
```
Voice-Assistant/
├── src/
│   └── voice_assistant/
│       ├── __init__.py          # Package init with version
│       ├── config.py            # Configuration management
│       ├── logging_config.py    # Logging setup
│       ├── speech.py            # Speech recognition module
│       ├── tts.py               # Text-to-speech module
│       ├── ai_engine.py         # AI response generation
│       ├── weather.py           # Weather API integration
│       ├── wiki.py              # Wikipedia integration
│       ├── commands.py          # Command registry & routing
│       └── assistant.py         # Main assistant orchestrator
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_weather.py
│   ├── test_wiki.py
│   ├── test_ai_engine.py
│   └── test_commands.py
├── config/
│   └── default.yaml             # Default configuration values
├── sounds/
│   ├── start_beep.wav
│   └── stop_beep.wav
├── scripts/
│   └── run.py                   # Entry point script
├── .github/
│   └── workflows/
│       ├── ci.yml               # Consolidated CI pipeline
│       └── publish.yml          # PyPI publish (cleaned up)
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── IMPROVEMENT_PLAN.md
├── IMPLEMENTATION_ROADMAP.md
├── pyproject.toml
└── requirements.txt
```

### Tasks
- [x] Create directory structure with `__init__.py` files
- [x] Extract speech recognition → `src/voice_assistant/speech.py`
- [x] Extract TTS → `src/voice_assistant/tts.py`
- [x] Extract AI engine → `src/voice_assistant/ai_engine.py`
- [x] Extract weather → `src/voice_assistant/weather.py`
- [x] Extract Wikipedia → `src/voice_assistant/wiki.py`
- [x] Create command registry → `src/voice_assistant/commands.py`
- [x] Create config management → `src/voice_assistant/config.py`
- [x] Create logging config → `src/voice_assistant/logging_config.py`
- [x] Create assistant orchestrator → `src/voice_assistant/assistant.py`
- [x] Create entry point → `scripts/run.py`
- [x] Rename `sounds1/` → `sounds/` with clean filenames

### Validation
- `python scripts/run.py` launches the assistant
- All imports resolve correctly
- No circular dependencies

---

## Phase 3: Code Quality & Best Practices ✅
**Priority:** High | **Timeline:** Immediate (depends on Phase 2)

### Tasks
- [x] Add type hints to all functions
- [x] Add docstrings to all modules and public functions
- [x] Replace `print()` with `logging` module
- [x] Fix Wikipedia case-sensitivity bug
- [x] Add input validation for weather city names
- [x] Use `requests.get(params=...)` instead of f-string URLs
- [x] Make `win32com` import conditional on platform
- [x] Consolidate 5 GitHub Actions into 2 workflows
- [x] Update action versions to latest (`@v5`)

### Validation
- `flake8` passes with 0 errors
- `mypy` reports no critical issues
- All logging uses proper levels

---

## Phase 4: Testing (Scaffolding Created)
**Priority:** Medium | **Timeline:** Next iteration

### Tasks
- [x] Create test scaffolding for all modules
- [ ] Achieve >70% unit test coverage
- [ ] Add integration tests with mocked audio
- [ ] Add CI test execution

### Validation
- `pytest` runs and passes
- Coverage report generated

---

## Phase 5: Future Enhancements (Planned)
**Priority:** Low | **Timeline:** Future iterations

### Tasks
- [ ] Lazy-load AI model on first use
- [ ] Add conversation memory/context
- [ ] Implement command plugin system
- [ ] Add graceful shutdown with signal handlers
- [ ] Create simple settings UI
- [ ] Multi-language support

---

## Dependency Graph

```
Phase 1 (Security) ──→ Phase 2 (Restructure) ──→ Phase 3 (Quality)
                                                       │
                                                       ↓
                                                  Phase 4 (Tests)
                                                       │
                                                       ↓
                                                  Phase 5 (Features)
```

