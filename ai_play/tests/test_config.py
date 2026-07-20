import pytest

from ai_play.config import Config


def test_config_requires_api_key(monkeypatch):
    monkeypatch.delenv("AI_PLAY_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AI_PLAY_API_KEY"):
        Config.from_env()


def test_config_uses_safe_defaults(monkeypatch):
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    for name in (
        "AI_PLAY_BASE_URL",
        "AI_PLAY_MODEL",
        "AI_PLAY_WS_HOST",
        "AI_PLAY_WS_PORT",
        "AI_PLAY_REQUEST_TIMEOUT_SECONDS",
        "AI_PLAY_API_MAX_RETRIES",
        "AI_PLAY_DATA_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
    config = Config.from_env()
    assert config.base_url == "https://api-cn.freeailab.cn/v1"
    assert config.model == "gemini-3.5-flash"
    assert config.ws_host == "127.0.0.1"
    assert config.ws_port == 8765
    assert config.request_timeout_seconds == 45.0
    assert config.api_max_retries == 2


def test_config_rejects_non_loopback_host(monkeypatch):
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.setenv("AI_PLAY_WS_HOST", "0.0.0.0")
    with pytest.raises(ValueError, match="loopback"):
        Config.from_env()


@pytest.mark.parametrize("host", ["localhost", "::1"])
def test_config_rejects_loopback_aliases(monkeypatch, host):
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.setenv("AI_PLAY_WS_HOST", host)
    with pytest.raises(ValueError, match="127.0.0.1"):
        Config.from_env()


@pytest.mark.parametrize("retries", ["-1", "6", "not-an-integer"])
def test_config_rejects_out_of_range_api_retries(monkeypatch, retries):
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.setenv("AI_PLAY_API_MAX_RETRIES", retries)

    with pytest.raises(ValueError, match="AI_PLAY_API_MAX_RETRIES"):
        Config.from_env()


def test_config_validate_rejects_boolean_api_retries():
    test_key = "test-key"
    with pytest.raises(ValueError, match="AI_PLAY_API_MAX_RETRIES"):
        Config(api_key=test_key, api_max_retries=True).validate()


@pytest.mark.parametrize("retries", ["0", "5"])
def test_config_accepts_api_retry_boundaries(monkeypatch, retries):
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.setenv("AI_PLAY_API_MAX_RETRIES", retries)

    assert Config.from_env().api_max_retries == int(retries)
