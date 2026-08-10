import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = REPO_ROOT / "tools" / "ai_play_codex_doubao_orchestrator.py"


def load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_codex_doubao_orchestrator",
        ORCHESTRATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _credential_file(tmp_path, env=None):
    source = tmp_path / "settings.local.json"
    source.write_text(
        json.dumps(
            {
                "env": env
                or {
                    "ANTHROPIC_AUTH_TOKEN": "real-secret",
                    "ANTHROPIC_BASE_URL": "https://yibuapi.com",
                    "UNRELATED": "ignore",
                }
            }
        ),
        encoding="utf-8",
    )
    return source


def test_load_credentials_reads_only_whitelisted_json_fields(tmp_path):
    orchestrator = load_orchestrator()

    credentials = orchestrator.load_doubao_credentials(_credential_file(tmp_path))

    assert credentials.api_key == "real-secret"
    assert credentials.base_url == "https://yibuapi.com/v1"


def test_load_credentials_prefers_auth_token_and_accepts_api_key_fallback(tmp_path):
    orchestrator = load_orchestrator()
    both = _credential_file(
        tmp_path,
        {
            "ANTHROPIC_AUTH_TOKEN": "auth-token",
            "ANTHROPIC_API_KEY": "api-key",
            "ANTHROPIC_BASE_URL": "https://yibuapi.com/v1/",
        },
    )
    assert orchestrator.load_doubao_credentials(both).api_key == "auth-token"

    both.write_text(
        json.dumps(
            {
                "env": {
                    "ANTHROPIC_API_KEY": "fallback",
                    "ANTHROPIC_BASE_URL": "https://yibuapi.com",
                }
            }
        ),
        encoding="utf-8",
    )
    assert orchestrator.load_doubao_credentials(both).api_key == "fallback"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json", "JSON"),
        (json.dumps({}), "env"),
        (json.dumps({"env": {"ANTHROPIC_BASE_URL": "https://yibuapi.com"}}), "token"),
        (
            json.dumps(
                {
                    "env": {
                        "ANTHROPIC_AUTH_TOKEN": "secret",
                        "ANTHROPIC_BASE_URL": "http://yibuapi.com",
                    }
                }
            ),
            "HTTPS",
        ),
        (
            json.dumps(
                {
                    "env": {
                        "ANTHROPIC_AUTH_TOKEN": "secret",
                        "ANTHROPIC_BASE_URL": "https://user@yibuapi.com",
                    }
                }
            ),
            "credentials",
        ),
        (
            json.dumps(
                {
                    "env": {
                        "ANTHROPIC_AUTH_TOKEN": "secret",
                        "ANTHROPIC_BASE_URL": "https://yibuapi.com/other",
                    }
                }
            ),
            "/v1",
        ),
    ],
)
def test_load_credentials_rejects_invalid_files(tmp_path, payload, message):
    source = tmp_path / "settings.local.json"
    source.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_orchestrator().load_doubao_credentials(source)


def test_write_codex_config_targets_loopback_proxy_without_real_secret(tmp_path):
    orchestrator = load_orchestrator()
    path = orchestrator.write_player_codex_doubao_config(
        tmp_path,
        model="doubao-seed-2-1-pro-260628",
        proxy_base_url="http://127.0.0.1:43210/v1",
        mcp_url="http://127.0.0.1:8766/mcp",
        workflow_memory_enabled=True,
    )

    text = path.read_text(encoding="utf-8")
    assert 'model = "doubao-seed-2-1-pro-260628"' in text
    assert 'model_provider = "doubao_proxy"' in text
    assert '[model_providers.doubao_proxy]' in text
    assert 'base_url = "http://127.0.0.1:43210/v1"' in text
    assert 'env_key = "DOUBAO_PROXY_API_KEY"' in text
    assert 'wire_api = "responses"' in text
    assert "model_reasoning_effort" not in text
    assert "real-secret" not in text
    assert 'enabled_tools = ["briefing", "workflow_memory_read", "observe", "act", "workflow_memory_update"]' in text
    assert "shell_tool = false" in text
    assert '"127.0.0.1" = "allow"' in text
    assert path.stat().st_mode & 0o777 == 0o600


