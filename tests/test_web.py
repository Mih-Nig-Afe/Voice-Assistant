import base64
import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from voice_assistant import web
from voice_assistant.web import app, process_user_query


@pytest.fixture(autouse=True)
def reset_web_runtime_state() -> None:
    web._pending_weather_city = False
    web._last_weather_city = ""
    web._last_news_topic = ""
    web._last_news_headline_response = ""
    web._last_selected_headline_index = 0
    web._last_selected_headline_title = ""
    web._last_selected_headline_source = ""


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
    with patch(
        "voice_assistant.web.get_weather", return_value="Addis weather ok"
    ) as mocked:
        response = process_user_query("what's weather of addis ababa today")
    mocked.assert_called_once_with("addis ababa")
    assert "Addis weather ok" == response.response


def test_web_weather_update_without_city_prompts_for_city_instead_of_using_going() -> None:
    with patch("voice_assistant.web.get_weather") as mocked:
        response = process_user_query("Update me on how the weather is going.")
    mocked.assert_not_called()
    assert "which city should i check" in response.response.lower()


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


def test_web_weather_follow_up_with_what_about_phrase_is_normalized() -> None:
    web._pending_weather_city = True
    with patch("voice_assistant.web.get_weather", return_value="Hawassa weather ok") as mocked:
        response = process_user_query("What about Hawassa?")
    mocked.assert_called_once_with("hawassa")
    assert response.response == "Hawassa weather ok"


def test_web_weather_follow_up_with_no_city_tokens_prompts_again() -> None:
    web._pending_weather_city = True
    with patch("voice_assistant.web.get_weather") as mocked:
        response = process_user_query("location where is the")
    mocked.assert_not_called()
    assert "Please tell me the city name" in response.response


def test_web_weather_follow_up_with_conversational_noise_prompts_again() -> None:
    web._pending_weather_city = True
    with patch("voice_assistant.web.get_weather") as mocked:
        response = process_user_query("i'm kinda feeling too")
    mocked.assert_not_called()
    assert "Please tell me the city name" in response.response


def test_web_clear_history_not_misread_as_pending_weather_city() -> None:
    web._pending_weather_city = True
    with patch("voice_assistant.web.get_weather") as mocked:
        response = process_user_query("clear history")
    mocked.assert_not_called()
    assert "cleared our conversation history" in response.response.lower()
    assert web._pending_weather_city is False


def test_web_hot_question_uses_explicit_city_reference() -> None:
    with patch(
        "voice_assistant.web.get_weather", return_value="Hawassa weather ok"
    ) as mocked:
        response = process_user_query(
            "Could you tell me how hot it is here in Hawassa?"
        )
    mocked.assert_called_once_with("hawassa")
    assert response.response == "Hawassa weather ok"


def test_web_hot_question_uses_last_weather_city_context() -> None:
    web._last_weather_city = "hawassa"
    with patch(
        "voice_assistant.web.get_weather", return_value="Hawassa weather ok"
    ) as mocked:
        response = process_user_query("How hot is it now?")
    mocked.assert_called_once_with("hawassa")
    assert response.response == "Hawassa weather ok"


def test_web_hot_followup_uses_city_from_prior_hot_statement() -> None:
    with patch(
        "voice_assistant.web.get_weather", return_value="Hawassa weather ok"
    ) as mocked:
        process_user_query("It's kinda hot here in Hawassa today.")
        response = process_user_query("Could you check me how old is it?")
    mocked.assert_called_once_with("hawassa")
    assert response.response == "Hawassa weather ok"


def test_web_weather_hot_descriptor_without_city_prompts_for_city() -> None:
    with patch("voice_assistant.web.get_weather") as mocked:
        response = process_user_query(
            "Yeah, it's like I just wanna sleep but like the weather is too hot like too hot."
        )
    mocked.assert_not_called()
    assert "which city should i check" in response.response.lower()


def test_web_weather_city_reference_inside_sentence_is_detected() -> None:
    with patch(
        "voice_assistant.web.get_weather", return_value="Hawassa weather ok"
    ) as mocked:
        response = process_user_query(
            "Now currently I'm in Hawassa and the weather is kinda hot. Could you check it for me?"
        )
    mocked.assert_called_once_with("hawassa")
    assert response.response == "Hawassa weather ok"


