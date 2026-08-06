from core.logging_config import scrub_sensitive_data


def test_scrubs_known_sensitive_keys():
    event_dict = {
        "event": "order_submitted",
        "api_secret": "sk_live_supersecret",
        "order_id": "abc123",
    }
    result = scrub_sensitive_data(None, "info", event_dict)

    assert result["api_secret"] == "***REDACTED***"
    assert result["order_id"] == "abc123"  # untouched
    assert result["event"] == "order_submitted"  # untouched


def test_scrub_is_case_insensitive():
    event_dict = {"API_KEY": "abc", "Authorization": "Bearer xyz"}
    result = scrub_sensitive_data(None, "info", event_dict)

    assert result["API_KEY"] == "***REDACTED***"
    assert result["Authorization"] == "***REDACTED***"


def test_scrub_leaves_clean_dict_untouched():
    event_dict = {"symbol": "BTCUSDT", "price": "65000.50"}
    result = scrub_sensitive_data(None, "info", event_dict)

    assert result == event_dict