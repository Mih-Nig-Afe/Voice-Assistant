"""Tests for news module."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from voice_assistant import news
from voice_assistant.news import (
    _get_conflict_headlines,
    _get_headlines_fallback,
    _rank_articles_for_topic,
    get_cached_article_context,
    get_top_headlines,
)


@pytest.fixture(autouse=True)
def reset_news_cache() -> None:
    news._RECENT_HEADLINE_ITEMS = []
    news._ARTICLE_DETAIL_CACHE = {}


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

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    @patch("voice_assistant.news._get_conflict_headlines")
    def test_conflict_topic_prefers_curated_rss_before_gnews(
        self, mock_conflict, mock_get, mock_config
    ):
        mock_config.GNEWS_API_KEY = "test_key"
        mock_conflict.return_value = (
            "Here are the latest curated conflict headlines on Iran Israel war:\n"
            "1. Iran and Israel exchange strikes overnight (BBC News, 2026-04-04)"
        )

        result = get_top_headlines(topic="iran israel war")

        assert "curated conflict headlines" in result.lower()
        mock_conflict.assert_called_once_with(topic="iran israel war", count=5)
        mock_get.assert_not_called()

    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    @patch("voice_assistant.news._get_conflict_headlines")
    def test_conflict_topic_falls_back_to_gnews_when_curated_mix_empty(
        self, mock_conflict, mock_get, mock_config
    ):
        mock_config.GNEWS_API_KEY = "test_key"
        mock_conflict.return_value = ""
        topic_response = MagicMock()
        topic_response.status_code = 200
        topic_response.json.return_value = {
            "articles": [
                {
                    "title": "Iran and Israel conflict story",
                    "description": "Regional conflict update",
                    "source": {"name": "Reuters"},
                },
            ]
        }
        mock_get.return_value = topic_response

        result = get_top_headlines(topic="iran israel war")

        assert "Iran and Israel conflict story" in result
        mock_conflict.assert_called_once_with(topic="iran israel war", count=5)
        assert mock_get.call_count == 1

    @patch("voice_assistant.news._get_nasa_headlines", return_value="")
    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_cached_article_context_uses_api_summary_and_content(
        self, mock_get, mock_config, mock_nasa
    ):
        mock_config.GNEWS_API_KEY = "test_key"
        topic_response = MagicMock()
        topic_response.status_code = 200
        topic_response.json.return_value = {
            "articles": [
                {
                    "title": "Artemis II mission enters final checks",
                    "description": "NASA says the crewed moon mission is moving into final integrated checks.",
                    "content": "Engineers completed spacecraft integration and the crew continues training ahead of flight.",
                    "url": "",
                    "source": {"name": "NASA"},
                    "publishedAt": "2026-04-04T12:00:00Z",
                }
            ]
        }
        mock_get.return_value = topic_response

        get_top_headlines(topic="artemis ii")
        context = get_cached_article_context(
            "Artemis II mission enters final checks", "NASA"
        )

        assert "crewed moon mission" in context["summary"].lower()
        assert "spacecraft integration" in context["excerpt"].lower()
        assert context["source"] == "NASA"
        assert context["date_label"] == "2026-04-04"

    @patch("voice_assistant.news._get_nasa_headlines", return_value="")
    @patch("voice_assistant.news.Config")
    @patch("voice_assistant.news.requests.get")
    def test_cached_article_context_fetches_article_excerpt_from_url(
        self, mock_get, mock_config, mock_nasa
    ):
        mock_config.GNEWS_API_KEY = "test_key"
        topic_response = MagicMock()
        topic_response.status_code = 200
        topic_response.json.return_value = {
            "articles": [
                {
                    "title": "Artemis II mission enters final checks",
                    "description": "NASA says the crewed moon mission is moving into final integrated checks.",
                    "content": "",
                    "url": "https://example.com/artemis-ii",
                    "source": {"name": "NASA"},
                    "publishedAt": "2026-04-04T12:00:00Z",
                }
            ]
        }
        article_response = MagicMock()
        article_response.status_code = 200
        article_response.url = "https://example.com/artemis-ii"
        article_response.text = """
            <html>
              <head>
                <meta property="og:description" content="NASA says Artemis II is moving through final launch preparations." />
              </head>
              <body>
                <article>
                  <p>Engineers completed a fresh round of integrated vehicle checks before the mission enters its final launch campaign.</p>
                  <p>The crew is continuing simulations and procedures training while teams review readiness data.</p>
                </article>
              </body>
            </html>
        """
        article_response.raise_for_status.return_value = None
        topic_response.raise_for_status.return_value = None
        mock_get.side_effect = [topic_response, article_response]

        get_top_headlines(topic="artemis ii")
        context = get_cached_article_context(
            "Artemis II mission enters final checks", "NASA"
        )

        assert "final launch preparations" in context["summary"].lower()
        assert "integrated vehicle checks" in context["excerpt"].lower()
        assert "continuing simulations" in context["excerpt"].lower()
        assert mock_get.call_count == 2


@patch("voice_assistant.news._fetch_rss_entries")
def test_curated_conflict_headlines_dedupe_and_filter_relevant_items(
    mock_fetch_rss_entries,
) -> None:
    def fake_entries(source_name: str, url: str) -> list[dict]:
        if source_name == "BBC News":
            return [
                {
                    "title": "Iran and Israel exchange strikes overnight",
                    "summary": "Regional fighting continues",
                    "source": source_name,
                    "published_at": datetime(2026, 4, 4, tzinfo=timezone.utc),
                    "published_sort": datetime(2026, 4, 4, tzinfo=timezone.utc).timestamp(),
                    "date_label": "2026-04-04",
                },
                {
                    "title": "London marathon route expands",
                    "summary": "City event update",
                    "source": source_name,
                    "published_at": datetime(2026, 4, 4, tzinfo=timezone.utc),
                    "published_sort": datetime(2026, 4, 4, tzinfo=timezone.utc).timestamp(),
                    "date_label": "2026-04-04",
                },
            ]
        if source_name == "NPR":
            return [
                {
                    "title": "Iran and Israel exchange strikes overnight",
                    "summary": "Duplicate cross-source headline",
                    "source": source_name,
                    "published_at": datetime(2026, 4, 4, 1, tzinfo=timezone.utc),
                    "published_sort": datetime(2026, 4, 4, 1, tzinfo=timezone.utc).timestamp(),
                    "date_label": "2026-04-04",
                }
            ]
        if source_name == "Al Jazeera":
            return [
                {
                    "title": "Ceasefire talks continue after Iran Israel escalation",
                    "summary": "Diplomatic efforts intensify",
                    "source": source_name,
                    "published_at": datetime(2026, 4, 4, 2, tzinfo=timezone.utc),
                    "published_sort": datetime(2026, 4, 4, 2, tzinfo=timezone.utc).timestamp(),
                    "date_label": "2026-04-04",
                }
            ]
        return []

    mock_fetch_rss_entries.side_effect = fake_entries

    result = _get_conflict_headlines("iran israel war", count=3)

    assert "curated conflict headlines" in result.lower()
    assert "Iran and Israel exchange strikes overnight" in result
    assert result.count("Iran and Israel exchange strikes overnight") == 1
    assert "Ceasefire talks continue after Iran Israel escalation" in result
    assert "London marathon route expands" not in result


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