def test_web_weather_comfort_followup_is_interpreted_humanly() -> None:
    web._last_weather_city = "hawassa"
    with patch(
        "voice_assistant.web.get_weather",
        return_value="Hawassa weather: light rain, 19.97°C, feels like 19.9°C.",
    ) as mocked:
        response = process_user_query(
            "So is that kinda hot? Is that why I'm feeling so uncomfy?"
        )
    mocked.assert_called_once_with("hawassa")
    assert "not truly hot" in response.response.lower()
    assert (
        "humidity" in response.response.lower()
        or "airflow" in response.response.lower()
    )


def test_web_weather_comfort_comparison_does_not_fall_back_to_detail_mode() -> None:
    web._last_weather_city = "hawassa"
    with patch(
        "voice_assistant.web.get_weather",
        return_value="Hawassa weather: light rain, 19.97°C, feels like 19.9°C.",
    ) as mocked:
        response = process_user_query(
            "So is it kind of hot or warm or just a moderate temperature?"
        )
    mocked.assert_called_once_with("hawassa")
    assert "In Hawassa right now:" not in response.response
    assert "mild" in response.response.lower() or "warm" in response.response.lower()


def test_web_weather_detail_request_returns_detail_style_response() -> None:
    with patch(
        "voice_assistant.web.get_weather",
        return_value="Hawassa weather: light rain, 19.97°C, feels like 19.9°C.",
    ) as mocked:
        response = process_user_query("Give me weather details for Hawassa.")
    mocked.assert_called_once_with("hawassa")
    assert response.response.startswith("In Hawassa right now:")
    assert "feels like 19.9°C" in response.response


def test_web_weather_happening_question_gets_explanatory_response() -> None:
    with patch(
        "voice_assistant.web.get_weather",
        return_value="Hawassa weather: light rain, 19.97°C, feels like 19.9°C.",
    ) as mocked:
        response = process_user_query(
            "I just moved back to Hawassa and it's kinda hot here. What is happening here?"
        )
    mocked.assert_called_once_with("hawassa")
    assert "In Hawassa" in response.response
    assert "19.9°C" in response.response


def test_web_news_generic_phrase_uses_general_headlines() -> None:
    with patch(
        "voice_assistant.web.get_top_headlines", return_value="Top news"
    ) as mocked:
        response = process_user_query("Tell me your news.")
    mocked.assert_called_once_with(None)
    assert response.response == "Top news"


def test_web_ambiguous_update_phrase_does_not_force_news_topic() -> None:
    with (
        patch("voice_assistant.web.get_top_headlines") as mocked_news,
        patch(
            "voice_assistant.web.generate_response",
            return_value="Do you mean weather updates or wallet news updates?",
        ) as mocked_ai,
    ):
        response = process_user_query("And just update me on how the wallet is going.")
    mocked_news.assert_not_called()
    mocked_ai.assert_called_once()
    assert "weather updates or wallet news" in response.response.lower()


def test_web_news_noise_phrase_extracts_clean_topic_keywords() -> None:
    with patch(
        "voice_assistant.web.get_top_headlines", return_value="Top news"
    ) as mocked:
        response = process_user_query(
            "Common world-news terms may include Iran, Israel, US, and USA."
        )
    mocked.assert_called_once_with("iran israel us")
    assert response.response == "Top news"


def test_web_news_headline_reference_followup_summarizes_selected_topic() -> None:
    web._last_news_headline_response = (
        "Here are the latest headlines:\n"
        "1. Story one (Source A)\n"
        "2. Story two (Source B)\n"
        "3. Story three (Source C)\n"
        "4. Story four (Source D)\n"
        "5. Iran strikes Tel Aviv with cluster warheads (CNA)"
    )
    with (
        patch(
            "voice_assistant.web.get_top_headlines",
            return_value=(
                "Here are the latest headlines on iran strikes:\n"
                "1. Regional escalation continues overnight (Source X)"
            ),
        ) as mocked_news,
        patch(
            "voice_assistant.web._summarize_news_update",
            return_value="Focused Iran strikes update.",
        ) as mocked_summary,
    ):
        response = process_user_query("More about the headline 5, the Iran strikes.")
    mocked_news.assert_called_once_with("iran strikes")
    mocked_summary.assert_called_once()
    assert response.response == "Focused Iran strikes update."


