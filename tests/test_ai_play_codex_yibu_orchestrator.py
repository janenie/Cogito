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
        ]
    )
    assert args.model == "h:qwen3.8-max-preview"
    assert args.context_window == 256000
    assert args.auto_compact_token_limit == 180000
    assert args.max_output_tokens == 4096
    assert not hasattr(args, "reasoning_effort")


def test_parse_args_accepts_artifact_root_or_resume_run_but_not_both(tmp_path):
    orchestrator = load_orchestrator()

    artifact_args = orchestrator.parse_args([
        "--model", "gemini-3.6-flash",
        "--artifact-root", str(tmp_path / "artifacts"),
    ])
    resume_args = orchestrator.parse_args([
        "--model", "gemini-3.6-flash",
        "--resume-run", str(tmp_path / "previous-run"),
    ])

    assert artifact_args.artifact_root == tmp_path / "artifacts"
    assert artifact_args.resume_run is None
    assert resume_args.resume_run == tmp_path / "previous-run"
    assert resume_args.artifact_root is None
    with pytest.raises(SystemExit):
        orchestrator.parse_args([
            "--model", "gemini-3.6-flash",
            "--artifact-root", str(tmp_path / "artifacts"),
            "--resume-run", str(tmp_path / "previous-run"),
        ])


def _write_resumable_run(tmp_path, *, completed_statuses):
    run_dir = tmp_path / "run"
    log_root = run_dir / "trusted_mcplogs"
    log_root.mkdir(parents=True)
    metadata = {
        "schema_version": 2,
        "player": "codex",
        "model": "gemini-3.6-flash",
        "reasoning_effort": "none",
        "scenario": "find_contract",
        "workflow_memory": "enabled",
        "requested_runs": 3,
        "benchmark": {"cycle_seed": 20260809, "attempts": []},
        "execution": {
            "model_context_window": 128000,
            "model_auto_compact_token_limit": 90000,
        },
    }
    (run_dir / "session.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    completed = [
        {
            "number": index,
            "scenario_id": "find_contract",
            "status": status,
            "terminal_reason": "terminal_reason",
            "consumed": True,
        }
        for index, status in enumerate(completed_statuses, 1)
    ]
    checkpoint = {
        "schema_version": 1,
        "scenario_id": "find_contract",
        "active_attempt": None,
        "completed": completed,
        "version": 1,
        "goal_pattern": None,
        "workflow": [],
        "landmarks": [],
        "avoid": [],
        "failure_reviews": [],
    }
    (log_root / "workflow_memory.json").write_text(
        json.dumps(checkpoint),
        encoding="utf-8",
    )
    return run_dir


def test_load_resume_progress_counts_only_formal_terminals(tmp_path):
    orchestrator = load_orchestrator()
    run_dir = _write_resumable_run(
        tmp_path,
        completed_statuses=["success", "shutdown", "failure"],
    )

    completed_runs = orchestrator.load_resume_progress(
        run_dir,
        model="gemini-3.6-flash",
        scenario="find_contract",
        workflow_memory_enabled=True,
        requested_runs=3,
        benchmark_cycle_seed=20260809,
        context_window=128000,
        auto_compact_token_limit=90000,
    )

    assert completed_runs == 2


def test_load_resume_progress_rejects_incompatible_model(tmp_path):
    orchestrator = load_orchestrator()
    run_dir = _write_resumable_run(
        tmp_path,
        completed_statuses=["success"],
    )

    with pytest.raises(ValueError, match="resume model mismatch"):
        orchestrator.load_resume_progress(
            run_dir,
            model="different-model",
            scenario="find_contract",
            workflow_memory_enabled=True,
            requested_runs=3,
            benchmark_cycle_seed=20260809,
            context_window=128000,
            auto_compact_token_limit=90000,
        )


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


@pytest.mark.parametrize("workflow_memory_enabled", [False, True])
def test_yibu_player_prompt_limits_active_image_context(
    workflow_memory_enabled,
):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(
        runs=3,
        workflow_memory_enabled=workflow_memory_enabled,
        scenario="find_contract",
        rotate_after_terminal=True,
    )

    assert "最多主动参考最近 10 张与当前任务相关的图片" in prompt
    assert "RGB 和深度图分别按一张图片计数" in prompt
    assert "为每张新图片写一条简短 caption" in prompt
    assert "更旧图片只使用此前生成的 caption" in prompt
    assert "仍随历史传输了更旧图片" in prompt


