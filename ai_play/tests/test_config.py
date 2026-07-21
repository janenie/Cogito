from pathlib import Path

import pytest

from ai_play.config import Config


def test_config_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_PLAY_API_KEY", raising=False)
    with pytest.raises(ValueError, match="AI_PLAY_API_KEY"):
        Config.from_env()


def test_config_reads_base_url_and_key_from_local_api_key_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_PLAY_API_KEY", raising=False)
    monkeypatch.delenv("AI_PLAY_BASE_URL", raising=False)
    Path("api_key.py").write_text(
        '''from openai import OpenAI

raise RuntimeError("this file must not be executed")
client = OpenAI(
    base_url="http://provider.example/v1",
    api_key="local-test-key",
)
''',
        encoding="utf-8",
    )

    config = Config.from_env()

    assert config.base_url == "http://provider.example/v1"
    assert config.api_key == "local-test-key"


def test_environment_overrides_local_api_key_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_PLAY_API_KEY", "environment-key")
    monkeypatch.setenv("AI_PLAY_BASE_URL", "https://environment.example/v1")
    Path("api_key.py").write_text(
        '''client = OpenAI(
    base_url="http://file.example/v1",
    api_key="file-key",
)
''',
        encoding="utf-8",
    )

    config = Config.from_env()

    assert config.base_url == "https://environment.example/v1"
    assert config.api_key == "environment-key"


def test_config_uses_default_log_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.delenv("AI_PLAY_LOG_ROOT", raising=False)

    assert Config.from_env().log_root == Path("~/workspace/cogito_logs").expanduser()


def test_config_expands_log_root_override(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    monkeypatch.setenv("AI_PLAY_LOG_ROOT", "~/custom-cogito-logs")

    assert Config.from_env().log_root == Path("~/custom-cogito-logs").expanduser()


def test_config_uses_safe_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_PLAY_API_KEY", "test-key")
    for name in (
        "AI_PLAY_BASE_URL",
        "AI_PLAY_MODEL",
        "AI_PLAY_WS_HOST",
        "AI_PLAY_WS_PORT",
        "AI_PLAY_REQUEST_TIMEOUT_SECONDS",
        "AI_PLAY_API_MAX_RETRIES",
        "AI_PLAY_DATA_DIR",
        "AI_PLAY_LOG_ROOT",
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
