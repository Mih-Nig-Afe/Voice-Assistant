"""Tests for AI engine module."""

from unittest.mock import patch

from voice_assistant.ai_engine import generate_response, is_available


class TestAIEngine:
    """Test suite for AI engine module."""

    @patch("voice_assistant.ai_engine._generator", None)
    @patch("voice_assistant.ai_engine._initialized", True)
    def test_unavailable_message(self):
        """Should return unavailable message when model not loaded."""
        result = generate_response("hello")
        assert "isn't available" in result.lower()

    @patch("voice_assistant.ai_engine._initialized", True)
    @patch("voice_assistant.ai_engine._generator")
    def test_successful_generation(self, mock_gen):
        """Should return generated text on success."""
        mock_gen.return_value = [{"generated_text": "Hello! How are you?"}]
        result = generate_response("hello")
        assert "Hello" in result

    @patch("voice_assistant.ai_engine._initialized", True)
    @patch("voice_assistant.ai_engine._generator")
    def test_generation_error(self, mock_gen):
        """Should return fallback message on generation error."""
        mock_gen.side_effect = RuntimeError("Model error")
        result = generate_response("hello")
        assert "couldn't" in result.lower() or "try again" in result.lower()

    @patch("voice_assistant.ai_engine._generator", None)
    @patch("voice_assistant.ai_engine._initialized", True)
    def test_is_available_false(self):
        """Should return False when generator is None."""
        assert is_available() is False

