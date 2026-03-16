"""Tests for command routing module."""

from voice_assistant.commands import register, route, list_commands


class TestCommandRouting:
    """Test suite for command registry and routing."""

    def test_route_weather_command(self):
        """Should match weather keyword."""
        handler, keyword = route("What's the weather today?")
        assert handler is not None
        assert keyword == "weather"

    def test_route_exit_command(self):
        """Should match bye keyword."""
        handler, keyword = route("bye")
        assert handler is not None
        assert keyword == "bye"

    def test_route_wikipedia_command(self):
        """Should match 'tell me about' keyword."""
        handler, keyword = route("tell me about Python")
        assert handler is not None
        assert keyword == "tell me about"

    def test_route_unknown_command(self):
        """Should return None for unrecognized commands."""
        handler, keyword = route("xyzrandomcommand12345")
        assert handler is None
        assert keyword == ""

    def test_list_commands_not_empty(self):
        """Should have registered commands."""
        cmds = list_commands()
        assert len(cmds) > 0

    def test_route_case_insensitive(self):
        """Routing should be case insensitive."""
        handler, _ = route("WEATHER forecast please")
        assert handler is not None

