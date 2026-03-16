"""Tests for command routing module."""

# Import assistant to trigger command registration
import voice_assistant.assistant  # noqa: F401
from voice_assistant.commands import route, list_commands


class TestCommandRouting:
    """Test suite for command registry and routing."""

    def test_route_weather_command(self):
        handler, keyword = route("What's the weather today?")
        assert handler is not None
        assert keyword == "weather"

    def test_route_exit_command(self):
        handler, keyword = route("bye")
        assert handler is not None
        assert keyword == "bye"

    def test_route_wikipedia_command(self):
        handler, keyword = route("tell me about Python")
        assert handler is not None
        assert keyword == "tell me about"

    def test_route_news_command(self):
        handler, keyword = route("What's the latest news?")
        assert handler is not None
        assert keyword == "latest news"

    def test_route_joke_command(self):
        handler, keyword = route("tell me a joke")
        assert handler is not None
        assert "joke" in keyword

    def test_route_dictionary_command(self):
        handler, keyword = route("define serendipity")
        assert handler is not None
        assert keyword == "define"

    def test_route_calculate_command(self):
        handler, keyword = route("calculate 5 plus 3")
        assert handler is not None
        assert keyword == "calculate"

    def test_route_time_command(self):
        handler, keyword = route("what time is it")
        assert handler is not None

    def test_route_date_command(self):
        handler, keyword = route("what date is it today")
        assert handler is not None

    def test_route_system_info(self):
        handler, keyword = route("system info")
        assert handler is not None

    def test_route_help_command(self):
        handler, keyword = route("help")
        assert handler is not None
        assert keyword == "help"

    def test_route_unknown_command(self):
        handler, keyword = route("xyzrandomcommand12345")
        assert handler is None
        assert keyword == ""

    def test_list_commands_not_empty(self):
        cmds = list_commands()
        assert len(cmds) >= 10  # We have at least 10 registered commands

    def test_route_case_insensitive(self):
        handler, _ = route("WEATHER forecast please")
        assert handler is not None

    def test_route_math_words(self):
        handler, _ = route("5 plus 3")
        assert handler is not None

    def test_route_battery(self):
        handler, _ = route("battery status")
        assert handler is not None
