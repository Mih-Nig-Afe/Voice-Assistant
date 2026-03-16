"""Tests for dictionary module."""

from unittest.mock import MagicMock, patch

from voice_assistant.dictionary import get_definition


class TestGetDefinition:
    """Test suite for dictionary lookups."""

    def test_empty_word(self):
        """Should prompt for a word when empty."""
        result = get_definition("")
        assert "tell me" in result.lower() or "please" in result.lower()

    def test_invalid_word(self):
        """Should reject non-alphabetic input."""
        result = get_definition("123!@#")
        assert "valid" in result.lower() or "doesn't" in result.lower()

    @patch("voice_assistant.dictionary.requests.get")
    def test_successful_definition(self, mock_get):
        """Should return formatted definition."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "word": "hello",
                "phonetic": "/həˈloʊ/",
                "meanings": [
                    {
                        "partOfSpeech": "noun",
                        "definitions": [
                            {
                                "definition": "A greeting.",
                                "example": "She gave a cheerful hello.",
                            }
                        ],
                    }
                ],
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = get_definition("hello")
        assert "hello" in result.lower()
        assert "greeting" in result.lower()

    @patch("voice_assistant.dictionary.requests.get")
    def test_word_not_found(self, mock_get):
        """Should handle 404 responses."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = get_definition("xyznotaword")
        assert "couldn't find" in result.lower()

    @patch("voice_assistant.dictionary.requests.get")
    def test_timeout(self, mock_get):
        """Should handle timeouts gracefully."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        result = get_definition("test")
        assert "taking too long" in result.lower() or "try again" in result.lower()

