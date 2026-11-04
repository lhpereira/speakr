import pytest

from speakr_mcp.config import DEFAULT_SCOPES, ConfigError, Settings, effective_scopes

BASE = {"SPEAKR_URL": "https://speakr.test", "SPEAKR_API_TOKEN": "t"}


def test_default_scopes_leave_out_delete_and_share():
    assert Settings.from_env(BASE).scopes == DEFAULT_SCOPES
    assert not DEFAULT_SCOPES & {"delete", "share"}


@pytest.mark.parametrize("url", ["https://speakr.test/", "https://speakr.test/api/v1", "https://speakr.test/api/v1/"])
def test_url_is_normalized(url):
    assert Settings.from_env({**BASE, "SPEAKR_URL": url}).url == "https://speakr.test"


def test_url_keeps_a_subpath():
    assert Settings.from_env({**BASE, "SPEAKR_URL": "https://x.test/speakr/"}).url == "https://x.test/speakr"


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"SPEAKR_API_TOKEN": "t"}, "SPEAKR_URL"),
        ({"SPEAKR_URL": "https://speakr.test"}, "SPEAKR_API_TOKEN"),
        ({**BASE, "SPEAKR_URL": "speakr.test"}, "http"),
        ({**BASE, "SPEAKR_MCP_SCOPES": "read,admin"}, "admin"),
    ],
)
def test_bad_settings_stop_the_start(env, message):
    with pytest.raises(ConfigError, match=message):
        Settings.from_env(env)


def test_scopes_can_be_chosen():
    settings = Settings.from_env({**BASE, "SPEAKR_MCP_SCOPES": " read, delete "})
    assert settings.scopes == {"read", "delete"}


def test_token_stays_out_of_repr():
    assert "s3cret" not in repr(Settings.from_env({**BASE, "SPEAKR_API_TOKEN": "s3cret"}))


@pytest.mark.parametrize(
    ("token_scopes", "expected"),
    [
        (["full"], {"read", "write"}),
        (None, {"read", "write"}),
        (["read"], {"read"}),
        (["read", "delete"], {"read"}),
        (["upload"], set()),
    ],
)
def test_effective_scopes_never_exceed_the_configuration(token_scopes, expected):
    assert effective_scopes(frozenset({"read", "write"}), token_scopes) == expected
