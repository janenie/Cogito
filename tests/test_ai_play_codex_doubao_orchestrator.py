import importlib.util
import io
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
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
    catalog_path = tmp_path / "model-catalog.json"
    assert f'model_catalog_json = "{catalog_path}"' in text
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert len(catalog["models"]) == 1
    catalog_model = catalog["models"][0]
    assert catalog_model["slug"] == "doubao-seed-2-1-pro-260628"
    assert catalog_model["display_name"] == "doubao-seed-2-1-pro-260628"
    assert catalog_model["supported_reasoning_levels"] == []
    assert catalog_model["shell_type"] == "shell_command"
    assert catalog_model["visibility"] == "list"
    assert catalog_model["supported_in_api"] is True
    assert catalog_model["priority"] == 0
    assert catalog_model["base_instructions"] == (
        "You are an AI game-playing agent. Follow the developer instructions."
    )
    assert catalog_model["support_verbosity"] is False
    assert catalog_model["truncation_policy"] == {
        "mode": "tokens",
        "limit": 10000,
    }
    assert catalog_model["supports_parallel_tool_calls"] is False
    assert catalog_model["experimental_supported_tools"] == []
    assert catalog_model["input_modalities"] == ["text", "image"]
    assert catalog_path.stat().st_mode & 0o777 == 0o600
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
    assert args.codex_max_resumes == 8
    assert args.credentials == orchestrator.REPO_ROOT / ".claude/settings.local.json"
    assert not hasattr(args, "reasoning_effort")


def test_parse_args_rejects_removed_codex_max_restarts_option():
    orchestrator = load_orchestrator()

    with pytest.raises(SystemExit):
        orchestrator.parse_args(["--codex-max-restarts", "1"])


def test_doubao_codex_commands_use_persistent_native_session(tmp_path):
    orchestrator = load_orchestrator()

    initial = orchestrator.build_codex_initial_command("/codex", tmp_path)
    resume = orchestrator.build_codex_resume_command("/codex")

    assert initial == [
        "/codex",
        "exec",
        "--cd",
        str(tmp_path),
        "--skip-git-repo-check",
        "-",
    ]
    assert "--ephemeral" not in initial
    assert resume == [
        "/codex",
        "exec",
        "resume",
        "--last",
        "--skip-git-repo-check",
        "-",
    ]


def test_internal_player_command_passes_runs_and_native_resume_limit(tmp_path):
    orchestrator = load_orchestrator()

    command = orchestrator.build_internal_player_command(
        python_bin="python",
        codex_bin="/codex",
        player_workspace=tmp_path,
        model=orchestrator.DEFAULT_MODEL,
        mcp_url="http://127.0.0.1:8766/mcp",
        max_output_tokens=8192,
        workflow_memory_enabled=True,
        runs=3,
        max_resumes=8,
    )

    assert command[command.index("--runs") + 1] == "3"
    assert command[command.index("--max-resumes") + 1] == "8"


def test_doubao_mcp_command_enables_codex_media_output():
    orchestrator = load_orchestrator()

    command = orchestrator.build_mcp_command(
        "python",
        8766,
        codex_media_output=True,
    )

    assert command[-1] == "--codex-media-output"


def test_resume_prompt_recovers_public_state_for_awm_modes():
    orchestrator = load_orchestrator()
    enabled = orchestrator.build_player_resume_prompt(3, True)
    disabled = orchestrator.build_player_resume_prompt(3, False)
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
    def __init__(self, *, running=False, returncode=17):
        self.stdin = _FakeStdin()
        self.stdout = iter(["codex line one\n", "codex line two\n"])
        self.terminated = False
        self.signals = []
        self.running = running
        self.returncode = returncode

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return None if self.running else self.returncode

    def terminate(self):
        self.terminated = True
        self.running = False

    def kill(self):
        self.terminated = True
        self.running = False

    def send_signal(self, signum):
        self.signals.append(signum)


