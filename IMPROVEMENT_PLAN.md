# Voice Assistant (Miehab) — Improvement Plan

> **Audit Date:** 2026-03-16
> **Auditor:** Augment Agent
> **Project:** AI-Powered Voice Assistant — Miehab

---

## 1. Critical Issues

### 1.1 🔴 Hardcoded API Key (Security Vulnerability)
- **File:** `app.py:240`
- **Issue:** OpenWeather API key `0e66cfb4c038c19707aadd74d4c14ac7` is committed directly in source code.
- **Risk:** Key exposed in public repository; can be harvested by bots, leading to abuse and billing issues.
- **Fix:** Move to environment variable (`OPENWEATHER_API_KEY`), add `.env` support via `python-dotenv`, and add `.env` to `.gitignore`. **Revoke the current key immediately.**

### 1.2 🔴 Hardcoded Absolute Windows File Paths
- **File:** `app.py:74-75`
- **Issue:** Paths `r'c:\Users\TS PDA\Documents\Projects\...'` are machine-specific and will break on any other system.
- **Fix:** Use `os.path` relative paths from the project root. Sound files already exist in `sounds1/` directory.

### 1.3 🔴 Windows-Only Dependency (`win32com.client`)
- **File:** `app.py:35`
- **Issue:** `import win32com.client` causes `ImportError` on macOS/Linux. The app cannot run on non-Windows systems.
- **Fix:** Make Windows SAPI optional with graceful platform detection using `sys.platform`.

---

## 2. High Priority Issues

### 2.1 🟠 No `requirements.txt` in Repository
- **Issue:** README references `pip install -r requirements.txt` but no such file exists. CI workflows will fail.
- **Fix:** Create `requirements.txt` with pinned versions for all dependencies.

### 2.2 🟠 No `.gitignore` File
- **Issue:** No `.gitignore` means `__pycache__/`, `.env`, model caches, IDE files can be committed.
- **Fix:** Add comprehensive Python `.gitignore`.

### 2.3 🟠 No Tests Exist
- **Issue:** CI workflows run `pytest` but no test files exist — every CI run reports 0 tests or fails.
- **Fix:** Create test suite with unit tests for each module.

### 2.4 🟠 Five Redundant GitHub Actions Workflows
- **Issue:** 5 separate workflow files with significant overlap:
  - `python-app.yml` — flake8 + pytest on Python 3.10
  - `python-package.yml` — flake8 + pytest on Python 3.9/3.10/3.11
  - `pylint.yml` — pylint on Python 3.8/3.9/3.10
  - `python-package-conda.yml` — requires non-existent `environment.yml`
  - `python-publish.yml` — PyPI publish (no `setup.py`/`pyproject.toml` exists)
- **Fix:** Consolidate into 1 CI workflow + 1 publish workflow; remove conda workflow.

### 2.5 🟠 README Inconsistencies
- **Issue:** README says `python main.py` but actual file is `app.py`. File structure section references non-existent `requirements.txt`.
- **Fix:** Update README to reflect actual project structure.

### 2.6 🟠 Monolithic Single-File Architecture
- **Issue:** All 243 lines in one `app.py` — speech, TTS, AI, weather, Wikipedia, and main loop all mixed together.
- **Fix:** Split into modular package with separate concerns.

---

## 3. Medium Priority Issues

### 3.1 🟡 Print Statements Instead of Logging
- **Issue:** 20+ `print()` calls used for debugging/status. No log levels, no file output, no structured logging.
- **Fix:** Replace with Python `logging` module with configurable levels.

### 3.2 🟡 No Type Hints
- **Issue:** No function signatures use type annotations. Reduces IDE support and code clarity.
- **Fix:** Add type hints to all functions per PEP 484.

### 3.3 🟡 No Docstrings (Beyond File Header)
- **Issue:** Functions have inline comments but no proper docstrings for API documentation.
- **Fix:** Add Google-style or NumPy-style docstrings to all public functions.

### 3.4 🟡 AI Model Loaded at Import Time
- **File:** `app.py:41-45`
- **Issue:** `pipeline('text-generation', ...)` downloads/loads a ~500MB model at startup, blocking the app.
- **Fix:** Lazy-load model on first use; add loading indicator.

### 3.5 🟡 No Input Validation on Weather City
- **Issue:** User-provided city name is passed directly to the API URL without sanitization.
- **Fix:** Validate/sanitize input, use `params` dict with `requests.get()`.

### 3.6 🟡 Wikipedia Case-Sensitivity Bug
- **File:** `app.py:215`
- **Issue:** `"Wikipedia" in user_query.lower()` — comparing capitalized "Wikipedia" against lowercased string, so it never matches.
- **Fix:** Change to `"wikipedia" in user_query.lower()`.

### 3.7 🟡 Thread Safety Concerns
- **Issue:** `engine_lock` protects TTS but `speaker` (win32com) object is not thread-safe by design (COM threading).
- **Fix:** Ensure COM objects are used in the thread they were created in, or use proper COM initialization.

---

## 4. Low Priority Issues

### 4.1 🔵 No Graceful Shutdown
- **Issue:** `Ctrl+C` during `listen()` or `speak()` can leave audio resources in bad state.
- **Fix:** Add signal handlers and cleanup logic.

### 4.2 🔵 Magic Numbers
- **Issue:** `timeout=8`, `phrase_time_limit=12`, `max_length=100`, `sentences=7` are unexplained constants.
- **Fix:** Move to configuration with documented defaults.

### 4.3 🔵 No Command Extensibility
- **Issue:** Commands are hardcoded `if/elif` chains. Adding new commands requires modifying the main loop.
- **Fix:** Implement command registry/plugin pattern.

### 4.4 🔵 Outdated GitHub Actions Versions
- **Issue:** Workflows use `actions/setup-python@v3` (deprecated). Current is `@v5`.
- **Fix:** Update all action versions.

### 4.5 🔵 No pyproject.toml or setup.py
- **Issue:** The publish workflow tries to build a package but no build configuration exists.
- **Fix:** Add `pyproject.toml` for proper Python packaging.

---

## 5. Feature Enhancement Opportunities

| Enhancement | Description | Priority |
|---|---|---|
| Cross-platform TTS | Use `pyttsx3` as default, remove `win32com` dependency | High |
| Conversation memory | Store context for multi-turn conversations | Medium |
| Command plugins | Extensible command system via registry pattern | Medium |
| Voice wake word | "Hey Miehab" activation without manual trigger | Low |
| GUI interface | Simple Tkinter/web UI for settings and status | Low |
| Multi-language | Support languages beyond English | Low |

---

## 6. Testing Strategy

| Test Type | Coverage Target | Tools |
|---|---|---|
| Unit Tests | Individual modules (weather, wikipedia, AI, config) | pytest, unittest.mock |
| Integration Tests | End-to-end command flow (mocked audio) | pytest |
| Linting | PEP 8 compliance | flake8, ruff |
| Type Checking | Static analysis | mypy |
| Security | Dependency vulnerability scanning | pip-audit, safety |

