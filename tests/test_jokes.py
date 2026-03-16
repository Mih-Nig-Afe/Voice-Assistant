"""Tests for jokes module."""

from unittest.mock import MagicMock, patch

from voice_assistant.jokes import get_joke


class TestGetJoke:
    """Test suite for joke fetching."""

    @patch("voice_assistant.jokes.requests.get")
    def test_twopart_joke(self, mock_get):
        """Should format two-part jokes correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": False,
            "type": "twopart",
            "setup": "Why do programmers prefer dark mode?",
            "delivery": "Because light attracts bugs!",
        }
        mock_get.return_value = mock_response

        result = get_joke()
        assert "programmers" in result
        assert "bugs" in result

    @patch("voice_assistant.jokes.requests.get")
    def test_single_joke(self, mock_get):
        """Should return single-line jokes."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": False,
            "type": "single",
            "joke": "A SQL query walks into a bar and sees two tables.",
        }
        mock_get.return_value = mock_response

        result = get_joke()
        assert "SQL" in result or "tables" in result

    @patch("voice_assistant.jokes.requests.get")
    def test_api_error(self, mock_get):
        """Should handle API errors gracefully."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": True,
            "message": "No joke found",
        }
        mock_get.return_value = mock_response

        result = get_joke()
        assert "couldn't" in result.lower() or "material" in result.lower()

    @patch("voice_assistant.jokes.requests.get")
    def test_timeout(self, mock_get):
        """Should handle timeouts."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        result = get_joke()
        assert "slow" in result.lower() or "try again" in result.lower()

