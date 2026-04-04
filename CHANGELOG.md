<!-- markdownlint-disable MD022 MD024 MD032 -->

# Changelog

All notable changes to this project are documented in this file.

## [1.2.22] - 2026-04-04

### Fixed

- Added robust date/time intent detection in web mode so phrasing like `what is the date today` routes to real local datetime responses instead of Wikipedia fallback.
- Reworked news update and news follow-up responses to deterministic headline-grounded output (no free-form model hallucination over live-news answers).
- Expanded news follow-up detection (including `when`/`launch`/`mission` language) so mission-update follow-up questions stay in live-news context.
- Added Groq chat retry logic for reasoning-only/empty `finish_reason=length` responses to keep primary model usage more stable before falling back.
- Fixed pending weather-city follow-ups so phrases like `what about Hawassa` resolve to the city instead of the invalid query `about hawassa`.
- Added source-grounded AI conversational rewrites for news summaries and news follow-ups, with deterministic fallback when the model reply is unavailable or unusable.
- Fixed news follow-up date extraction so source metadata like `NASA, 2026-04-01` is recognized in timing answers.
- Added guarded fallback for short/truncated AI news rewrites and clearer handling for `how did it begin` follow-up questions.
- Restricted conversational news rewrites to the primary model only, so empty primary rewrites fall back to grounded source text instead of jumping to backup models.
- Added curated conflict-news RSS routing before GNews for conflict-heavy topics so sources like BBC, NPR, Al Jazeera, and DW are preferred over noisier generic matches.
- Added parallel curated-feed fetch, topic scoring, and cross-source dedupe for conflict headlines.
- Switched the default Groq primary model to `llama-3.3-70b-versatile` and moved `openai/gpt-oss-120b` into the fallback chain.
- Added query-aware conflict headline prioritization so explainer questions prefer explainer-style sources and live-update questions prefer current reporting.
- Stripped Groq STT prompt leakage from transcripts before routing so hidden speech hints no longer surface as assistant replies.
- Expanded headline-reference parsing for speech errors like `first line`, `first hit on the news`, and `Force Head Light`, while preserving topic-refresh behavior for explicit topical follow-ups.
- Added selected-headline memory for pronoun follow-ups like `more on it` so the assistant stays anchored to the last chosen story.
- Guarded truncated speech fragments like `Cameras and...` so partial captures prompt for a retry instead of producing unrelated answers.

### Changed

- Updated default fallback chain to `openai/gpt-oss-120b,qwen/qwen3-32b` now that `llama-3.3-70b-versatile` is the primary model.
- Updated Docker Compose mounts to include `.env` in-container so runtime AI config refresh can read live model changes from your `.env` file.

### Tested

- Added/updated regression tests for deterministic news summary/follow-up output, date-intent routing, and reasoning-only primary-model retry behavior.
- Added tests covering NASA-topic routing through NASA's official RSS source and fallback behavior.
- Added regression tests for `what about <city>` weather follow-ups and AI-grounded news rewrite/fallback behavior.
- Added regression tests for news follow-up date extraction from source metadata and origin-question handling.
- Added regression tests for curated conflict RSS routing, fallback behavior, and duplicate/off-topic filtering.
- Added regression tests for query-aware conflict headline prioritization and default model config changes.
- Added regression tests for STT prompt-leak cleanup, selected-headline reuse, speech-misheard headline references, and truncated-fragment handling.
- Full suite passing: `179 passed`.

## [1.2.21] - 2026-04-04

### Fixed

- Added runtime AI config refresh from `.env` so changing `AI_MODEL`/`AI_MODEL_FALLBACKS`/`AI_BACKEND` updates active model selection without code edits.
- Added runtime backend reset when AI env signature changes to avoid stale clients after model/backend updates.

### Security

- Added `.DS_Store` to `.gitignore` and removed the tracked root `.DS_Store` artifact from the repository workspace.
- Performed tracked-file secret-pattern scan and confirmed no committed credential material (only placeholders in docs/examples).

### Tested

- Added tests covering runtime AI-config refresh behavior and env-driven config reload.
- Full suite passing: `153 passed`.

## [1.2.20] - 2026-04-04

### Changed

- Migrated default Groq model from deprecated Kimi K2 variants to `openai/gpt-oss-120b`.
- Updated default fallback chain to `openai/gpt-oss-20b,llama-3.3-70b-versatile,qwen/qwen3-32b` to keep free-tier-friendly failover behavior.

### Docs

- Updated `.env.example` and README model defaults and naming to reflect GPT OSS migration and remove Kimi-specific guidance.

## [1.2.19] - 2026-03-18

### Fixed

