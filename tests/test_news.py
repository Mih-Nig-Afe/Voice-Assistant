"""Tests for news module."""

from unittest.mock import MagicMock, patch

from voice_assistant.news import get_top_headlines, _get_headlines_fallback


class TestGetTopHeadlines:
    """Test suite for news headlines."""

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_successful_headlines(self, mock_get, mock_config):
        """Should return formatted headlines."""
        mock_config.GNEWS_API_KEY = "test_key"
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "articles": [
                {"title": "Breaking News Story", "source": {"name": "Reuters"}},
                {"title": "Another Big Event", "source": {"name": "BBC"}},
            ]
        }
        mock_get.return_value = mock_response

        result = get_top_headlines()
        assert "Breaking News Story" in result
        assert "Reuters" in result

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_topic_filter(self, mock_get, mock_config):
        """Should include topic in the header."""
        mock_config.GNEWS_API_KEY = "test_key"
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "articles": [
                {"title": "Tech News", "source": {"name": "TechCrunch"}},
            ]
        }
        mock_get.return_value = mock_response

        result = get_top_headlines(topic="technology")
        assert "technology" in result.lower()

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_no_articles(self, mock_get, mock_config):
        """Should handle empty results."""
        mock_config.GNEWS_API_KEY = "test_key"
        mock_response = MagicMock()
        mock_response.json.return_value = {"articles": []}
        mock_get.return_value = mock_response

        result = get_top_headlines()
        assert "no news" in result.lower()

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_topic_no_articles_falls_back_to_general_headlines(
        self, mock_get, mock_config
    ):
        mock_config.GNEWS_API_KEY = "test_key"
        topic_empty = MagicMock()
        topic_empty.status_code = 200
        topic_empty.json.return_value = {"articles": []}
        general = MagicMock()
        general.status_code = 200
        general.json.return_value = {
            "articles": [
                {"title": "General Story", "source": {"name": "Reuters"}},
            ]
        }
        mock_get.side_effect = [topic_empty, general]

        result = get_top_headlines(topic="tell me your")
        assert "General Story" in result
        assert mock_get.call_count == 2

    @patch("voice_assistant.news.Config")
    def test_no_api_key_uses_fallback(self, mock_config):
        """Should fall back to RSS when no API key."""
        mock_config.GNEWS_API_KEY = ""
        with patch("voice_assistant.news._get_headlines_fallback") as mock_fallback:
            mock_fallback.return_value = "Fallback headlines"
            result = get_top_headlines()
            mock_fallback.assert_called_once()

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_timeout(self, mock_get, mock_config):
        """Should handle timeouts."""
        mock_config.GNEWS_API_KEY = "test_key"
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        result = get_top_headlines()
        assert "taking too long" in result.lower() or "try again" in result.lower()
