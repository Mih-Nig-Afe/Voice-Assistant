"""
Date/Time module for Voice Assistant.

Provides current date, time, and day of the week.
No external API required — uses Python's built-in datetime.
"""

from datetime import datetime

from voice_assistant.logging_config import get_logger

logger = get_logger("datetime_cmd")


def get_current_time() -> str:
    """
    Get the current time in a human-friendly format.

    Returns:
        Formatted time string (e.g., "The current time is 2:30 PM").
    """
    now = datetime.now()
    time_str = now.strftime("%I:%M %p")
    logger.debug("Time requested: %s", time_str)
    return f"The current time is {time_str}."


def get_current_date() -> str:
    """
    Get the current date in a human-friendly format.

    Returns:
        Formatted date string (e.g., "Today is Sunday, March 16, 2026").
    """
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    logger.debug("Date requested: %s", date_str)
    return f"Today is {date_str}."


def get_day_of_week() -> str:
    """
    Get the current day of the week.

    Returns:
        Day name string (e.g., "Today is Sunday").
    """
    day = datetime.now().strftime("%A")
    return f"Today is {day}."


def get_full_datetime() -> str:
    """
    Get both date and time combined.

    Returns:
        Full datetime string.
    """
    now = datetime.now()
    return (
        f"Today is {now.strftime('%A, %B %d, %Y')} "
        f"and the time is {now.strftime('%I:%M %p')}."
    )

