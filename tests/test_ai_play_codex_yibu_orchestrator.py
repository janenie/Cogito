import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_PATH = REPO_ROOT / "tools" / "ai_play_codex_yibu_orchestrator.py"
MODELS = (
    "gemini-3.1-pro-preview",
    "grok-4.6",
    "h:qwen3.8-max-preview",
    "MiniMax-M3",
    "hy3",
)


def load_orchestrator():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_codex_yibu_orchestrator",
        ORCHESTRATOR_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("model", MODELS)
def test_write_player_config_creates_image_capable_single_model_catalog(
    tmp_path,
    model,
):
    orchestrator = load_orchestrator()

    config_path = orchestrator.write_player_codex_yibu_config(
        tmp_path,
        model=model,
        base_url="http://127.0.0.1:18767/v1",
        mcp_url="http://127.0.0.1:8766/mcp",
    )

    catalog_path = tmp_path / "model-catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entry = catalog["models"][0]
    assert entry["slug"] == model
    assert entry["input_modalities"] == ["text", "image"]
    assert entry["context_window"] == 128000
    assert entry["max_context_window"] == 128000
    assert entry["supports_parallel_tool_calls"] is False
    assert entry["supports_reasoning_summaries"] is False
    assert entry["truncation_policy"] == {"mode": "bytes", "limit": 10000}
    assert os.stat(catalog_path).st_mode & 0o777 == 0o600
    assert os.stat(config_path).st_mode & 0o777 == 0o600


def test_write_player_config_sets_context_and_catalog_without_secret(tmp_path):
    orchestrator = load_orchestrator()

    config_path = orchestrator.write_player_codex_yibu_config(
        tmp_path,
        model="gemini-3.1-pro-preview",
        base_url="http://127.0.0.1:18767/v1",
        mcp_url="http://127.0.0.1:8766/mcp",
        context_window=256000,
        auto_compact_token_limit=180000,
    )

    text = config_path.read_text(encoding="utf-8")
    assert 'model = "gemini-3.1-pro-preview"' in text
    assert "model_context_window = 256000" in text
    assert "model_auto_compact_token_limit = 180000" in text
    assert f'model_catalog_json = {json.dumps(str(tmp_path / "model-catalog.json"))}' in text
    assert "model_reasoning_effort" not in text
    assert "secret" not in text


@pytest.mark.parametrize(
    ("context_window", "compact_limit", "message"),
    [
        (0, 1, "--context-window"),
        (10_000_001, 1, "--context-window"),
        (128000, 0, "--auto-compact-token-limit"),
        (128000, 128000, "--auto-compact-token-limit"),
        (128000, 128001, "--auto-compact-token-limit"),
    ],
)
def test_validate_context_limits_rejects_invalid_values(
    context_window,
    compact_limit,
    message,
):
    orchestrator = load_orchestrator()

    with pytest.raises(ValueError, match=message):
        orchestrator.validate_context_limits(context_window, compact_limit)


def test_parse_args_requires_model_and_accepts_context_overrides():
    orchestrator = load_orchestrator()

    with pytest.raises(SystemExit) as error:
        orchestrator.parse_args([])
    assert error.value.code == 2

    args = orchestrator.parse_args(
        [
            "--model",
            "h:qwen3.8-max-preview",
            "--context-window",
            "256000",
            "--auto-compact-token-limit",
            "180000",
            "--max-historical-images",
            "4",
        ]
    )
    assert args.model == "h:qwen3.8-max-preview"
    assert args.context_window == 256000
    assert args.auto_compact_token_limit == 180000
    assert args.max_historical_images == 4
    assert not hasattr(args, "reasoning_effort")

    with pytest.raises(SystemExit) as error:
        orchestrator.parse_args(
            ["--model", "fixture", "--max-historical-images", "-1"]
        )
    assert error.value.code == 2


@pytest.mark.parametrize("model", ("", "bad model", "bad\nmodel", "x" * 257))
def test_validate_yibu_model_argument_rejects_unsafe_ids(model):
    orchestrator = load_orchestrator()

    with pytest.raises(ValueError):
        orchestrator.validate_yibu_model_argument(model)


def test_validate_yibu_model_argument_accepts_colon_literally():
    orchestrator = load_orchestrator()

    assert (
        orchestrator.validate_yibu_model_argument("h:qwen3.8-max-preview")
        == "h:qwen3.8-max-preview"
    )


def test_load_yibu_credentials_does_not_execute_source(tmp_path):
    marker = tmp_path / "executed"
    source = tmp_path / "opus.py"
    source.write_text(
        'ak = {"key": "secret", "url": "https://yibuapi.com"}\n'
        f'open({str(marker)!r}, "w").write("bad")\n',
        encoding="utf-8",
    )

    credentials = load_orchestrator().load_yibu_credentials(source)

    assert credentials.api_key == "secret"
    assert credentials.base_url == "https://yibuapi.com/v1"
    assert not marker.exists()


