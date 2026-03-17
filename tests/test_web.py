from voice_assistant.web import process_user_query


def test_web_help_command_returns_capabilities() -> None:
    response = process_user_query("help")
    assert "I can help" in response.response
    assert response.should_exit is False


def test_web_exit_command_sets_should_exit() -> None:
    response = process_user_query("bye")
    assert response.should_exit is True
    assert "Goodbye" in response.response


def test_web_empty_message_prompts_user() -> None:
    response = process_user_query("   ")
    assert "Please say or type" in response.response
