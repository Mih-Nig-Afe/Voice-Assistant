# ─────────────────────────────────────────────────────────────────────
# Voice Assistant (Miehab) — Docker Image
# ─────────────────────────────────────────────────────────────────────
# Build:  docker build -t miehab .
# Run:    docker run --env-file .env -it miehab
# ─────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash miehab
WORKDIR /home/miehab/app

# Install Python dependencies (no audio packages needed — text mode)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
    groq>=0.4.0 \
    SpeechRecognition>=3.10.0 \
    requests>=2.31.0 \
    wikipedia>=1.4.0 \
    python-dotenv>=1.0.0 \
    PyYAML>=6.0

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

