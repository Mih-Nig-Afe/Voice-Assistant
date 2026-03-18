"""Tests for AI engine module."""

import pytest
from unittest.mock import patch, MagicMock

from voice_assistant import ai_engine
from voice_assistant.config import Config
from voice_assistant.ai_engine import generate_response, is_available, get_backend_name


@pytest.fixture(autouse=True)
def reset_model_runtime_state() -> None:
    """Reset per-process model health trackers between tests."""
    ai_engine._MODEL_FAILURE_COUNTS.clear()
    ai_engine._MODEL_EMPTY_COUNTS.clear()
    ai_engine._MODEL_BLOCKLIST.clear()


class TestAIEngine:
    """Test suite for AI engine module."""

    @patch("voice_assistant.ai_engine._backend", "none")
    @patch("voice_assistant.ai_engine._initialized", True)
    def test_unavailable_message(self):
        """Should return unavailable message when no backend loaded."""
        result = generate_response("hello")
        assert "isn't available" in result.lower() or "groq_api_key" in result.lower()

    @patch("voice_assistant.ai_engine._backend", "none")
    @patch("voice_assistant.ai_engine._initialized", True)
    def test_is_available_false(self):
        """Should return False when no backend available."""
        assert is_available() is False

    @patch("voice_assistant.ai_engine._backend", "groq")
    @patch("voice_assistant.ai_engine._initialized", True)
    def test_get_backend_name_groq(self):
        """Should return 'groq' when Groq is active."""
        assert get_backend_name() == "groq"

    @patch("voice_assistant.ai_engine._backend", "huggingface")
    @patch("voice_assistant.ai_engine._initialized", True)
    @patch("voice_assistant.ai_engine._hf_generator")
    def test_huggingface_generation(self, mock_gen):
        """Should return generated text via HuggingFace fallback."""
        mock_gen.return_value = [{"generated_text": "Hello! How are you?"}]
        result = generate_response("hello")
        assert "Hello" in result

    @patch("voice_assistant.ai_engine._backend", "huggingface")
    @patch("voice_assistant.ai_engine._initialized", True)
    @patch("voice_assistant.ai_engine._hf_generator")
    def test_huggingface_error(self, mock_gen):
        """Should return fallback message on HuggingFace error."""
        mock_gen.side_effect = RuntimeError("Model error")
        result = generate_response("hello")
        assert "couldn't" in result.lower() or "try again" in result.lower()

    @patch("voice_assistant.ai_engine._backend", "groq")
    @patch("voice_assistant.ai_engine._initialized", True)
    @patch("voice_assistant.ai_engine._groq_client")
    def test_groq_generation(self, mock_client):
        """Should return generated text via Groq API."""
        mock_choice = MagicMock()
        mock_choice.message.content = "I'm doing great, thanks!"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        result = generate_response("How are you?")
        assert "doing great" in result.lower()

    @patch("voice_assistant.ai_engine._backend", "groq")
    @patch("voice_assistant.ai_engine._initialized", True)
    @patch("voice_assistant.ai_engine._groq_client")
    def test_groq_with_history(self, mock_client):
        """Should pass conversation history to Groq."""
        mock_choice = MagicMock()
        mock_choice.message.content = "Based on our conversation..."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = generate_response("Continue", conversation_history=history)
        assert result  # Should return something

        # Verify history was passed
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
        assert len(messages) >= 3  # system + history + new prompt

    @patch("voice_assistant.ai_engine._backend", "groq")
    @patch("voice_assistant.ai_engine._initialized", True)
    @patch("voice_assistant.ai_engine._groq_client")
    def test_groq_error(self, mock_client):
        """Should handle Groq API errors gracefully."""
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        result = generate_response("hello")
        assert "response right now" in result.lower() or "try again" in result.lower()

    @patch("voice_assistant.ai_engine._backend", "groq")
    @patch("voice_assistant.ai_engine._initialized", True)
    @patch("voice_assistant.ai_engine._groq_client")
    def test_groq_falls_back_to_secondary_model_on_empty_primary(self, mock_client):
        first = MagicMock()
        first.choices = [MagicMock(message=MagicMock(content=""))]
        second = MagicMock()
        second.choices = [MagicMock(message=MagicMock(content="Fallback response"))]
        mock_client.chat.completions.create.side_effect = [first, second]

        result = generate_response("hello")
        assert "fallback response" in result.lower()
        assert mock_client.chat.completions.create.call_count == 2

    @patch("voice_assistant.ai_engine._backend", "groq")
    @patch("voice_assistant.ai_engine._initialized", True)
    @patch("voice_assistant.ai_engine._groq_client")
    def test_groq_blocks_tool_calling_primary_model_and_uses_fallback(self, mock_client):
        tool_error = Exception(
            "Error code: 400 - Tool choice is none, but model called a tool"
        )
        fallback = MagicMock()
        fallback.choices = [MagicMock(message=MagicMock(content="Fallback answer"))]
        mock_client.chat.completions.create.side_effect = [tool_error, fallback]

        result = generate_response("weather")
        assert "fallback answer" in result.lower()
        assert Config.AI_MODEL in ai_engine._MODEL_BLOCKLIST

        second_response = MagicMock()
        second_response.choices = [MagicMock(message=MagicMock(content="Second answer"))]
        mock_client.chat.completions.create.side_effect = [second_response]
        second = generate_response("another question")
        assert "second answer" in second.lower()
        assert mock_client.chat.completions.create.call_count == 3
