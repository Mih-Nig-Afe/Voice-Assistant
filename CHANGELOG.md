# Changelog

All notable changes to this project are documented in this file.

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
