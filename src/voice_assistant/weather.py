"""
Weather module for Voice Assistant.

Fetches current weather data from the OpenWeather API.
"""

import re
import time
from typing import Optional

import requests

from voice_assistant.config import Config
from voice_assistant.logging_config import get_logger
from voice_assistant.runtime import sanitize_query

logger = get_logger("weather")

# Simple pattern: allow letters, spaces, hyphens, apostrophes
_VALID_CITY_PATTERN = re.compile(r"^[a-zA-Z](?:[a-zA-Z\s\-'\.]*[a-zA-Z])?$")
_CITY_ALIASES = {
    "shashamani": "shashemene",
    "shashamane": "shashemene",
    "nazret": "adama",
}


def _validate_city(city: str) -> bool:
    """
    Validate city name to prevent injection or malformed requests.

    Args:
        city: City name to validate.

    Returns:
        True if the city name is valid.
    """
    return bool(city and _VALID_CITY_PATTERN.match(city.strip()))


def _normalize_city_alias(city: str) -> str:
    """Map common transliteration aliases to OpenWeather-friendly names."""
    normalized = city.strip().lower()
    return _CITY_ALIASES.get(normalized, city.strip())


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

    city = sanitize_query(city, max_length=80)
    city = _normalize_city_alias(city)
    if not _validate_city(city):
        return "That doesn't look like a valid city name. Please try again."

    try:
        def _weather_request(query: str):
            start = time.perf_counter()
            response = requests.get(
                Config.WEATHER_API_URL,
                params={"q": query, "appid": key, "units": Config.WEATHER_UNITS},
                timeout=Config.HTTP_TIMEOUT,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            payload = response.json()
            logger.info(
                "Weather API call completed in %.1fms (status=%s)",
                elapsed_ms,
                response.status_code,
            )
            return response, payload

        response, data = _weather_request(city)
        logger.info(
            "Weather lookup query used: %s",
            city,
        )

        if data.get("cod") != 200 and "," not in city:
            message = str(data.get("message", "")).lower()
            if response.status_code == 404 and "city not found" in message:
                et_query = f"{city},ET"
                response, et_data = _weather_request(et_query)
                if et_data.get("cod") == 200:
                    data = et_data
                else:
                    data = et_data

        if data.get("cod") != 200:
            error_msg = str(data.get("message", "Unknown error"))
            if response.status_code == 429:
                return "Weather service rate limit reached. Please try again shortly."
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
    except requests.exceptions.RequestException as exc:
        logger.error("Weather HTTP error for '%s': %s", city, exc)
        return "Couldn't connect to the weather service. Please try again later."
    except Exception as e:
        logger.error("Error fetching weather for '%s': %s", city, e)
        return "I couldn't fetch the weather details. Please try later."