def test_write_codex_config_can_disable_awm_tools(tmp_path):
    orchestrator = load_orchestrator()
    path = orchestrator.write_player_codex_doubao_config(
        tmp_path,
        model="doubao-seed-2-1-pro-260628",
        proxy_base_url="http://127.0.0.1:43210/v1",
        mcp_url="http://127.0.0.1:8766/mcp",
        workflow_memory_enabled=False,
    )
    text = path.read_text(encoding="utf-8")
    assert 'enabled_tools = ["briefing", "observe", "act"]' in text
    assert "workflow_memory_read" not in text


def test_build_wrapper_env_contains_real_secret_but_codex_env_does_not(tmp_path):
    orchestrator = load_orchestrator()
    credentials = orchestrator.DoubaoCredentials("real-secret", "https://yibuapi.com/v1")
    wrapper = orchestrator.build_wrapper_env(
        credentials,
        base_env={"PATH": "/safe", "OPENAI_API_KEY": "drop", "HTTPS_PROXY": "drop"},
    )
    codex = orchestrator.build_codex_proxy_env(
        tmp_path,
        "local-proxy-token",
        base_env=wrapper,
    )

    assert wrapper[orchestrator.DOUBAO_UPSTREAM_KEY_ENV] == "real-secret"
    assert wrapper[orchestrator.DOUBAO_UPSTREAM_URL_ENV] == "https://yibuapi.com/v1"
    assert codex["DOUBAO_PROXY_API_KEY"] == "local-proxy-token"
    assert "real-secret" not in repr(codex)
    assert orchestrator.DOUBAO_UPSTREAM_KEY_ENV not in codex
    assert "OPENAI_API_KEY" not in codex
    assert "HTTPS_PROXY" not in codex


def test_parse_args_has_doubao_defaults_and_no_effort_option():
    orchestrator = load_orchestrator()
    args = orchestrator.parse_args([])
    assert args.model == "doubao-seed-2-1-pro-260628"
    assert args.runs == 3
    assert args.workflow_memory == "enabled"
    assert args.max_output_tokens == 8192
    assert args.codex_max_restarts == 8
    assert args.credentials == orchestrator.REPO_ROOT / ".claude/settings.local.json"
    assert not hasattr(args, "reasoning_effort")


def test_restart_prompt_recovers_public_state_for_awm_modes():
    orchestrator = load_orchestrator()
    enabled = orchestrator.build_player_restart_prompt(3, True)
    disabled = orchestrator.build_player_restart_prompt(3, False)
    assert "workflow_memory_read、briefing、observe" in enabled
    assert "completed_runs" in enabled
    assert "workflow_memory_read" not in disabled
    assert "briefing、observe" in disabled


class _FakeStdin:
    def __init__(self):
        self.value = ""
        self.closed = False

    def write(self, value):
        self.value += value

    def close(self):
        self.closed = True


class _FakeProcess:
    def __init__(self):
        self.stdin = _FakeStdin()
        self.stdout = iter(["codex line one\n", "codex line two\n"])
        self.terminated = False

    def wait(self, timeout=None):
        return 17

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True


def test_internal_wrapper_forwards_prompt_output_and_isolates_secret(tmp_path, capsys):
    orchestrator = load_orchestrator()
    captured = {}
    process = _FakeProcess()

    class FakeProxy:
        def __init__(self, **kwargs):
            captured["proxy_kwargs"] = kwargs
            self.base_url = "http://127.0.0.1:41234/v1"

        def __enter__(self):
            captured["proxy_entered"] = True
            return self

        def __exit__(self, *args):
            captured["proxy_exited"] = True

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["popen_kwargs"] = kwargs
        captured["config"] = (
            Path(kwargs["env"]["CODEX_HOME"]) / "config.toml"
        ).read_text(encoding="utf-8")
        return process

    result = orchestrator.run_internal_player(
        [
            "--codex-bin", "/codex",
            "--player-workspace", str(tmp_path),
            "--model", "doubao-seed-2-1-pro-260628",
            "--mcp-url", "http://127.0.0.1:8766/mcp",
            "--max-output-tokens", "8192",
            "--workflow-memory", "enabled",
        ],
        stdin_text="play exactly this",
        base_env={
            "PATH": "/safe",
            orchestrator.DOUBAO_UPSTREAM_KEY_ENV: "real-secret",
            orchestrator.DOUBAO_UPSTREAM_URL_ENV: "https://yibuapi.com/v1",
        },
        popen_factory=fake_popen,
        proxy_factory=FakeProxy,
        token_factory=lambda: "local-proxy-token",
    )

    assert result == 17
    assert captured["proxy_entered"] and captured["proxy_exited"]
    assert captured["proxy_kwargs"]["upstream_token"] == "real-secret"
    assert process.stdin.value == "play exactly this"
    assert process.stdin.closed
    assert captured["popen_kwargs"]["env"]["DOUBAO_PROXY_API_KEY"] == "local-proxy-token"
    assert "real-secret" not in repr(captured["popen_kwargs"]["env"])
    assert "real-secret" not in captured["config"]
    assert "codex line one" in capsys.readouterr().out


