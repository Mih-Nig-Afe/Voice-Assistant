import base64
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from voice_assistant import web
from voice_assistant.web import app, process_user_query


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


def test_web_weather_follow_up_with_preposition_is_normalized() -> None:
    web._pending_weather_city = True
    with patch(
        "voice_assistant.web.get_weather", return_value="Shashamani weather ok"
    ) as mocked:
        response = process_user_query("for shashamani")
    mocked.assert_called_once_with("shashamani")
    assert response.response == "Shashamani weather ok"


def test_web_weather_follow_up_with_no_city_tokens_prompts_again() -> None:
    web._pending_weather_city = True
    with patch("voice_assistant.web.get_weather") as mocked:
        response = process_user_query("location where is the")
    mocked.assert_not_called()
    assert "Please tell me the city name" in response.response


def test_web_news_generic_phrase_uses_general_headlines() -> None:
    with patch("voice_assistant.web.get_top_headlines", return_value="Top news") as mocked:
        response = process_user_query("Tell me your news.")
    mocked.assert_called_once_with(None)
    assert response.response == "Top news"


def test_web_news_topic_phrase_extracts_clean_topic() -> None:
    with patch(
        "voice_assistant.web.get_top_headlines", return_value="Tech headlines"
    ) as mocked:
        response = process_user_query("What's the latest news about technology?")
    mocked.assert_called_once_with("technology")
    assert response.response == "Tech headlines"


def test_web_redirects_0_0_0_0_origin_to_127_loopback() -> None:
    client = TestClient(app, base_url="http://0.0.0.0:8000")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "http://127.0.0.1:8000/"


def test_web_static_assets_are_served_with_no_store_cache_headers() -> None:
    client = TestClient(app)
    response = client.get("/static/app.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, max-age=0"


def test_web_transcribe_endpoint_returns_text() -> None:
    client = TestClient(app)
    sample_audio = b"audio-bytes" * 200
    payload = base64.b64encode(sample_audio).decode("ascii")
    with patch(
        "voice_assistant.web._transcribe_audio_bytes", return_value="hello from mic"
    ) as mocked:
        response = client.post(
            "/api/speech/transcribe",
            json={"audio_base64": payload, "mime_type": "audio/webm"},
        )
    assert response.status_code == 200
    assert response.json() == {"transcript": "hello from mic"}
    mocked.assert_called_once()
    assert mocked.call_args.args[0] == sample_audio


def test_web_transcribe_endpoint_rejects_invalid_base64() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/speech/transcribe",
        json={"audio_base64": "not-base64", "mime_type": "audio/webm"},
    )
    assert response.status_code == 400
    assert "base64" in response.json()["detail"].lower()


def test_web_transcribe_endpoint_returns_empty_for_tiny_audio() -> None:
    client = TestClient(app)
    payload = base64.b64encode(b"a").decode("ascii")
    with patch("voice_assistant.web._transcribe_audio_bytes") as mocked:
        response = client.post(
            "/api/speech/transcribe",
            json={"audio_base64": payload, "mime_type": "audio/webm"},
        )
    assert response.status_code == 200
    assert response.json() == {"transcript": ""}
    mocked.assert_not_called()


def test_web_synthesize_endpoint_returns_audio() -> None:
    client = TestClient(app)
    sample = b"\x00\x01\x02\x03"
    with patch(
        "voice_assistant.web._synthesize_text_audio_bytes",
        new=AsyncMock(return_value=sample),
    ) as mocked:
        response = client.post("/api/speech/synthesize", json={"text": "hello there"})
    assert response.status_code == 200
    assert response.json()["audio_base64"] == base64.b64encode(sample).decode("ascii")
    assert response.json()["mime_type"] == "audio/mpeg"
    mocked.assert_awaited_once_with("hello there")


def test_web_synthesize_endpoint_rejects_empty_text() -> None:
    client = TestClient(app)
    response = client.post("/api/speech/synthesize", json={"text": "   "})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_web_synthesize_endpoint_returns_503_on_runtime_unavailable() -> None:
    client = TestClient(app)
    with patch(
        "voice_assistant.web._synthesize_text_audio_bytes",
        new=AsyncMock(side_effect=RuntimeError("tts disabled")),
    ):
        response = client.post("/api/speech/synthesize", json={"text": "hello"})
    assert response.status_code == 503