def test_main_wires_media_context_audit_and_secret_isolation(monkeypatch, tmp_path):
    orchestrator = load_orchestrator()
    credential_path = tmp_path / "opus.py"
    credential_path.write_text(
        'ak = {"key": "fixture-secret", "url": "https://yibuapi.com"}',
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    player_workspace = run_dir / "player_workspace"
    log_root = run_dir / "trusted_mcplogs"
    player_workspace.mkdir(parents=True)
    log_root.mkdir()
    paths = SimpleNamespace(
        run_dir=run_dir,
        player_workspace=player_workspace,
        log_root=log_root,
    )
    captured = {}

    monkeypatch.setattr(
        orchestrator,
        "validate_isolated_session_root",
        lambda root: Path(root).resolve(),
    )
    monkeypatch.setattr(orchestrator, "resolve_codex_bin", lambda _value: "/codex")
    monkeypatch.setattr(orchestrator, "is_port_listening", lambda *_args: False)

    def fake_runtime_metadata(**kwargs):
        captured["runtime_metadata_kwargs"] = kwargs
        return {"execution": kwargs["execution"]}

    monkeypatch.setattr(
        orchestrator,
        "collect_runtime_metadata",
        fake_runtime_metadata,
    )

    def fake_create_run_paths(*args, **kwargs):
        captured["run_path_args"] = args
        captured["run_path_kwargs"] = kwargs
        return paths

    monkeypatch.setattr(orchestrator, "create_run_paths", fake_create_run_paths)

    def fake_build_mcp_command(*args, **kwargs):
        captured["mcp_build"] = (args, kwargs)
        command = ["mcp"]
        if kwargs.get("codex_media_output"):
            command.append("--codex-media-output")
        return command

    monkeypatch.setattr(orchestrator, "build_mcp_command", fake_build_mcp_command)
    monkeypatch.setattr(
        orchestrator,
        "build_supervisor_command",
        lambda **_kwargs: ["supervisor"],
    )
    monkeypatch.setattr(
        orchestrator,
        "build_trusted_mcp_env",
        lambda *_args, **_kwargs: {"MCP": "safe"},
    )
    monkeypatch.setattr(
        orchestrator,
        "build_supervisor_env",
        lambda *_args, **_kwargs: {"GODOT": "safe"},
    )
    monkeypatch.setattr(
        orchestrator,
        "build_provider_proxy_env",
        lambda *_args, **_kwargs: {"PROXY": "safe"},
    )

    def fake_run_orchestrated_session(**kwargs):
        captured["session"] = kwargs
        home = Path(kwargs["player_env"]["CODEX_HOME"])
        captured["config_text"] = (home / "config.toml").read_text()
        captured["catalog_text"] = (home / "model-catalog.json").read_text()
        return 23

    monkeypatch.setattr(
        orchestrator,
        "run_orchestrated_session",
        fake_run_orchestrated_session,
    )

    result = orchestrator.main(
        [
            "--session-root",
            str(tmp_path / "sessions"),
            "--yibu-credentials",
            str(credential_path),
            "--model",
            "gemini-3.1-pro-preview",
            "--max-historical-images",
            "4",
        ]
    )

    assert result == 23
    assert captured["mcp_build"][1]["codex_media_output"] is True
    assert captured["session"]["mcp_command"][-1] == "--codex-media-output"
    assert captured["session"]["provider_proxy_command"][-2:] == [
        "--diagnostics-jsonl",
        str(log_root / "provider_requests.jsonl"),
    ]
    assert "--max-historical-images" in captured["session"][
        "provider_proxy_command"
    ]
    history_limit_index = captured["session"]["provider_proxy_command"].index(
        "--max-historical-images"
    )
    assert captured["session"]["provider_proxy_command"][
        history_limit_index + 1
    ] == "4"
    assert captured["run_path_kwargs"]["reasoning_effort"] == "none"
    execution = captured["runtime_metadata_kwargs"]["execution"]
    assert execution["model_context_window"] == 128000
    assert execution["model_auto_compact_token_limit"] == 90000
    assert execution["max_historical_images"] == 4
    assert captured["session"]["player_env"]["YIBU_API_KEY"] == "fixture-secret"
    for safe_value in (
        captured["run_path_kwargs"],
        captured["runtime_metadata_kwargs"],
        captured["session"]["mcp_command"],
        captured["session"]["provider_proxy_command"],
        captured["session"]["provider_proxy_env"],
        captured["config_text"],
        captured["catalog_text"],
    ):
        assert "fixture-secret" not in repr(safe_value)