@pytest.mark.parametrize("workflow_memory_enabled", [False, True])
def test_yibu_restart_prompt_repeats_image_context_limit(
    workflow_memory_enabled,
):
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_restart_prompt(
        runs=3,
        workflow_memory_enabled=workflow_memory_enabled,
    )

    assert "最多主动参考最近 10 张与当前任务相关的图片" in prompt
    assert "RGB 和深度图分别按一张图片计数" in prompt
    assert "更旧图片只使用此前生成的 caption" in prompt


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
        runtime_dir=run_dir,
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
        lambda **kwargs: captured.setdefault("supervisor_build", kwargs)
        and ["supervisor"],
    )

    def fake_build_trusted_mcp_env(*args, **kwargs):
        captured["mcp_env_build"] = (args, kwargs)
        return {"MCP": "safe"}

    monkeypatch.setattr(
        orchestrator,
        "build_trusted_mcp_env",
        fake_build_trusted_mcp_env,
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
            "--artifact-root",
            str(tmp_path / "artifacts"),
            "--yibu-credentials",
            str(credential_path),
            "--model",
            "gemini-3.1-pro-preview",
        ]
    )

    assert result == 23
    assert captured["mcp_build"][1]["codex_media_output"] is True
    assert captured["run_path_kwargs"]["artifact_root"] == (
        tmp_path / "artifacts"
    )
    assert captured["mcp_env_build"][1]["workflow_memory_path"] == (
        log_root / "workflow_memory.json"
    )
    assert captured["supervisor_build"]["attempt_offset"] == 0
    assert captured["session"]["mcp_command"][-1] == "--codex-media-output"
    proxy_command = captured["session"]["provider_proxy_command"]
    assert proxy_command[
        proxy_command.index("--diagnostics-jsonl") + 1
    ] == str(log_root / "provider_requests.jsonl")
    assert proxy_command[
        proxy_command.index("--max-output-tokens") + 1
    ] == "4096"
    assert "最多主动参考最近 10 张与当前任务相关的图片" in captured[
        "session"
    ]["prompt"]
    assert "最多主动参考最近 10 张与当前任务相关的图片" in captured[
        "session"
    ]["player_restart_prompt"]
    assert captured["run_path_kwargs"]["reasoning_effort"] == "none"
    execution = captured["runtime_metadata_kwargs"]["execution"]
    assert execution["player_restart_limit"] is None
    assert execution["model_context_window"] == 128000
    assert execution["model_auto_compact_token_limit"] == 90000
    assert execution["max_output_tokens"] == 4096
    assert captured["session"]["player_restart_limit"] is None
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


def test_main_resumes_remaining_runs_with_checkpoint_and_global_offset(
    monkeypatch,
    tmp_path,
):
    orchestrator = load_orchestrator()
    run_dir = _write_resumable_run(
        tmp_path / "artifacts",
        completed_statuses=["success", "shutdown"],
    )
    credential_path = tmp_path / "opus.py"
    credential_path.write_text(
        'ak = {"key": "fixture-secret", "url": "https://yibuapi.com"}',
        encoding="utf-8",
    )
    captured = {}
    monkeypatch.setattr(orchestrator, "resolve_codex_bin", lambda _value: "/codex")
    monkeypatch.setattr(orchestrator, "is_port_listening", lambda *_args: False)
    monkeypatch.setattr(
        orchestrator,
        "collect_runtime_metadata",
        lambda **kwargs: {"execution": kwargs["execution"]},
    )

    def fake_run_orchestrated_session(**kwargs):
        captured.update(kwargs)
        return 31

    monkeypatch.setattr(
        orchestrator,
        "run_orchestrated_session",
        fake_run_orchestrated_session,
    )

    result = orchestrator.main([
        "--session-root", str(tmp_path / "runtime"),
        "--resume-run", str(run_dir),
        "--yibu-credentials", str(credential_path),
        "--model", "gemini-3.6-flash",
        "--runs", "3",
        "--scenario", "find_contract",
    ])

    assert result == 31
    supervisor = captured["supervisor_command"]
    assert supervisor[supervisor.index("--runs") + 1] == "2"
    assert supervisor[supervisor.index("--attempt-offset") + 1] == "1"
    assert captured["mcp_env"]["AI_PLAY_WORKFLOW_MEMORY_PATH"] == str(
        run_dir / "trusted_mcplogs" / "workflow_memory.json"
    )
    assert captured["player_cwd"].parent.parent == (
        tmp_path / "runtime"
    ).resolve()
    proxy_command = captured["provider_proxy_command"]
    assert proxy_command[
        proxy_command.index("--diagnostics-jsonl") + 1
    ] == str(run_dir / "trusted_mcplogs" / "provider_requests.jsonl")
    assert proxy_command[
        proxy_command.index("--max-output-tokens") + 1
    ] == "4096"
