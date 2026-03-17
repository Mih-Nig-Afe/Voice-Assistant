# Changelog

All notable changes to this project are documented in this file.

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
