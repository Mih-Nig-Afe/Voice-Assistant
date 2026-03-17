from unittest.mock import patch

from voice_assistant import web
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


def test_web_weather_phrase_extracts_city() -> None:
    web._pending_weather_city = False
    with patch("voice_assistant.web.get_weather", return_value="Hawassa weather ok"):
        response = process_user_query("tell me weather of hawassa")
    assert "Hawassa weather ok" == response.response


def test_web_weather_follow_up_city_is_understood() -> None:
    web._pending_weather_city = True
    with patch("voice_assistant.web.get_weather", return_value="Hawassa weather ok"):
        response = process_user_query("hawassa")
    assert "Hawassa weather ok" == response.response


def test_web_weather_phrase_with_today_suffix() -> None:
    web._pending_weather_city = False
    with patch(
        "voice_assistant.web.get_weather", return_value="Addis weather ok"
    ) as mocked:
        response = process_user_query("what's weather of addis ababa today")
    mocked.assert_called_once_with("addis ababa")
    assert "Addis weather ok" == response.response


def test_web_city_name_not_misread_as_calculator_intent() -> None:
    web._pending_weather_city = True
    with patch("voice_assistant.web.get_weather", return_value="Addis weather ok"):
        response = process_user_query("addis")
    assert "Addis weather ok" == response.response
