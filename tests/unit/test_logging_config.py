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


def test_scrub_catches_key_variants_not_just_exact_matches():
    """
    Regression test for docs/risk_register.md (2026-08-06): the old
    exact-match check would have let "apiKey", "my_api_secret", and
    "AUTH_TOKEN_2" all slip through unredacted, since none of those
    exactly equal an entry in SENSITIVE_KEYS.
    """
    event_dict = {
        "apiKey": "sk_live_abc123",
        "my_api_secret": "sk_live_def456",
        "AUTH_TOKEN_2": "Bearer xyz789",
        "symbol": "BTCUSDT",  # should stay untouched
    }
    result = scrub_sensitive_data(None, "info", event_dict)

    assert result["apiKey"] == "***REDACTED***"
    assert result["my_api_secret"] == "***REDACTED***"
    assert result["AUTH_TOKEN_2"] == "***REDACTED***"
    assert result["symbol"] == "BTCUSDT"


def test_scrub_against_realistic_secret_values():
    """
    Regression test for docs/risk_register.md (2026-08-06): redaction
    had only ever been tested against empty/placeholder strings, not
    values that actually look like real credentials.
    """
    event_dict = {
        "database_url": "postgresql+asyncpg://tsdbadmin:gee4xcdpzs1smd3g@s7pd80z8u1.lzgubwg89f.tsdb.cloud.timescale.com:38061/tsdb",
        "binance_testnet_api_secret": "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6",
        "signature": "3045022100f3a8b1c2d4e5f6a7b8c9d0e1f2a3b4c5",
    }
    result = scrub_sensitive_data(None, "info", event_dict)

    assert result["database_url"] == "***REDACTED***"
    assert result["binance_testnet_api_secret"] == "***REDACTED***"
    assert result["signature"] == "***REDACTED***"
    # None of the real secret text should survive anywhere in the output
    assert "gee4xcdpzs1smd3g" not in str(result)
    assert "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6" not in str(result)