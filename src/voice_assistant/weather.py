"""
Weather module for Voice Assistant.

Fetches current weather data from the OpenWeather API.
"""

import re
from typing import Optional

import requests

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger

logger = get_logger("weather")

# Simple pattern: allow letters, spaces, hyphens, apostrophes
_VALID_CITY_PATTERN = re.compile(r"^[a-zA-Z\s\-'\.]+$")


def _validate_city(city: str) -> bool:
    """
    Validate city name to prevent injection or malformed requests.

    Args:
        city: City name to validate.

    Returns:
        True if the city name is valid.
    """
    return bool(city and _VALID_CITY_PATTERN.match(city.strip()))


def get_weather(city: str, api_key: Optional[str] = None) -> str:
    """
    Fetch current weather information for a city.

    Args:
        city: Name of the city to check weather for.
        api_key: OpenWeather API key. Falls back to config if not provided.

    Returns:
        Formatted weather description string.
    """
    key = api_key or Config.get_api_key()
    if not key:
        return "Weather feature is unavailable. Please set your OPENWEATHER_API_KEY."

    city = city.strip()
    if not _validate_city(city):
        return "That doesn't look like a valid city name. Please try again."

    try:
        response = requests.get(
            Config.WEATHER_API_URL,
            params={
                "q": city,
                "appid": key,
                "units": Config.WEATHER_UNITS,
            },
            timeout=10,
        )
        data = response.json()

        if data.get("cod") != 200:
            error_msg = data.get("message", "Unknown error")
            logger.warning("Weather API error for '%s': %s", city, error_msg)
            return f"Couldn't get weather for {city}: {error_msg}"

        weather = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]

        return (
            f"{city.capitalize()} weather: {weather}, "
            f"{temp}°C, feels like {feels_like}°C."
        )

    except requests.exceptions.Timeout:
        logger.error("Weather API request timed out for '%s'", city)
        return "The weather service is taking too long. Please try again."
    except requests.exceptions.ConnectionError:
        logger.error("No internet connection for weather request")
        return "Couldn't connect to the weather service. Check your internet."
    except Exception as e:
        logger.error("Error fetching weather for '%s': %s", city, e)
        return "I couldn't fetch the weather details. Please try later."

