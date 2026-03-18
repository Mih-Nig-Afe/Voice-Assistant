# Changelog

All notable changes to this project are documented in this file.

## [1.2.12] - 2026-03-18

### Fixed

- Added server-side neural speech synthesis endpoint (`/api/speech/synthesize`) using `edge-tts`, with frontend playback support and browser-speech fallback.
- Improved spoken reply naturalness via neural voice output, voice chunking, and safer playback cancellation handling.
- Added runtime model-health tracking that blocks unstable Groq models (for example tool-call-incompatible responses) after repeated failures.
- Updated default Groq primary model to `moonshotai/kimi-k2-instruct-0905` and added configurable fallback chain (`AI_MODEL_FALLBACKS`).

### Tested

- Added web endpoint tests for speech synthesis success, empty text validation, and unavailable-backend handling.
- Added AI-engine test coverage for tool-call-incompatible primary model failover and runtime blocklisting behavior.

## [1.2.11] - 2026-03-18

### Fixed

- Improved news intent parsing so natural phrases like `tell me your news` route to general headlines instead of malformed topic filters.
- Added news-topic normalization for natural language phrasing (for example `what's the latest news about technology`).
- Added fallback behavior to retry general headlines when topic-filtered news returns no articles.
- Changed default conversational model to `openai/gpt-oss-120b` for stronger dialogue quality on Groq.

### Tested

- Added web/news tests covering generic news phrases, topic extraction, and topic-empty fallback behavior.

## [1.2.10] - 2026-03-18

### Fixed

- Improved weather city extraction for noisy voice follow-ups (for example phrases like `for shashamani` now normalize to `shashamani`).
- Upgraded fallback speech transcription default to `whisper-large-v3` for better recognition quality.
- Added configurable speech-to-text settings (`STT_MODEL`, `STT_LANGUAGE`, `STT_PROMPT`) and wired them into Groq transcription requests.
- Improved AI response system prompt for better intent inference from imperfect transcripts and more direct answers.

### Tested

- Added weather/transcription-oriented web tests and kept full suite passing.

## [1.2.9] - 2026-03-18

### Fixed

- Removed browser-speech network cooldown lockout flow that could keep voice input blocked.
- Switched browser speech `network` failures to immediate built-in recording fallback.
- Added WebAudio WAV capture fallback so backend transcription still works when `MediaRecorder` is unavailable.
- Added no-store cache headers for `/` and `/static/*` to reduce stale frontend JS after redeploys.

### Tested

- Added static asset cache-header coverage in web tests.

## [1.2.8] - 2026-03-18

### Fixed

- Added backend speech transcription endpoint (`/api/speech/transcribe`) using Groq Whisper for browser-recorded audio fallback.
- Added frontend automatic fallback from browser speech-recognition network/service failures to built-in recording mode.
- Added safer handling for tiny/noise-only audio payloads to return an empty transcript instead of backend errors.

### Tested

- Added endpoint tests for transcription success path, invalid base64 rejection, and tiny-audio handling.

## [1.2.7] - 2026-03-18

### Fixed

- Added web middleware redirect from `http://0.0.0.0:8000` to `http://127.0.0.1:8000` so browser mic features can use a loopback-safe origin.
- Improved frontend mic guidance with explicit `0.0.0.0` bind-address messaging and dynamic loopback URL hints.
- Reset browser speech network cooldown state after successful recognition so intermittent failures do not accumulate into false lockouts.

### Tested

- Added regression test coverage for `0.0.0.0` host redirect behavior in web mode.

## [1.2.6] - 2026-03-17

### Fixed

- Removed strict frontend secure-context pre-block that could prevent valid browser speech attempts.
- Added direct speech-start fallback when microphone preflight APIs are unavailable or unreliable.
- Improved permission messaging so "granted" appears only after a successful `getUserMedia` request.
- Added clearer startup-failure guidance when voice capture cannot start in the browser.

## [1.2.5] - 2026-03-17

### Fixed

- Fixed weather-intent parsing for phrases like "what is weather in addis ababa today".
- Prevented city-only follow-ups (for example "addis") from being misrouted to calculator intent.
- Added defensive frontend event-binding guards so UI controls remain responsive even with partial/stale DOM.

### Tested

- Added regression test coverage for city follow-up routing with "addis" in pending-weather flow.

