"""Tests for conversation memory module."""

from voice_assistant.conversation import ConversationMemory


class TestConversationMemory:
    """Test suite for conversation memory."""

    def test_add_user_message(self):
        """Should store user messages."""
        mem = ConversationMemory()
        mem.add_user_message("Hello")
        assert mem.message_count == 1

    def test_add_assistant_message(self):
        """Should store assistant messages."""
        mem = ConversationMemory()
        mem.add_assistant_message("Hi there!")
        assert mem.message_count == 1

    def test_message_count(self):
        """Should track total messages."""
        mem = ConversationMemory()
        mem.add_user_message("Hello")
        mem.add_assistant_message("Hi!")
        mem.add_user_message("How are you?")
        assert mem.message_count == 3

    def test_clear(self):
        """Should clear all messages."""
        mem = ConversationMemory()
        mem.add_user_message("Hello")
        mem.add_assistant_message("Hi!")
        mem.clear()
        assert mem.message_count == 0

    def test_max_history_trim(self):
        """Should trim to max history size."""
        mem = ConversationMemory(max_history=3)
        for i in range(5):
            mem.add_user_message(f"Message {i}")
        assert mem.message_count == 3

    def test_get_context_string(self):
        """Should format context as readable string."""
        mem = ConversationMemory()
        mem.add_user_message("What's the weather?")
        mem.add_assistant_message("It's sunny in London.")
        context = mem.get_context_string()
        assert "User:" in context
        assert "Miehab:" in context
        assert "weather" in context.lower()

    def test_get_messages_for_api(self):
        """Should return list of dicts with role and content."""
        mem = ConversationMemory()
        mem.add_user_message("Hello")
        mem.add_assistant_message("Hi!")
        msgs = mem.get_messages_for_api()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "Hi!"

    def test_get_messages_for_api_limit(self):
        """Should limit to last_n messages."""
        mem = ConversationMemory()
        for i in range(10):
            mem.add_user_message(f"msg {i}")
        msgs = mem.get_messages_for_api(last_n=3)
        assert len(msgs) == 3

    def test_context_string_empty(self):
        """Should return empty string when no history."""
        mem = ConversationMemory()
        assert mem.get_context_string() == ""