def test_web_news_headline_reference_understands_first_line_phrase() -> None:
    web._last_news_headline_response = (
        "Here are the latest curated conflict headlines on iran israel us:\n"
        "1. Iranians are leaving the country just to get internet (NPR, 2026-04-03)\n"
        "2. Iran war live: US-Israel attacks hit petrochemical, nuclear sites in Iran (Al Jazeera, 2026-04-04)"
    )
    with patch(
        "voice_assistant.web.generate_response",
        return_value=(
            "The first headline says some Iranians are leaving the country to get internet access, "
            "but details are still limited from that single headline."
        ),
    ) as mocked_generate:
        response = process_user_query("More on the first line.")
    mocked_generate.assert_called_once()
    assert "first headline says" in response.response.lower()


def test_web_news_headline_reference_reuses_selected_headline_for_more_on_it() -> None:
    web._last_news_headline_response = (
        "Here are the latest curated conflict headlines on iran israel us:\n"
        "1. Iranians are leaving the country just to get internet (NPR, 2026-04-03)\n"
        "2. Iran war live: US-Israel attacks hit petrochemical, nuclear sites in Iran (Al Jazeera, 2026-04-04)"
    )
    web._last_selected_headline_index = 1
    web._last_selected_headline_title = "Iranians are leaving the country just to get internet"
    web._last_selected_headline_source = "NPR, 2026-04-03"
    with patch(
        "voice_assistant.web.generate_response",
        return_value="That first headline is about Iranians leaving the country to access internet service.",
    ) as mocked_generate:
        response = process_user_query("More on it.")
    mocked_generate.assert_called_once()
    assert "internet service" in response.response.lower()


def test_web_selected_headline_deep_dive_uses_cached_article_context() -> None:
    web._last_news_headline_response = (
        "Here are the latest curated conflict headlines on iran israel us:\n"
        "1. Iranians are leaving the country just to get internet (NPR, 2026-04-03)\n"
        "2. Iran war live: US-Israel attacks hit petrochemical, nuclear sites in Iran (Al Jazeera, 2026-04-04)"
    )
    with (
        patch(
            "voice_assistant.web.get_cached_article_context",
            return_value={
                "title": "Iranians are leaving the country just to get internet",
                "source": "NPR",
                "source_label": "NPR, 2026-04-03",
                "summary": "People are crossing borders to reconnect after severe internet restrictions.",
                "excerpt": "The report says families are traveling temporarily so they can contact relatives and access blocked services.",
            },
        ) as mocked_context,
        patch(
            "voice_assistant.web.generate_response",
            return_value=(
                "According to NPR, people are temporarily leaving the country because internet restrictions are severe. "
                "The report says they are trying to reconnect with relatives and access blocked services."
            ),
        ) as mocked_generate,
    ):
        response = process_user_query("More on the first line.")
    mocked_context.assert_called_once()
    mocked_generate.assert_called_once()
    assert "reconnect with relatives" in response.response.lower()


def test_web_news_headline_reference_handles_first_hit_on_the_news_phrase() -> None:
    web._last_news_headline_response = (
        "Here are the latest curated conflict headlines on iran israel us:\n"
        "1. Iranians are leaving the country just to get internet (NPR, 2026-04-03)\n"
        "2. Iran war live: US-Israel attacks hit petrochemical, nuclear sites in Iran (Al Jazeera, 2026-04-04)"
    )
    with patch(
        "voice_assistant.web.generate_response",
        return_value="The first headline is about Iranians leaving the country just to get internet access.",
    ) as mocked_generate:
        response = process_user_query("This is the first hit on the news.")
    mocked_generate.assert_called_once()
    assert "first headline" in response.response.lower()


def test_web_news_headline_reference_handles_force_head_light_phrase() -> None:
    web._last_news_headline_response = (
        "Here are the latest curated conflict headlines on iran israel us:\n"
        "1. Iranians are leaving the country just to get internet (NPR, 2026-04-03)\n"
        "2. Iran war live: US-Israel attacks hit petrochemical, nuclear sites in Iran (Al Jazeera, 2026-04-04)"
    )
    with patch(
        "voice_assistant.web.generate_response",
        return_value="The first headline says Iranians are leaving the country to get internet access.",
    ) as mocked_generate:
        response = process_user_query("Give me more details on the Force Head Light.")
    mocked_generate.assert_called_once()
    assert "first headline says" in response.response.lower()


