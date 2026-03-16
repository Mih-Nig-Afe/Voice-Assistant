"""Tests for configuration module."""

import os
from unittest.mock import patch

from voice_assistant.config import Config


class TestConfig:
    """Test suite for Config class."""

    def test_default_assistant_name(self):
        """Default assistant name should be Miehab."""
        assert Config.ASSISTANT_NAME == "Miehab"

    def test_default_weather_units(self):
        """Default weather units should be metric."""
        assert Config.WEATHER_UNITS == "metric"

    def test_default_wiki_language(self):
        """Default Wikipedia language should be English."""
        assert Config.WIKI_LANGUAGE == "en"

    def test_get_api_key_empty(self):
        """get_api_key should return None when key is empty."""
        with patch.object(Config, "OPENWEATHER_API_KEY", ""):
            assert Config.get_api_key() is None

    def test_get_api_key_placeholder(self):
        """get_api_key should return None for placeholder value."""
        with patch.object(Config, "OPENWEATHER_API_KEY", "your_api_key_here"):
            assert Config.get_api_key() is None

    def test_get_api_key_valid(self):
        """get_api_key should return the key when set."""
        with patch.object(Config, "OPENWEATHER_API_KEY", "test_key_123"):
            assert Config.get_api_key() == "test_key_123"

    def test_validate_warns_on_missing_api_key(self):
        """validate should warn when API key is missing."""
        with patch.object(Config, "OPENWEATHER_API_KEY", ""):
            warnings = Config.validate()
            assert any("OPENWEATHER_API_KEY" in w for w in warnings)

    def test_project_root_exists(self):
        """Project root path should exist."""
        assert Config.PROJECT_ROOT.exists()

    def test_listen_timeout_is_positive(self):
        """Listen timeout should be a positive integer."""
        assert Config.LISTEN_TIMEOUT > 0

    def test_phrase_time_limit_is_positive(self):
        """Phrase time limit should be a positive integer."""
        assert Config.PHRASE_TIME_LIMIT > 0