- Added explicit headline-reference follow-up handling (for example `more about headline 5`) so news stays anchored to the selected headline/topic instead of drifting into unrelated lists.
- Improved topic cleanup for noisy speech-transcript phrasing by removing filler tokens and standalone digits from extracted news topics.
- Added a guarded fallback message when a topic-specific refresh cannot be found, to avoid presenting unrelated generic headlines as if they were topical.

### Tested

- Added web regression tests for noisy news phrase normalization, headline-number follow-up summarization, and headline follow-up fallback behavior.
- Full suite passing: `151 passed`.

## [1.2.18] - 2026-03-18

### Fixed

- Upgraded weather responses to be conversational and intent-aware instead of always repeating raw API text.
- Added weather interpretation for comfort-style follow-ups (for example `is that hot` / `why am I uncomfortable`) using live condition + temperature + feels-like values.
- Added detail-mode weather replies when users explicitly ask for numbers/details.
- Improved weather city extraction for phrasing like `moved back to Hawassa` and `weather details for Hawassa`.
- Fixed comfort-vs-detail prioritization so comparative questions (for example `hot or warm or moderate`) get interpreted answers instead of raw numeric repeats.

### Tested

- Added web regression tests for comfort follow-up weather interpretation, detail-style weather replies, and explanatory weather responses from mixed conversational input.
- Full suite passing: `147 passed`.

## [1.2.17] - 2026-03-18

### Fixed

- Improved weather city extraction for embedded phrases like `I'm in Hawassa and the weather is hot` by switching to non-greedy context matching.
- Fixed news follow-up cache reuse so topic switches (for example from `world` to `Iran/Israel/US`) fetch fresh headlines instead of reusing stale results.
- Added explicit `general` news-topic caching so follow-up questions can safely distinguish broad headlines from a new specific conflict topic.
- Tightened news relevance filtering to require stronger multi-keyword/entity matches for entity-heavy conflict queries, reducing unrelated headline leakage.
- Updated default AI model chain to `moonshotai/kimi-k2-instruct` with safer fallbacks tuned for Groq runtime stability.
- Updated default web neural voice to `en-US-AvaMultilingualNeural` and expanded STT prompt vocabulary for common Ethiopia city names and conflict terms.
- Switched news update/follow-up responses to human-style output by default, with confidence/sources metadata included only when explicitly requested.

### Tested

- Added news ranking regression coverage for filtering out US-only noise on Iran/Israel/US topics.
- Added/ran web regression tests for embedded city extraction and follow-up fresh-news fetch behavior.
- Added web regression coverage for explicit `general` topic caching and opt-in confidence/source metadata behavior.
- Full suite passing: `143 passed`.

## [1.2.16] - 2026-03-18

### Fixed

- Added news follow-up QA routing so questions like `who is attacking now?` stay grounded in recent news context instead of being misrouted to Wikipedia.
- Added in-memory recent-news context (`topic` + fetched headline block) to support multi-turn conflict follow-up questions.
- Added follow-up answer formatter with confidence and sources lines, aligned with summarized-update transparency.

### Tested

- Added web tests for follow-up routing using recent-news context and confidence/source lines on follow-up answers.

## [1.2.15] - 2026-03-18

### Fixed

- Added confidence/uncertainty annotation to summarized news updates based on source and headline coverage.
- Added explicit `Sources used` line to summarized news updates for better transparency.
- Kept headline-summary mode grounded in fetched headlines while making responses more human-readable.

### Tested

- Added regression coverage for confidence and source-line presence in summarized news responses.

## [1.2.14] - 2026-03-18

### Fixed

- Added weather context carry-over for hot/cold phrasing so recent city mentions can be reused in follow-up requests (for example `how hot is it now?`).
- Added support for common speech-to-text confusion around `how old is it` in hot-weather conversations by routing through weather intent when context indicates it.
- Added conversational news-update mode that summarizes fetched headlines into a short human-readable situational update instead of always returning a raw list.
- Improved topic extraction for update phrasing such as `update me on ...` and city-reference extraction with trailing punctuation.

### Tested

- Added web tests for hot-question city inference, context carry-over across turns, and summary-style news responses.
- Full suite passing: `130 passed`.

## [1.2.13] - 2026-03-18

### Fixed

- Improved news intent routing so update-style requests (for example `give me an update on ...`) use the live news pipeline instead of generic AI answers.
- Expanded topic extraction patterns for update/latest phrasing and normalized noisy wording around geopolitical requests.
- Added news-topic relevance ranking to prioritize headlines that match requested entities (for example Iran/US/Israel) and de-prioritize unrelated results.
- Tightened weather follow-up city handling to reject conversational noise and reprompt for a city instead of querying invalid phrases.

### Tested

- Added web regression tests for update-intent news routing, news-over-wiki preference for `what is the latest on ...`, and noisy weather follow-up handling.
- Added news tests for relevance ranking/filtering and fallback when topic results are unrelated.

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