## [1.2.4] - 2026-03-17

### Fixed

- Added explicit `Request Mic Access` button in the web UI to trigger microphone permission requests on demand.
- Improved microphone permission handling to avoid false hard-block behavior on browsers with inconsistent permission-state reporting.
- Improved weather city extraction to ignore trailing time/filler words (for example `today`, `now`) in natural phrases.

### Tested

- Added web test coverage for weather phrase parsing with trailing `today`.

## [1.2.3] - 2026-03-17

### Fixed

- Improved web speech permission flow to request microphone access more safely and allow retry without hard lockout.
- Added browser-permission checks and cooldown-based retry behavior for repeated speech `network` errors.
- Improved weather intent parsing for natural phrasing such as "tell me weather of hawassa".
- Added follow-up weather handling so a city-only reply (for example "hawassa") is understood after a weather prompt.

### Tested

- Added/updated unit tests for weather phrase extraction and follow-up city handling in web mode.

## [1.2.2] - 2026-03-17

### Fixed

- Improved browser speech-recognition resilience in the web frontend.
- Added microphone permission preflight before starting speech capture.
- Added network-error throttling and auto-pause after repeated `network` failures to prevent error spam loops.
- Added clearer user guidance in-UI for permission/network recovery while preserving text chat fallback.

## [1.2.1] - 2026-03-17

### Fixed

- Updated Docker Compose to start the web frontend server (`scripts/run_web.py`) instead of terminal mode.
- Exposed port `8000` in Compose for browser access.

### Docs

- Updated Docker instructions to reflect web-first Compose startup and browser URL.

## [1.2.0] - 2026-03-17

### Added

- Introduced a new FastAPI-powered web frontend backend at `scripts/run_web.py`.
- Added browser UI with a modern chat console and animated glowing assistant orb.
- Implemented browser speech recognition for voice input and speech synthesis for spoken replies.
- Added `/api/chat` and `/api/health` endpoints for frontend interaction and diagnostics.

### Changed

- Added `fastapi` and `uvicorn` to project dependencies and package scripts (`miehab-web`).
- Added web query processing pipeline with command handling and AI fallback in `voice_assistant.web`.

### Tested

- Added unit tests for key web query behaviors (help, exit, empty input).

## [1.1.3] - 2026-03-17

### Security

- Hardened `.gitignore` to ignore `.env.*` and common key/certificate artifacts while keeping `.env.example` tracked.
- Hardened `.dockerignore` to exclude secret files from Docker build context.
- Added `SECURITY.md` with public-repo secret management policy and incident response steps.

### Docs

- Added README security section linking to `SECURITY.md`.

## [1.1.2] - 2026-03-17

### Fixed

- Added explicit runtime diagnostics that explain why voice is disabled in container text sessions.
- Added startup warnings clarifying that Docker text mode does not provide microphone capture or spoken playback.
- Improved operator guidance to run voice mode locally for full microphone and speaker functionality.

### Docs

- Added local voice quick-start instructions and expected voice-mode logs.
- Clarified Docker vs local voice behavior for macOS/Windows users.

## [1.1.1] - 2026-03-17

### Fixed
- Improved text mode behavior when stdin is not actually interactive (common with docker compose service logs mode).
- Added clear runtime warning messages explaining the correct interactive run commands.
- Prevented silent waiting loops when no input stream is available.

### Docs
- Added Docker input troubleshooting guidance.
- Clarified the difference between `docker compose run` (interactive) and `docker compose up` (service/log mode).
- Added changelog reference in the main README.

## [1.1.0] - 2026-03-17

### Added
- Voice-first interaction detection with robust auto mode.
- Runtime capability detection for Docker/headless vs local hosts.
- Shared runtime utilities for input sanitization and HTTP behavior.
- Graceful shutdown resource cleanup for input, TTS, and HTTP session.

### Changed
- Upgraded dependencies to newer stable versions.
- Added optional Docker audio-capable build variant while keeping text-first default image lightweight.
- Strengthened API error handling, rate limit handling, timeout behavior, and request timing logs.
- Improved command routing priority for news intents.

### Tested
- Unit tests passing.
- Docker piped stdin interaction validated.
- Full command set verified in text-mode container session.

## [1.0.0] - 2026-03-17

### Initial
- Initial public release of the voice assistant core features.
