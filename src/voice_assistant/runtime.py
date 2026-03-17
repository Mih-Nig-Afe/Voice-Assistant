"""Runtime utilities for interaction mode, validation, and HTTP behavior."""

from __future__ import annotations

import os
import re
import socket
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger

logger = get_logger("runtime")

_session: Optional[requests.Session] = None


@dataclass(frozen=True)
class InteractionCapabilities:
    """Computed runtime capabilities for interaction mode selection."""

    in_docker: bool
    has_tty_stdin: bool
    has_display: bool
    has_microphone: bool
    has_speaker: bool

    @property
    def has_audio_io(self) -> bool:
        return self.has_microphone and self.has_speaker


def in_docker() -> bool:
    """Best-effort Docker/container detection."""
    if os.path.exists("/.dockerenv"):
        return True
    with suppress(OSError):
        with open("/proc/1/cgroup", "r", encoding="utf-8") as fh:
            content = fh.read()
        if "docker" in content or "kubepods" in content or "containerd" in content:
            return True
    return False


def _probe_audio_devices() -> tuple[bool, bool]:
    """Detect microphone/speaker availability via PyAudio when available."""
    try:
        import pyaudio  # type: ignore[import-not-found]
    except Exception:
        return False, False

    has_input = False
    has_output = False
    pa = None
    try:
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                has_input = True
            if info.get("maxOutputChannels", 0) > 0:
                has_output = True
            if has_input and has_output:
                break
    except Exception as exc:
        logger.debug("Audio probe failed: %s", exc)
    finally:
        if pa is not None:
            with suppress(Exception):
                pa.terminate()
    return has_input, has_output


def detect_interaction_capabilities() -> InteractionCapabilities:
    """Collect current runtime capabilities for robust mode decisions."""
    current_os = sys.platform
    is_docker = in_docker()
    tty_stdin = bool(sys.stdin and sys.stdin.isatty())

    # Display availability is relevant mainly on Linux desktop environments.
    has_display = bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    if current_os in {"win32", "darwin"}:
        has_display = True

    mic, speaker = _probe_audio_devices()
    return InteractionCapabilities(
        in_docker=is_docker,
        has_tty_stdin=tty_stdin,
        has_display=has_display,
        has_microphone=mic,
        has_speaker=speaker,
    )


def choose_interaction_mode() -> str:
    """Resolve runtime interaction mode from config and detected capabilities."""
    configured = Config.INTERACTION_MODE.strip().lower()
    if configured not in {"auto", "text", "voice"}:
        logger.warning(
            "Invalid INTERACTION_MODE='%s'; falling back to auto.",
            Config.INTERACTION_MODE,
        )
        configured = "auto"

    caps = detect_interaction_capabilities()

    if configured == "text":
        logger.info("Interaction mode forced to text by configuration.")
        return "text"

    if configured == "voice":
        if caps.has_microphone:
            logger.info("Interaction mode forced to voice by configuration.")
            return "voice"
        logger.warning(
            "INTERACTION_MODE=voice but no microphone was detected; falling back to text."
        )
        return "text"

    # Auto mode: prefer voice on non-container hosts with real microphone.
    if not caps.in_docker and caps.has_microphone:
        logger.info("Auto mode selected voice input (microphone detected).")
        return "voice"

    logger.info(
        "Auto mode selected text input (docker=%s, microphone=%s, tty=%s).",
        caps.in_docker,
        caps.has_microphone,
        caps.has_tty_stdin,
    )
    return "text"


def get_http_session() -> requests.Session:
    """Return a shared requests session with retries and pooling."""
    global _session
    if _session is not None:
        return _session

    retries = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        status_forcelist=(408, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        backoff_factor=0.4,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)

    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    _session = session
    return session


def close_http_session() -> None:
    """Close the shared HTTP session during shutdown."""
    global _session
    if _session is not None:
        with suppress(Exception):
            _session.close()
        _session = None


def timed_request(
    *,
    method: str,
    url: str,
    timeout: Optional[float] = None,
    **kwargs: Any,
) -> tuple[requests.Response, float]:
    """Perform an HTTP request and return response plus elapsed time."""
    session = get_http_session()
    start = time.perf_counter()
    response = session.request(
        method=method.upper(),
        url=url,
        timeout=timeout if timeout is not None else Config.HTTP_TIMEOUT,
        **kwargs,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return response, elapsed_ms


_SAFE_TEXT_PATTERN = re.compile(r"[^\w\s\-\.'\?,:!/]", re.UNICODE)


def sanitize_query(text: str, max_length: int = 120) -> str:
    """Sanitize user-facing query strings passed to remote APIs."""
    clean = _SAFE_TEXT_PATTERN.sub(" ", text or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:max_length]


def validate_hostname_connectivity(
    host: str, port: int = 443, timeout: float = 2.0
) -> bool:
    """Quick connectivity test used for better diagnostics."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
