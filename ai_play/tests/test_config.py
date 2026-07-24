import pytest

from ai_play.config import Config


def test_config_has_no_model_or_credential_fields(monkeypatch):
    monkeypatch.delenv("AI_PLAY_" + "API_KEY", raising=False)
    monkeypatch.delenv("AI_PLAY_MODEL", raising=False)

    config = Config.from_env()

    assert config.ws_host == "127.0.0.1"
    assert config.ws_port == 8765
    assert config.wait_timeout_seconds == 30.0
    assert config.stop_timeout_seconds == 5.0
    assert config.max_act_requests == 500
    assert not hasattr(config, "api_key")
    assert not hasattr(config, "model")


def test_config_rejects_non_loopback_host(monkeypatch):
    monkeypatch.setenv("AI_PLAY_WS_HOST", "localhost")

    with pytest.raises(ValueError, match="127.0.0.1"):
        Config.from_env()


def test_config_reads_bounded_mcp_waits(monkeypatch):
    monkeypatch.setenv("AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("AI_PLAY_STOP_TIMEOUT_SECONDS", "2")

    config = Config.from_env()

    assert config.wait_timeout_seconds == 12.5
    assert config.stop_timeout_seconds == 2.0


def test_config_reads_max_act_requests(monkeypatch):
    monkeypatch.setenv("AI_PLAY_MAX_ACT_REQUESTS", "7")

    config = Config.from_env()

    assert config.max_act_requests == 7


@pytest.mark.parametrize(
    "name",
    [
        "AI_PLAY_WS_PORT",
        "AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS",
        "AI_PLAY_MAX_ACT_REQUESTS",
    ],
)
def test_config_rejects_invalid_numeric_environment_values(monkeypatch, name):
    monkeypatch.setenv(name, "not-a-number")

    with pytest.raises(ValueError, match=name):
        Config.from_env()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("AI_PLAY_WS_PORT", "0"),
        ("AI_PLAY_WS_PORT", "65536"),
        ("AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS", "0"),
        ("AI_PLAY_MCP_WAIT_TIMEOUT_SECONDS", "121"),
        ("AI_PLAY_STOP_TIMEOUT_SECONDS", "0"),
        ("AI_PLAY_STOP_TIMEOUT_SECONDS", "31"),
        ("AI_PLAY_MAX_ACT_REQUESTS", "0"),
        ("AI_PLAY_MAX_ACT_REQUESTS", "1000001"),
    ],
)
def test_config_rejects_out_of_range_values(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        Config.from_env()
