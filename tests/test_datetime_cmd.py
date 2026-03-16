"""Tests for datetime command module."""

from datetime import datetime

from voice_assistant.datetime_cmd import (
    get_current_date,
    get_current_time,
    get_day_of_week,
    get_full_datetime,
)


class TestDateTimeCommands:
    """Test suite for datetime commands."""

    def test_get_current_time_format(self):
        """Should return a string containing the current time."""
        result = get_current_time()
        assert "current time" in result.lower()
        # Should contain AM or PM
        assert "AM" in result or "PM" in result

    def test_get_current_date_format(self):
        """Should return today's date."""
        result = get_current_date()
        assert "today is" in result.lower()
        # Should contain current year
        assert str(datetime.now().year) in result

    def test_get_day_of_week(self):
        """Should return today's day name."""
        result = get_day_of_week()
        today = datetime.now().strftime("%A")
        assert today in result

    def test_get_full_datetime(self):
        """Should return both date and time."""
        result = get_full_datetime()
        assert "today is" in result.lower()
        assert "time is" in result.lower()