def test_internal_wrapper_forwards_termination_signals(monkeypatch):
    orchestrator = load_orchestrator()
    process = _FakeProcess(running=True)
    installed = {}
    restored = []

    monkeypatch.setattr(orchestrator.signal, "getsignal", lambda signum: f"old-{signum}")

    def fake_signal(signum, handler):
        if callable(handler):
            installed[signum] = handler
        else:
            restored.append((signum, handler))

    monkeypatch.setattr(orchestrator.signal, "signal", fake_signal)

    with orchestrator._forward_child_signals([process]) as received:
        installed[signal.SIGTERM](signal.SIGTERM, None)
        installed[signal.SIGINT](signal.SIGINT, None)

    assert process.signals == [signal.SIGTERM, signal.SIGINT]
    assert [received.get_nowait(), received.get_nowait()] == [
        signal.SIGTERM,
        signal.SIGINT,
    ]
    assert restored == [
        (signal.SIGTERM, f"old-{signal.SIGTERM}"),
        (signal.SIGINT, f"old-{signal.SIGINT}"),
    ]


def test_internal_wrapper_does_not_resume_after_signal_between_turns(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    installed = {}
    commands = []

    class SignalAfterExitProcess(_FakeProcess):
        def __init__(self):
            super().__init__(returncode=0)
            self.sent = False

        def wait(self, timeout=None):
            if not self.sent:
                self.sent = True
                installed[signal.SIGTERM](signal.SIGTERM, None)
            return 0

    processes = [SignalAfterExitProcess(), _FakeProcess(returncode=17)]

    class FakeProxy:
        base_url = "http://127.0.0.1:41234/v1"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(orchestrator.signal, "getsignal", lambda signum: signal.SIG_DFL)

    def fake_signal(signum, handler):
        if callable(handler):
            installed[signum] = handler

    monkeypatch.setattr(orchestrator.signal, "signal", fake_signal)

    def fake_popen(command, **kwargs):
        commands.append(command)
        return processes[len(commands) - 1]

    result = orchestrator.run_internal_player(
        [
            "--codex-bin", "/codex",
            "--player-workspace", str(tmp_path),
            "--model", orchestrator.DEFAULT_MODEL,
            "--mcp-url", "http://127.0.0.1:8766/mcp",
            "--max-output-tokens", "8192",
            "--workflow-memory", "disabled",
            "--runs", "3",
            "--max-resumes", "8",
        ],
        stdin_text="play",
        base_env={
            orchestrator.DOUBAO_UPSTREAM_KEY_ENV: "real-secret",
            orchestrator.DOUBAO_UPSTREAM_URL_ENV: "https://yibuapi.com/v1",
        },
        popen_factory=fake_popen,
        proxy_factory=lambda **kwargs: FakeProxy(),
    )

    assert result == 128 + signal.SIGTERM
    assert len(commands) == 1


def test_monitor_bounds_cleanup_after_forwarded_termination():
    orchestrator = load_orchestrator()
    process = _FakeProcess(running=True)
    received = queue.SimpleQueue()
    received.put(signal.SIGTERM)

    result = orchestrator._monitor_codex_process(
        process,
        SimpleNamespace(failure_event=threading.Event()),
        received,
    )

    assert result == 128 + signal.SIGTERM
    assert process.terminated


def test_monitor_kills_child_that_ignores_termination(monkeypatch):
    orchestrator = load_orchestrator()

    class StubbornProcess(_FakeProcess):
        def __init__(self):
            super().__init__(running=True)
            self.killed = False

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            if self.running:
                raise subprocess.TimeoutExpired("codex", timeout)
            return -9

        def kill(self):
            self.killed = True
            self.running = False

    process = StubbornProcess()
    received = queue.SimpleQueue()
    received.put(signal.SIGTERM)
    monkeypatch.setattr(
        orchestrator,
        "CODEX_INNER_TERMINATION_GRACE_SECONDS",
        0.01,
    )

    result = orchestrator._monitor_codex_process(
        process,
        SimpleNamespace(failure_event=threading.Event()),
        received,
    )

    assert result == 128 + signal.SIGTERM
    assert process.terminated
    assert process.killed


def test_monitor_prioritizes_proxy_failure_after_codex_exit():
    orchestrator = load_orchestrator()
    failure = threading.Event()
    failure.set()

    with pytest.raises(RuntimeError, match="proxy stopped unexpectedly"):
        orchestrator._monitor_codex_process(
            _FakeProcess(running=False),
            SimpleNamespace(
                failure_event=failure,
                thread_error=RuntimeError("proxy failed"),
            ),
            queue.SimpleQueue(),
        )


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
            "--runs", "3",
            "--max-resumes", "8",
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


def test_internal_wrapper_resumes_same_native_session_after_normal_exit(tmp_path):
    orchestrator = load_orchestrator()
    processes = [
        _FakeProcess(returncode=0),
        _FakeProcess(returncode=17),
    ]
    calls = []

    class FakeProxy:
        base_url = "http://127.0.0.1:41234/v1"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return processes[len(calls) - 1]

    result = orchestrator.run_internal_player(
        [
            "--codex-bin", "/codex",
            "--player-workspace", str(tmp_path),
            "--model", orchestrator.DEFAULT_MODEL,
            "--mcp-url", "http://127.0.0.1:8766/mcp",
            "--max-output-tokens", "8192",
            "--workflow-memory", "enabled",
            "--runs", "3",
            "--max-resumes", "8",
        ],
        stdin_text="play exactly this",
        base_env={
            orchestrator.DOUBAO_UPSTREAM_KEY_ENV: "real-secret",
            orchestrator.DOUBAO_UPSTREAM_URL_ENV: "https://yibuapi.com/v1",
        },
        popen_factory=fake_popen,
        proxy_factory=lambda **kwargs: FakeProxy(),
        token_factory=lambda: "local-proxy-token",
    )

    assert result == 17
    assert len(calls) == 2
    assert calls[0][0] == orchestrator.build_codex_initial_command(
        "/codex",
        tmp_path,
    )
    assert calls[1][0] == orchestrator.build_codex_resume_command("/codex")
    assert calls[0][1]["env"]["CODEX_HOME"] == calls[1][1]["env"]["CODEX_HOME"]
    assert calls[0][1]["cwd"] == calls[1][1]["cwd"] == tmp_path
    assert processes[0].stdin.value == "play exactly this"
    assert processes[1].stdin.value == orchestrator.build_player_resume_prompt(3, True)


def test_internal_wrapper_returns_exact_code_when_native_resume_limit_exhausted(
    tmp_path,
):
    orchestrator = load_orchestrator()
    processes = [
        _FakeProcess(returncode=0),
        _FakeProcess(returncode=0),
    ]
    commands = []

    class FakeProxy:
        base_url = "http://127.0.0.1:41234/v1"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def fake_popen(command, **kwargs):
        commands.append(command)
        return processes[len(commands) - 1]

    result = orchestrator.run_internal_player(
        [
            "--codex-bin", "/codex",
            "--player-workspace", str(tmp_path),
            "--model", orchestrator.DEFAULT_MODEL,
            "--mcp-url", "http://127.0.0.1:8766/mcp",
            "--max-output-tokens", "8192",
            "--workflow-memory", "disabled",
            "--runs", "3",
            "--max-resumes", "1",
        ],
        stdin_text="play",
        base_env={
            orchestrator.DOUBAO_UPSTREAM_KEY_ENV: "real-secret",
            orchestrator.DOUBAO_UPSTREAM_URL_ENV: "https://yibuapi.com/v1",
        },
        popen_factory=fake_popen,
        proxy_factory=lambda **kwargs: FakeProxy(),
    )

    assert result == orchestrator.NATIVE_RESUME_LIMIT_EXIT_CODE == 6
    assert len(commands) == 2


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
                "--runs", "3",
                "--max-resumes", "8",
            ],
            stdin_text="",
            base_env={},
            proxy_factory=lambda **kwargs: pytest.fail("proxy must not start"),
        )