def test_web_news_headline_reference_followup_handles_general_fallback_payload() -> (
    None
):
    web._last_news_headline_response = (
        "Here are the latest headlines:\n"
        "1. Story one (Source A)\n"
        "2. Story two (Source B)\n"
        "3. Story three (Source C)\n"
        "4. Story four (Source D)\n"
        "5. Iran strikes Tel Aviv with cluster warheads (CNA)"
    )
    with patch(
        "voice_assistant.web.get_top_headlines",
        return_value="Here are the latest headlines:\n1. Unrelated story (Source Z)",
    ) as mocked_news:
        response = process_user_query("More about the headline 5, the Iran strikes.")
    mocked_news.assert_called_once_with("iran strikes")
    assert "do not have enough new related headlines" in response.response.lower()
    assert "headline 5" in response.response.lower()
    assert "iran strikes tel aviv with cluster warheads" in response.response.lower()


def test_web_news_headline_reference_uses_selected_headline_topic_when_query_is_noisy() -> (
    None
):
    web._last_news_headline_response = (
        "Here are the latest headlines:\n"
        "1. Story one (Source A)\n"
        "2. Story two (Source B)\n"
        "3. Iran's army leader vows decisive retaliation for death of security chief (BBC)\n"
        "4. Story four (Source D)\n"
        "5. Story five (Source E)"
    )
    with (
        patch("voice_assistant.web.get_top_headlines") as mocked_news,
        patch(
            "voice_assistant.web.generate_response",
            return_value=(
                "Headline 3 says Iran's army leader is promising decisive retaliation, "
                "but details are still limited from this single headline."
            ),
        ) as mocked_generate,
    ):
        response = process_user_query(
            "Just give me a dip about the headline 3, the Iran's army leader vote."
        )
    mocked_news.assert_not_called()
    mocked_generate.assert_called_once()
    assert "headline 3 says" in response.response.lower()
    assert "details are still limited" in response.response.lower()


def test_web_news_topic_phrase_extracts_clean_topic() -> None:
    with patch(
        "voice_assistant.web.get_top_headlines", return_value="Tech headlines"
    ) as mocked:
        response = process_user_query("What's the latest news about technology?")
    mocked.assert_called_once_with("technology")
    assert response.response == "Tech headlines"


def test_web_news_update_phrase_routes_to_news_lookup() -> None:
    with patch(
        "voice_assistant.web.get_top_headlines", return_value="Iran update"
    ) as mocked:
        response = process_user_query(
            "Give me an update on the Iran case based on the war with US and Israel."
        )
    mocked.assert_called_once_with("iran war us israel")
    assert response.response == "Iran update"


def test_web_what_is_latest_on_topic_prefers_news_over_wiki() -> None:
    with (
        patch(
            "voice_assistant.web.get_top_headlines", return_value="Latest headlines"
        ) as mocked_news,
        patch("voice_assistant.web.get_summary") as mocked_wiki,
    ):
        response = process_user_query("What is the latest on Iran and Israel?")
    mocked_news.assert_called_once_with("iran israel")
    mocked_wiki.assert_not_called()
    assert response.response == "Latest headlines"


def test_web_news_update_request_prefers_summary_style_response() -> None:
    with (
        patch(
            "voice_assistant.web.get_top_headlines",
            return_value=(
                "Here are the latest headlines on iran us israel:\n"
                "1. Headline one (Source A)\n"
                "2. Headline two (Source B)"
            ),
        ) as mocked_news,
        patch(
            "voice_assistant.web._summarize_news_update",
            return_value="Short grounded update.",
        ) as mocked_summary,
    ):
        response = process_user_query("Update me on the Iran and US and Israel war.")
    mocked_news.assert_called_once_with("iran us israel war")
    mocked_summary.assert_called_once()
    assert response.response == "Short grounded update."


def test_web_news_summary_omits_confidence_and_sources_lines_by_default() -> None:
    headline_payload = (
        "Here are the latest headlines on iran us israel:\n"
        "1. Story one (Source A)\n"
        "2. Story two (Source B)\n"
        "3. Story three (Source C)"
    )
    response = web._summarize_news_update(
        "Update me on Iran and Israel.",
        "iran israel",
        headline_payload,
    )
    assert "latest reporting on iran israel" in response.lower()
    assert "one report from source a says story one." in response.lower()
    assert "Confidence:" not in response
    assert "Sources used:" not in response


