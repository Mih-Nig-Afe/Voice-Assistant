# ─────────────────────────────────────────────────────────────────────
# Voice Assistant (Miehab) — Docker Image
# ─────────────────────────────────────────────────────────────────────
# Build:  docker build -t miehab .
# Run:    docker run --env-file .env -it --device /dev/snd miehab
# ─────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# System dependencies for audio (PortAudio for PyAudio, ALSA for sound)
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    libasound2-dev \
    libespeak-dev \
    espeak \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash miehab
WORKDIR /home/miehab/app

# ── Dependencies ────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application ─────────────────────────────────────────────────────
FROM deps AS app

# Copy source code
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/
COPY sounds/ sounds/
COPY pyproject.toml .

# Set Python path so the package is importable
ENV PYTHONPATH="/home/miehab/app/src"
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
RUN chown -R miehab:miehab /home/miehab/app
USER miehab

# Health check — verify Python can import the package
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "from voice_assistant.config import Config; Config.validate()" || exit 1

# Default command
ENTRYPOINT ["python", "scripts/run.py"]