def test_internal_wrapper_rejects_empty_prompt_before_proxy_start(tmp_path):
    orchestrator = load_orchestrator()
    with pytest.raises(ValueError, match="prompt"):
        orchestrator.run_internal_player(
            [
                "--codex-bin", "/codex",
                "--player-workspace", str(tmp_path),
                "--model", "doubao-seed-2-1-pro-260628",
                "--mcp-url", "http://127.0.0.1:8766/mcp",
                "--max-output-tokens", "8192",
                "--workflow-memory", "enabled",
            ],
            stdin_text="",
            base_env={},
            proxy_factory=lambda **kwargs: pytest.fail("proxy must not start"),
        )


def test_main_wires_wrapper_restart_and_metadata_without_secret(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    credentials = _credential_file(tmp_path)
    run_dir = tmp_path / "run"
    paths = SimpleNamespace(
        run_dir=run_dir,
        player_workspace=run_dir / "player_workspace",
        log_root=run_dir / "logs",
    )
    paths.player_workspace.mkdir(parents=True)
    paths.log_root.mkdir()
    captured = {}
    monkeypatch.setattr(orchestrator, "validate_isolated_session_root", lambda path: Path(path))
    monkeypatch.setattr(orchestrator, "resolve_codex_bin", lambda value: "/native/codex")
    monkeypatch.setattr(orchestrator, "is_port_listening", lambda *args: False)
    monkeypatch.setattr(orchestrator, "collect_runtime_metadata", lambda **kwargs: {"runtime": "ok"})
    monkeypatch.setattr(orchestrator, "create_run_paths", lambda *args, **kwargs: (captured.setdefault("run", kwargs), paths)[1])
    monkeypatch.setattr(orchestrator, "build_mcp_command", lambda *args: ["mcp"])
    monkeypatch.setattr(orchestrator, "build_supervisor_command", lambda **kwargs: ["supervisor"])
    monkeypatch.setattr(orchestrator, "build_trusted_mcp_env", lambda *args: {"MCP": "safe"})
    monkeypatch.setattr(orchestrator, "build_supervisor_env", lambda *args: {"GODOT": "safe"})
    def fake_run_orchestrated_session(**kwargs):
        captured["session"] = kwargs
        return 23

    monkeypatch.setattr(
        orchestrator,
        "run_orchestrated_session",
        fake_run_orchestrated_session,
    )

    result = orchestrator.main(
        [
            "--session-root", str(tmp_path / "sessions"),
            "--credentials", str(credentials),
            "--scenario", "garden_watering",
        ]
    )

    assert result == 23
    assert captured["run"]["model"] == "doubao-seed-2-1-pro-260628"
    assert captured["run"]["reasoning_effort"] == "none"
    session = captured["session"]
    assert session["player_restart_limit"] == 8
    assert "workflow_memory_read" in session["player_restart_prompt"]
    assert session["player_command"][1].endswith("ai_play_codex_doubao_orchestrator.py")
    assert session["player_command"][2] == orchestrator.INTERNAL_PLAYER_FLAG
    assert session["mcp_env"] == {"MCP": "safe"}
    assert session["supervisor_env"] == {"GODOT": "safe"}
    assert session["player_env"][orchestrator.DOUBAO_UPSTREAM_KEY_ENV] == "real-secret"
    assert "real-secret" not in repr(captured["run"])