def test_web_news_summary_uses_ai_rewrite_when_enabled() -> None:
    headline_payload = (
        "Here are the latest headlines on artemis ii:\n"
        "1. Liftoff nears for Artemis II (NASA)\n"
        "2. Crew training continues ahead of launch (Reuters)"
    )
    with patch(
        "voice_assistant.web.generate_response",
        return_value=(
            "NASA's Artemis II update sounds steady so far. "
            "NASA says liftoff is nearing, and Reuters reports the crew is still moving "
            "through launch preparation."
        ),
    ) as mocked_ai:
        response = web._summarize_news_update(
            "Update me on Artemis II.",
            "artemis ii",
            headline_payload,
            allow_ai=True,
        )
    mocked_ai.assert_called_once()
    assert "artemis ii update sounds steady" in response.lower()


def test_web_news_summary_falls_back_when_ai_rewrite_is_unavailable() -> None:
    headline_payload = (
        "Here are the latest headlines on iran us israel:\n"
        "1. Story one (Source A)\n"
        "2. Story two (Source B)\n"
        "3. Story three (Source C)"
    )
    with patch(
        "voice_assistant.web.generate_response",
        return_value="I don't have a response right now. Please try once more.",
    ):
        response = web._summarize_news_update(
            "Update me on Iran and Israel.",
            "iran israel",
            headline_payload,
            allow_ai=True,
        )
    assert "latest reporting on iran israel" in response.lower()


def test_web_news_summary_includes_meta_lines_when_explicitly_requested() -> None:
    headline_payload = (
        "Here are the latest headlines on iran us israel:\n"
        "1. Story one (Source A)\n"
        "2. Story two (Source B)\n"
        "3. Story three (Source C)"
    )
    response = web._summarize_news_update(
        "Update me on Iran and Israel with confidence and sources.",
        "iran israel",
        headline_payload,
    )
    assert "latest reporting on iran israel" in response.lower()
    assert "Confidence:" in response
    assert "Sources used:" in response
    assert "Source A" in response
    assert "Source B" in response


def test_web_news_followup_uses_ai_rewrite_when_enabled() -> None:
    headline_payload = (
        "Here are the latest headlines on iran us israel:\n"
        "1. Officials say strikes continued overnight (Source A)\n"
        "2. Diplomats push for restraint (Source B)"
    )
    with patch(
        "voice_assistant.web.generate_response",
        return_value=(
            "From the current reporting, the fighting is still active. "
            "One headline says strikes continued overnight, while another says diplomats "
            "are pushing for restraint."
        ),
    ) as mocked_ai:
        response = web._answer_news_followup(
            "How is the Iran war going now?",
            "iran israel",
            headline_payload,
            allow_ai=True,
        )
    mocked_ai.assert_called_once()
    assert "fighting is still active" in response.lower()


def test_web_news_followup_detail_prefers_cached_article_context() -> None:
    headline_payload = (
        "Here are the latest official NASA updates on artemis ii:\n"
        "1. Artemis II mission enters final checks (NASA, 2026-04-04)\n"
        "2. Crew continues integrated simulations (NASA, 2026-04-03)"
    )
    with (
        patch(
            "voice_assistant.web.get_cached_article_context",
            return_value={
                "title": "Artemis II mission enters final checks",
                "source": "NASA",
                "source_label": "NASA, 2026-04-04",
                "summary": "NASA says Artemis II is moving through final integrated launch checks.",
                "excerpt": "Engineers completed another round of vehicle testing and the crew is still running mission simulations ahead of launch.",
            },
        ) as mocked_context,
        patch(
            "voice_assistant.web.generate_response",
            return_value=(
                "NASA says Artemis II is now in its final integrated checks. "
                "Engineers have been testing the vehicle again while the crew keeps running mission simulations ahead of launch."
            ),
        ) as mocked_ai,
    ):
        response = web._answer_news_followup(
            "Can you give me more details on Artemis II?",
            "artemis ii",
            headline_payload,
            allow_ai=True,
        )
    mocked_context.assert_called_once_with(
        "Artemis II mission enters final checks", "NASA, 2026-04-04"
    )
    mocked_ai.assert_called_once()
    assert "final integrated checks" in response.lower()


def test_web_news_followup_timing_uses_dates_from_source_metadata() -> None:
    headline_payload = (
        "Here are the latest headlines on artemis ii:\n"
        "1. Liftoff! NASA Launches Astronauts on Historic Artemis Moon Mission (NASA, 2026-04-01)\n"
        "2. NASA's Artemis II Mission Leaves Earth Orbit for Flight around Moon (NASA, 2026-04-03)"
    )
    response = web._answer_news_followup(
        "So when is it launching?",
        "artemis ii",
        headline_payload,
    )
    assert "april 1, 2026" in response.lower()


