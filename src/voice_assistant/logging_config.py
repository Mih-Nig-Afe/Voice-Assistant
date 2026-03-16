"""
Logging configuration for Voice Assistant.

Sets up structured logging with configurable levels.
"""

import logging
import sys

from voice_assistant.config import Config


def setup_logging() -> logging.Logger:
    """
    Configure and return the root logger for the application.

    Returns:
        logging.Logger: Configured root logger.
    """
    log_format = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    logger = logging.getLogger("voice_assistant")
    logger.setLevel(log_level)
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger under the voice_assistant namespace.

    Args:
        name: Module name for the logger.

    Returns:
        logging.Logger: Named logger instance.
    """
    return logging.getLogger(f"voice_assistant.{name}")

