"""Tests for Wikipedia integration module."""

from unittest.mock import MagicMock, patch

import wikipedia

from voice_assistant.wiki import get_summary


class TestGetSummary:
    """Test suite for Wikipedia get_summary function."""

    def test_empty_query(self):
        """Should return prompt message for empty query."""
        result = get_summary("")
        assert "specify a topic" in result.lower()

    def test_whitespace_query(self):
        """Should return prompt message for whitespace-only query."""
        result = get_summary("   ")
        assert "specify a topic" in result.lower()

    @patch("voice_assistant.wiki.wikipedia.summary")
    @patch("voice_assistant.wiki.wikipedia.set_lang")
    def test_successful_summary(self, mock_lang, mock_summary):
        """Should return Wikipedia summary on success."""
        mock_summary.return_value = "Python is a programming language."
        result = get_summary("Python")
        assert "Python is a programming language" in result

    @patch("voice_assistant.wiki.wikipedia.summary")
    @patch("voice_assistant.wiki.wikipedia.set_lang")
    def test_disambiguation_error(self, mock_lang, mock_summary):
        """Should list options on disambiguation error."""
        mock_summary.side_effect = wikipedia.exceptions.DisambiguationError(
            "Python", ["Python (programming)", "Python (snake)", "Monty Python"]
        )
        result = get_summary("Python")
        assert "did you mean" in result.lower()

    @patch("voice_assistant.wiki.wikipedia.summary")
    @patch("voice_assistant.wiki.wikipedia.set_lang")
    def test_page_error(self, mock_lang, mock_summary):
        """Should return not-found message on PageError."""
        mock_summary.side_effect = wikipedia.exceptions.PageError("xyznonexistent")
        result = get_summary("xyznonexistent")
        assert "couldn't find" in result.lower()

    @patch("voice_assistant.wiki.wikipedia.summary")
    @patch("voice_assistant.wiki.wikipedia.set_lang")
    def test_general_exception(self, mock_lang, mock_summary):
        """Should handle unexpected errors gracefully."""
        mock_summary.side_effect = Exception("Network error")
        result = get_summary("test")
        assert "issue" in result.lower() or "try again" in result.lower()