def test_internal_wrapper_terminates_codex_when_proxy_thread_fails(tmp_path):
    orchestrator = load_orchestrator()
    process = _FakeProcess(running=True)

    class FailedProxy:
        base_url = "http://127.0.0.1:41234/v1"
        failure_event = threading.Event()
        thread_error = RuntimeError("proxy thread failed")

        def __enter__(self):
            self.failure_event.set()
            return self

        def __exit__(self, *args):
            pass

    with pytest.raises(RuntimeError, match="proxy stopped unexpectedly"):
        orchestrator.run_internal_player(
            [
                "--codex-bin", "/codex",
                "--player-workspace", str(tmp_path),
                "--model", orchestrator.DEFAULT_MODEL,
                "--mcp-url", "http://127.0.0.1:8766/mcp",
                "--max-output-tokens", "8192",
                "--workflow-memory", "disabled",
                "--runs", "3",
                "--max-resumes", "8",
            ],
            stdin_text="play",
            base_env={
                orchestrator.DOUBAO_UPSTREAM_KEY_ENV: "real-secret",
                orchestrator.DOUBAO_UPSTREAM_URL_ENV: "https://yibuapi.com/v1",
            },
            popen_factory=lambda *args, **kwargs: process,
            proxy_factory=lambda **kwargs: FailedProxy(),
        )

    assert process.terminated