def test_web_explainer_followup_prefers_explanation_headline_when_available() -> None:
    headline_payload = (
        "Here are the latest curated conflict headlines on iran israel war:\n"
        "1. Iran war live: attacks hit key sites in Iran (Al Jazeera, 2026-04-04)\n"
        "2. Why did US and Israel attack Iran and how long could the war last? (BBC News, 2026-04-03)\n"
        "3. Are Iran-allied paramilitaries dragging Iraq into the war? (DW, 2026-04-03)"
    )
    response = web._answer_news_followup(
        "How did the war between Iran and Israel begin?",
        "iran israel war",
        headline_payload,
    )
    assert "explanation-focused current headline" in response.lower()
    assert "why did us and israel attack iran" in response.lower()


def test_web_current_followup_prefers_live_update_headline_when_available() -> None:
    headline_payload = (
        "Here are the latest curated conflict headlines on iran israel war:\n"
        "1. Why did US and Israel attack Iran and how long could the war last? (BBC News, 2026-04-03)\n"
        "2. Iran war live: attacks hit key sites in Iran (Al Jazeera, 2026-04-04)\n"
        "3. Are Iran-allied paramilitaries dragging Iraq into the war? (DW, 2026-04-03)"
    )
    response = web._answer_news_followup(
        "How is it going now?",
        "iran israel war",
        headline_payload,
    )
    assert "al jazeera" in response.lower()
    assert "attacks hit key sites in iran" in response.lower()


def test_web_precise_news_followup_skips_ai_rewrite() -> None:
    headline_payload = (
        "Here are the latest headlines on artemis ii:\n"
        "1. Liftoff! NASA Launches Astronauts on Historic Artemis Moon Mission (NASA, 2026-04-01)\n"
        "2. NASA's Artemis II Mission Leaves Earth Orbit for Flight around Moon (NASA, 2026-04-03)"
    )
    with patch("voice_assistant.web.generate_response") as mocked_ai:
        response = web._answer_news_followup(
            "So when is it launching?",
            "artemis ii",
            headline_payload,
            allow_ai=True,
        )
    mocked_ai.assert_not_called()
    assert "april 1, 2026" in response.lower()


def test_web_news_followup_begin_question_admits_headlines_do_not_explain_origin() -> None:
    headline_payload = (
        "Here are the latest headlines on iran us israel:\n"
        "1. Officials say strikes continued overnight (Source A)\n"
        "2. Diplomats push for restraint (Source B)"
    )
    response = web._answer_news_followup(
        "How did the war between Iran and Israel begin?",
        "iran israel",
        headline_payload,
    )
    assert "do not explain how it began" in response.lower()


def test_web_news_followup_question_uses_recent_headlines_context() -> None:
    web._last_news_topic = "iran us israel war"
    web._last_news_headline_response = (
        "Here are the latest headlines on iran us israel:\n"
        "1. Story one (Source A)\n"
        "2. Story two (Source B)"
    )
    with (
        patch(
            "voice_assistant.web._answer_news_followup",
            return_value="Direct follow-up answer.",
        ) as mocked_followup,
        patch("voice_assistant.web.get_summary") as mocked_wiki,
    ):
        response = process_user_query("Who is attacking now? Iran, Israel, or US?")
    mocked_followup.assert_called_once()
    mocked_wiki.assert_not_called()
    assert response.response == "Direct follow-up answer."


def test_web_news_followup_with_new_topic_fetches_fresh_headlines() -> None:
    web._last_news_topic = "world"
    web._last_news_headline_response = (
        "Here are the latest headlines:\n"
        "1. General item (Source A)\n"
        "2. Another item (Source B)"
    )
    with (
        patch(
            "voice_assistant.web.get_top_headlines",
            return_value=(
                "Here are the latest headlines on iran israel us:\n"
                "1. Conflict item (Source X)"
            ),
        ) as mocked_news,
        patch(
            "voice_assistant.web._answer_news_followup",
            return_value="Conflict-focused follow-up answer.",
        ) as mocked_followup,
    ):
        response = process_user_query(
            "What about the war between Iran, Israel, and the US?"
        )
    mocked_news.assert_called_once_with("war iran israel us")
    mocked_followup.assert_called_once()
    assert response.response == "Conflict-focused follow-up answer."


