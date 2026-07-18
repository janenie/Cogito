import pytest

from ai_play.config import Config


def test_config_requires_api_key(monkeypatch):
    monkeypatch.delenv("AI_PLAY_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AI_PLAY_API_KEY"):
        Config.from_env()


def test_config_uses_safe_defaults(monkeypatch):
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    config = Config.from_env()
    assert config.base_url == "https://api-cn.freeailab.cn/v1"
    assert config.model == "gemini-3.5-flash"
    assert config.ws_host == "127.0.0.1"
    assert config.ws_port == 8765
    assert config.request_timeout_seconds == 45.0


def test_config_rejects_non_loopback_host(monkeypatch):
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.setenv("AI_PLAY_WS_HOST", "0.0.0.0")
    with pytest.raises(ValueError, match="loopback"):
        Config.from_env()