def test_internal_wrapper_closes_proxy_when_codex_start_fails(tmp_path):
    orchestrator = load_orchestrator()
    lifecycle = []

    class FakeProxy:
        base_url = "http://127.0.0.1:41234/v1"

        def __enter__(self):
            lifecycle.append("enter")
            return self

        def __exit__(self, *args):
            lifecycle.append("exit")

    def fail_start(*args, **kwargs):
        raise OSError("could not start Codex")

    with pytest.raises(OSError, match="could not start Codex"):
        orchestrator.run_internal_player(
            [
                "--codex-bin", "/codex",
                "--player-workspace", str(tmp_path),
                "--model", orchestrator.DEFAULT_MODEL,
                "--mcp-url", "http://127.0.0.1:8766/mcp",
                "--max-output-tokens", "8192",
                "--workflow-memory", "disabled",
                "--runs", "3",
                "--max-resumes", "8",
            ],
            stdin_text="play",
            base_env={
                orchestrator.DOUBAO_UPSTREAM_KEY_ENV: "real-secret",
                orchestrator.DOUBAO_UPSTREAM_URL_ENV: "https://yibuapi.com/v1",
            },
            popen_factory=fail_start,
            proxy_factory=lambda **kwargs: FakeProxy(),
        )

    assert lifecycle == ["enter", "exit"]


def test_main_wires_native_resume_and_metadata_without_secret(monkeypatch, tmp_path):
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
    monkeypatch.setattr(
        orchestrator,
        "collect_runtime_metadata",
        lambda **kwargs: (
            captured.setdefault("runtime", kwargs) or {"runtime": "ok"}
        ),
    )
    monkeypatch.setattr(orchestrator, "create_run_paths", lambda *args, **kwargs: (captured.setdefault("run", kwargs), paths)[1])
    monkeypatch.setattr(
        orchestrator,
        "build_mcp_command",
        lambda *args, **kwargs: ["mcp"],
    )
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
    assert session["player_restart_limit"] == 0
    assert session["player_restart_prompt"] is None
    assert session["stop_player_on_supervisor_exit"] is True
    assert captured["runtime"]["execution"]["player_restart_limit"] == 0
    assert captured["runtime"]["execution"]["native_resume_limit"] == 8
    assert session["player_command"][1].endswith("ai_play_codex_doubao_orchestrator.py")
    assert session["player_command"][2] == orchestrator.INTERNAL_PLAYER_FLAG
    assert session["player_command"][session["player_command"].index("--runs") + 1] == "3"
    assert session["player_command"][session["player_command"].index("--max-resumes") + 1] == "8"
    assert session["mcp_env"] == {"MCP": "safe"}
    assert session["supervisor_env"] == {"GODOT": "safe"}
    assert session["player_env"][orchestrator.DOUBAO_UPSTREAM_KEY_ENV] == "real-secret"
    assert "real-secret" not in repr(captured["run"])


