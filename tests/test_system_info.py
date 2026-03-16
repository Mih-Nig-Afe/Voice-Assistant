"""Tests for system info module."""

import platform

from voice_assistant.system_info import get_system_info, get_platform_summary


class TestSystemInfo:
    """Test suite for system information module."""

    def test_get_system_info_has_os(self):
        """Should include operating system name."""
        result = get_system_info()
        assert platform.system() in result

    def test_get_system_info_has_python(self):
        """Should include Python version."""
        result = get_system_info()
        assert "Python" in result

    def test_get_system_info_has_hostname(self):
        """Should include hostname."""
        result = get_system_info()
        assert "Hostname" in result

    def test_get_platform_summary(self):
        """Should return a brief platform description."""
        result = get_platform_summary()
        assert platform.system() in result
        assert "running" in result.lower()