def test_web_general_news_request_sets_general_topic_cache() -> None:
    with patch("voice_assistant.web.get_top_headlines", return_value="Top news"):
        response = process_user_query("Tell me your news.")
    assert response.response == "Top news"
    assert web._last_news_topic == "general"


def test_web_news_followup_with_new_topic_after_general_cache_fetches_fresh_headlines() -> (
    None
):
    web._last_news_topic = ""
    web._last_news_headline_response = (
        "Here are the latest headlines:\n"
        "1. General item (Source A)\n"
        "2. Another item (Source B)"
    )
    with (
        patch(
            "voice_assistant.web.get_top_headlines",
            return_value=(
                "Here are the latest headlines on iran israel us:\n"
                "1. Conflict item (Source X)"
            ),
        ) as mocked_news,
        patch(
            "voice_assistant.web._answer_news_followup",
            return_value="Conflict-focused follow-up answer.",
        ) as mocked_followup,
    ):
        response = process_user_query(
            "What about the war between Iran, Israel, and the US?"
        )
    mocked_news.assert_called_once_with("war iran israel us")
    mocked_followup.assert_called_once()
    assert response.response == "Conflict-focused follow-up answer."


def test_web_news_generic_other_headlines_phrase_falls_back_to_general() -> None:
    with patch(
        "voice_assistant.web.get_top_headlines",
        return_value="Here are the latest headlines:\n1. General",
    ) as mocked:
        response = process_user_query("Or look for any other headlines such as more.")
    mocked.assert_called_once_with(None)
    assert "latest headlines" in response.response.lower()


def test_web_news_followup_answer_omits_meta_lines_by_default() -> None:
    payload = (
        "Here are the latest headlines on iran us israel:\n"
        "1. Side A and Side B exchanged strikes (Source A)\n"
        "2. Diplomatic statement follows overnight attacks (Source B)\n"
        "3. Regional military alert raised (Source C)"
    )
    response = web._answer_news_followup(
        "Who is attacking now? Iran, Israel, or US?",
        "iran us israel",
        payload,
    )
    assert "not clearly identified" in response.lower()
    assert "Confidence:" not in response
    assert "Sources used:" not in response


def test_web_news_followup_answer_includes_meta_lines_when_requested() -> None:
    payload = (
        "Here are the latest headlines on iran us israel:\n"
        "1. Side A and Side B exchanged strikes (Source A)\n"
        "2. Diplomatic statement follows overnight attacks (Source B)\n"
        "3. Regional military alert raised (Source C)"
    )
    response = web._answer_news_followup(
        "Who is attacking now? Iran, Israel, or US? Include confidence and sources.",
        "iran us israel",
        payload,
    )
    assert "not clearly identified" in response.lower()
    assert "Confidence:" in response
    assert "Sources used:" in response


def test_web_date_today_question_prefers_datetime_over_wikipedia() -> None:
    with (
        patch(
            "voice_assistant.web.get_current_date",
            return_value="Today is Saturday, April 04, 2026.",
        ) as mocked_date,
        patch("voice_assistant.web.get_summary") as mocked_wiki,
    ):
        response = process_user_query("So what is the date today?")
    mocked_date.assert_called_once()
    mocked_wiki.assert_not_called()
    assert response.response == "Today is Saturday, April 04, 2026."


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


def test_web_transcribe_endpoint_strips_stt_prompt_leak_text() -> None:
    client = TestClient(app)
    sample_audio = b"audio-bytes" * 200
    payload = base64.b64encode(sample_audio).decode("ascii")
    leaked = (
        "Common world-news terms may include Iran, Israel, US, and USA. "
        "Update me on Iran and Israel."
    )
    with patch("voice_assistant.web._transcribe_audio_bytes", return_value=leaked):
        response = client.post(
            "/api/speech/transcribe",
            json={"audio_base64": payload, "mime_type": "audio/webm"},
        )
    assert response.status_code == 200
    assert response.json() == {"transcript": "Update me on Iran and Israel."}


def test_web_incomplete_fragment_prompts_repeat_instead_of_ai_chat() -> None:
    with patch("voice_assistant.web.generate_response") as mocked_ai:
        response = process_user_query("Cameras and...")
    mocked_ai.assert_not_called()
    assert "only caught part of that" in response.response.lower()


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
