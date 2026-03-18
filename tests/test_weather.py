"""Tests for weather module."""

from unittest.mock import MagicMock, patch

from voice_assistant.weather import _normalize_city_alias, _validate_city, get_weather


class TestValidateCity:
    """Test suite for city name validation."""

    def test_valid_city(self):
        assert _validate_city("London") is True

    def test_valid_city_with_spaces(self):
        assert _validate_city("New York") is True

    def test_valid_city_with_hyphen(self):
        assert _validate_city("Addis-Ababa") is True

    def test_valid_city_with_apostrophe(self):
        assert _validate_city("N'Djamena") is True

    def test_empty_string(self):
        assert _validate_city("") is False

    def test_numbers_rejected(self):
        assert _validate_city("City123") is False

    def test_special_chars_rejected(self):
        assert _validate_city("City;DROP TABLE") is False

    def test_city_alias_mapping(self):
        assert _normalize_city_alias("shashamani") == "shashemene"


class TestGetWeather:
    """Test suite for get_weather function."""

    def test_no_api_key(self):
        """Should return unavailable message when no API key."""
        with patch("voice_assistant.weather.Config") as mock_config:
            mock_config.get_api_key.return_value = None
            result = get_weather("London")
            assert "unavailable" in result.lower() or "OPENWEATHER_API_KEY" in result

    @patch("voice_assistant.weather.requests.get")
    def test_successful_weather(self, mock_get):
        """Should return formatted weather string on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "cod": 200,
            "weather": [{"description": "clear sky"}],
            "main": {"temp": 25.0, "feels_like": 23.0},
        }
        mock_get.return_value = mock_response

        with patch("voice_assistant.weather.Config") as mock_config:
            mock_config.get_api_key.return_value = "test_key"
            mock_config.WEATHER_API_URL = "https://api.test.com"
            mock_config.WEATHER_UNITS = "metric"
            result = get_weather("London", api_key="test_key")

        assert "clear sky" in result
        assert "25" in result

    @patch("voice_assistant.weather.requests.get")
    def test_api_error_response(self, mock_get):
        """Should handle API error responses gracefully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "cod": 404,
            "message": "city not found",
        }
        mock_get.return_value = mock_response

        result = get_weather("NonexistentCity", api_key="test_key")
        assert "city not found" in result.lower() or "couldn't" in result.lower()

    def test_invalid_city_name(self):
        """Should reject invalid city names."""
        result = get_weather("'; DROP TABLE--", api_key="test_key")
        assert "valid city" in result.lower()

    @patch("voice_assistant.weather.requests.get")
    def test_city_not_found_retries_with_et_country_hint(self, mock_get):
        first = MagicMock()
        first.status_code = 404
        first.json.return_value = {"cod": 404, "message": "city not found"}

        second = MagicMock()
        second.status_code = 200
        second.json.return_value = {
            "cod": 200,
            "weather": [{"description": "clear sky"}],
            "main": {"temp": 21.0, "feels_like": 20.0},
        }

        mock_get.side_effect = [first, second]
        result = get_weather("shashamani", api_key="test_key")
        assert "clear sky" in result
        assert mock_get.call_count == 2
        second_call_params = mock_get.call_args_list[1].kwargs["params"]
        assert second_call_params["q"].endswith(",ET")
