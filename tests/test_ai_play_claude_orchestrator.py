import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = REPO_ROOT / "tools" / "ai_play_claude_orchestrator.py"


def load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_claude_orchestrator",
        ORCHESTRATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_claude_provider_env_keeps_only_explicit_service_keys(tmp_path):
    orchestrator = load_orchestrator()
    settings = tmp_path / "settings.local.json"
    settings.write_text(
        json.dumps(
            {
                "env": {
                    "ANTHROPIC_AUTH_TOKEN": "fixture-token",
                    "ANTHROPIC_BASE_URL": "https://example.invalid",
                    "ANTHROPIC_MODEL": "claude-test",
                    "ANTHROPIC_SMALL_FAST_MODEL": "claude-small-test",
                    "OPENAI_API_KEY": "must-drop",
                    "AI_PLAY_LOG_ROOT": "/must/drop",
                },
                "hooks": {"PreToolUse": ["must-drop"]},
                "permissions": {"allow": ["Bash"]},
            }
        ),
        encoding="utf-8",
    )

    assert orchestrator.load_claude_provider_env(settings) == {
        "ANTHROPIC_AUTH_TOKEN": "fixture-token",
        "ANTHROPIC_BASE_URL": "https://example.invalid",
        "ANTHROPIC_MODEL": "claude-test",
        "ANTHROPIC_SMALL_FAST_MODEL": "claude-small-test",
    }


def test_temporary_claude_player_config_is_private_and_removed(tmp_path):
    orchestrator = load_orchestrator()
    provider_env = {
        "ANTHROPIC_AUTH_TOKEN": "fixture-token",
        "ANTHROPIC_BASE_URL": "https://example.invalid",
    }

    with orchestrator.temporary_claude_player_config(
        provider_env,
        "http://127.0.0.1:8766/mcp",
    ) as config:
        assert config.root.stat().st_mode & 0o777 == 0o700
        assert config.settings_path.stat().st_mode & 0o777 == 0o600
        assert config.mcp_path.stat().st_mode & 0o777 == 0o600
        assert json.loads(config.settings_path.read_text(encoding="utf-8")) == {
            "env": provider_env
        }
        assert json.loads(config.mcp_path.read_text(encoding="utf-8")) == {
            "mcpServers": {
                "cogito_ai_play": {
                    "type": "http",
                    "url": "http://127.0.0.1:8766/mcp",
                }
            }
        }
        root = config.root

    assert not root.exists()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "root must be a JSON object"),
        ({}, "must contain an env object"),
        ({"env": []}, "must contain an env object"),
        ({"env": {"ANTHROPIC_AUTH_TOKEN": 7}}, "must be a non-empty string"),
        ({"env": {"ANTHROPIC_AUTH_TOKEN": ""}}, "must be a non-empty string"),
        ({"env": {"ANTHROPIC_MODEL": "claude-test"}}, "must provide"),
        (
            {
                "env": {
                    "ANTHROPIC_AUTH_TOKEN": "fixture-token",
                    "ANTHROPIC_BASE_URL": "http://example.invalid",
                }
            },
            "must use https",
        ),
    ],
)
def test_load_claude_provider_env_rejects_invalid_settings(
    tmp_path,
    payload,
    message,
):
    orchestrator = load_orchestrator()
    settings = tmp_path / "settings.local.json"
    settings.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        orchestrator.load_claude_provider_env(settings)


def test_load_claude_provider_env_rejects_missing_or_malformed_file(tmp_path):
    orchestrator = load_orchestrator()
    missing = tmp_path / "missing.json"

    with pytest.raises(ValueError, match="missing Claude settings"):
        orchestrator.load_claude_provider_env(missing)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid Claude settings"):
        orchestrator.load_claude_provider_env(malformed)


def test_temporary_claude_player_config_cleans_up_after_error():
    orchestrator = load_orchestrator()

    with pytest.raises(RuntimeError, match="fixture failure"):
        with orchestrator.temporary_claude_player_config(
            {"ANTHROPIC_API_KEY": "fixture-key"},
            "http://127.0.0.1:8766/mcp",
        ) as config:
            root = config.root
            raise RuntimeError("fixture failure")

    assert not root.exists()
