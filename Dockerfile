# ─────────────────────────────────────────────────────────────────────
# Voice Assistant (Miehab) — Docker Image
# ─────────────────────────────────────────────────────────────────────
# Build:  docker build -t miehab .
# Run:    docker run --env-file .env -it miehab
# ─────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

ARG ENABLE_AUDIO=false

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash miehab
WORKDIR /home/miehab/app

# Install base system packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && if [ "$ENABLE_AUDIO" = "true" ]; then \
    apt-get install -y --no-install-recommends portaudio19-dev espeak-ng; \
    fi \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies for text mode by default.
# A separate voice-capable variant can be built with: --build-arg ENABLE_AUDIO=true
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
    groq>=0.18.0 \
    edge-tts>=6.1.12 \
    SpeechRecognition>=3.14.3 \
    requests>=2.32.5 \
    wikipedia>=1.4.0 \
    python-dotenv>=1.1.1 \
    PyYAML>=6.0.2 \
    fastapi>=0.116.1 \
    uvicorn>=0.35.0 \
    pyttsx3>=2.99 \
    playsound3>=3.2.8 \
    psutil>=5.9.8 \
    && if [ "$ENABLE_AUDIO" = "true" ]; then pip install --no-cache-dir PyAudio>=0.2.14; fi

# Copy source code
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/
COPY sounds/ sounds/
COPY pyproject.toml .

# Force text mode in Docker (no mic/speaker available)
ENV PYTHONPATH="/home/miehab/app/src"
ENV PYTHONUNBUFFERED=1
ENV INTERACTION_MODE=text

# Switch to non-root user
RUN chown -R miehab:miehab /home/miehab/app
USER miehab

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "from voice_assistant.config import Config; Config.validate()" || exit 1

ENTRYPOINT ["python", "scripts/run.py"]