def _native_codex_bin():
    candidates = [
        Path(
            "/usr/local/lib/node_modules/@openai/codex/node_modules/"
            "@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex"
        ),
        Path(shutil.which("codex") or ""),
    ]
    return next((str(path) for path in candidates if path.is_file()), None)


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_port(port, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError(f"port {port} did not open")


def _response_sse(events):
    return b"".join(
        (
            f"event: {event['type']}\n"
            f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
        ).encode()
        for event in events
    )


def _tool_call_stream(model):
    alias = "mcp__cogito_ai_play__briefing"
    item = {
        "id": "fc_test",
        "type": "function_call",
        "status": "completed",
        "arguments": "{}",
        "call_id": "call_test",
        "name": alias,
    }
    response = {
        "id": "resp_tool",
        "object": "response",
        "created_at": 1,
        "status": "completed",
        "model": model,
        "output": [item],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }
    return _response_sse(
        [
            {"type": "response.created", "response": response | {"status": "in_progress", "output": []}},
            {"type": "response.output_item.added", "output_index": 0, "item": item | {"status": "in_progress", "arguments": ""}},
            {"type": "response.function_call_arguments.done", "item_id": "fc_test", "output_index": 0, "arguments": "{}"},
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {"type": "response.completed", "response": response},
        ]
    )


def _final_text_stream(model):
    item = {
        "id": "msg_test",
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "integration complete", "annotations": []}],
    }
    response = {
        "id": "resp_final",
        "object": "response",
        "created_at": 2,
        "status": "completed",
        "model": model,
        "output": [item],
        "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
    }
    return _response_sse(
        [
            {"type": "response.created", "response": response | {"status": "in_progress", "output": []}},
            {"type": "response.output_item.added", "output_index": 0, "item": item | {"status": "in_progress", "content": []}},
            {"type": "response.output_text.delta", "item_id": "msg_test", "output_index": 0, "content_index": 0, "delta": "integration complete"},
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {"type": "response.completed", "response": response},
        ]
    )


def test_codex_proxy_routes_flat_function_call_to_mcp(tmp_path):
    codex_bin = _native_codex_bin()
    if codex_bin is None:
        pytest.skip("Codex CLI is unavailable")
    orchestrator = load_orchestrator()
    proxy_module = importlib.import_module("tools.ai_play_doubao_responses_proxy")
    marker = tmp_path / "briefing-called"
    port = _free_port()
    mcp_process = subprocess.Popen(
        [
            sys.executable,
            str(REPO_ROOT / "tests" / "fixtures" / "fake_ai_play_mcp_server.py"),
            "--port", str(port),
            "--marker", str(marker),
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _wait_port(port)
    calls = []

    class Response:
        status_code = 200
        headers = {"content-type": "text/event-stream"}

        def __init__(self, body):
            self.body = body

        def iter_bytes(self):
            yield self.body

        def close(self):
            pass

    from contextlib import contextmanager

    @contextmanager
    def upstream(url, headers, content, timeout):
        calls.append(json.loads(content))
        body = (
            _tool_call_stream(orchestrator.DEFAULT_MODEL)
            if len(calls) == 1
            else _final_text_stream(orchestrator.DEFAULT_MODEL)
        )
        yield Response(body)

    def proxy_factory(**kwargs):
        return proxy_module.DoubaoProxyServer(
            **kwargs,
            upstream_factory=upstream,
            event_logger=lambda event: None,
        )

    try:
        result = orchestrator.run_internal_player(
            [
                "--codex-bin", codex_bin,
                "--player-workspace", str(tmp_path),
                "--model", orchestrator.DEFAULT_MODEL,
                "--mcp-url", f"http://127.0.0.1:{port}/mcp",
                "--max-output-tokens", "8192",
                "--workflow-memory", "disabled",
            ],
            stdin_text="Call briefing once, then finish.",
            base_env={
                "PATH": os.environ["PATH"],
                orchestrator.DOUBAO_UPSTREAM_KEY_ENV: "fake-upstream-token",
                orchestrator.DOUBAO_UPSTREAM_URL_ENV: "https://yibuapi.com/v1",
            },
            proxy_factory=proxy_factory,
            token_factory=lambda: "local-proxy-token",
        )
    finally:
        mcp_process.terminate()
        mcp_process.wait(timeout=5)

    assert result == 0
    assert marker.read_text(encoding="utf-8") == "briefing-called"
    assert calls
    assert [tool["type"] for tool in calls[0]["tools"]] == ["function"] * 3
