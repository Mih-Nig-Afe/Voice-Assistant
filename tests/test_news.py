"""Tests for news module."""

from unittest.mock import MagicMock, patch

from voice_assistant.news import get_top_headlines, _get_headlines_fallback, _rank_articles_for_topic


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
    @patch("voice_assistant.news.requests.get")
    def test_topic_results_rank_and_filter_by_relevance(self, mock_get, mock_config):
        mock_config.GNEWS_API_KEY = "test_key"
        topic_response = MagicMock()
        topic_response.status_code = 200
        topic_response.json.return_value = {
            "articles": [
                {
                    "title": "LPG surcharge debate in restaurants",
                    "description": "Local story",
                    "source": {"name": "Example A"},
                },
                {
                    "title": "US-Israel and Iran tensions rise",
                    "description": "Regional conflict update",
                    "source": {"name": "Example B"},
                },
            ]
        }
        mock_get.return_value = topic_response

        result = get_top_headlines(topic="iran case us and israel")
        assert "US-Israel and Iran tensions rise" in result
        assert "LPG surcharge debate in restaurants" not in result

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_topic_with_only_irrelevant_results_falls_back_to_general(
        self, mock_get, mock_config
    ):
        mock_config.GNEWS_API_KEY = "test_key"
        topic_irrelevant = MagicMock()
        topic_irrelevant.status_code = 200
        topic_irrelevant.json.return_value = {
            "articles": [
                {
                    "title": "Local sports tournament announced",
                    "description": "No relation",
                    "source": {"name": "Example X"},
                }
            ]
        }
        general = MagicMock()
        general.status_code = 200
        general.json.return_value = {
            "articles": [
                {"title": "General Story", "source": {"name": "Reuters"}},
            ]
        }
        mock_get.side_effect = [topic_irrelevant, general]

        result = get_top_headlines(topic="iran us israel")
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

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_nasa_topic_prefers_official_nasa_rss(self, mock_get, mock_config):
        mock_config.GNEWS_API_KEY = "test_key"
        nasa_rss = MagicMock()
        nasa_rss.status_code = 200
        nasa_rss.text = (
            "<rss><channel>"
            "<item>"
            "<title><![CDATA[NASA confirms Artemis II integrated testing milestone]]></title>"
            "<pubDate>Fri, 04 Apr 2026 12:00:00 +0000</pubDate>"
            "</item>"
            "</channel></rss>"
        )
        nasa_rss.raise_for_status.return_value = None
        mock_get.return_value = nasa_rss

        result = get_top_headlines(topic="nasa artemis ii")

        assert "official nasa updates" in result.lower()
        assert "Artemis II integrated testing milestone" in result
        assert "NASA" in result
        call_url = mock_get.call_args.args[0]
        assert "nasa.gov/rss/dyn/breaking_news.rss" in call_url

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_nasa_topic_falls_back_when_nasa_feed_has_no_relevant_items(
        self, mock_get, mock_config
    ):
        mock_config.GNEWS_API_KEY = "test_key"
        nasa_rss = MagicMock()
        nasa_rss.status_code = 200
        nasa_rss.text = (
            "<rss><channel>"
            "<item>"
            "<title><![CDATA[Earth science briefing update]]></title>"
            "<pubDate>Fri, 04 Apr 2026 12:00:00 +0000</pubDate>"
            "</item>"
            "</channel></rss>"
        )
        nasa_rss.raise_for_status.return_value = None

        gnews_topic = MagicMock()
        gnews_topic.status_code = 200
        gnews_topic.json.return_value = {
            "articles": [
                {"title": "General space coverage", "source": {"name": "Reuters"}},
            ]
        }
        gnews_general = MagicMock()
        gnews_general.status_code = 200
        gnews_general.json.return_value = {
            "articles": [
                {"title": "General space coverage", "source": {"name": "Reuters"}},
            ]
        }
        mock_get.side_effect = [nasa_rss, gnews_topic, gnews_general]

        result = get_top_headlines(topic="nasa artemis ii")

        assert "General space coverage" in result
        assert mock_get.call_count == 3


def test_rank_articles_for_entity_topic_filters_us_only_noise() -> None:
    articles = [
        {
            "title": "US inflation cools in latest report",
            "description": "Domestic economy update",
            "source": {"name": "Finance Source"},
        },
        {
            "title": "Iran and Israel exchange strikes overnight",
            "description": "Regional escalation draws US diplomatic response",
            "source": {"name": "World Source"},
        },
    ]
    ranked = _rank_articles_for_topic(articles, topic="war between iran israel and us")
    assert len(ranked) == 1
    assert ranked[0]["title"] == "Iran and Israel exchange strikes overnight"
