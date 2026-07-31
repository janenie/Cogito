import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "tools" / "run_find_contract_awm_comparison.py"


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_find_contract_awm_comparison",
        RUNNER_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_group_command_uses_current_checkout_and_fixed_settings(tmp_path):
    runner = load_runner()

    command = runner.build_group_command(
        repo_root=REPO_ROOT,
        python_bin="python-test",
        session_root=tmp_path / "without_awm",
        runs=3,
        model="gpt-5.6-sol",
        reasoning_effort="high",
        workflow_memory="disabled",
        codex_auth_home=Path("~/.codex-cogito-player"),
    )

    assert command[:2] == [
        "python-test",
        str(REPO_ROOT / "tools" / "ai_play_codex_orchestrator.py"),
    ]
    assert command[command.index("--scenario") + 1] == "find_contract"
    assert command[command.index("--runs") + 1] == "3"
    assert command[command.index("--model") + 1] == "gpt-5.6-sol"
    assert command[command.index("--reasoning-effort") + 1] == "high"
    assert command[command.index("--workflow-memory") + 1] == "disabled"


def test_parse_group_output_counts_outcomes_and_paths(tmp_path):
    runner = load_runner()
    output = "\n".join(
        [
            f"[orchestrator] run_dir={tmp_path / 'run'}",
            f"[orchestrator] trusted_log_root={tmp_path / 'logs'}",
            "[supervisor] AI_PLAY_GAME_OVER outcome=success reason=correct_password",
            "[supervisor] AI_PLAY_GAME_OVER outcome=failure reason=timeout",
            "[supervisor] AI_PLAY_GAME_OVER outcome=success reason=correct_password",
        ]
    )

    parsed = runner.parse_group_output(output)

    assert parsed["successes"] == 2
    assert parsed["failures"] == 1
    assert parsed["reasons"] == {"correct_password": 2, "timeout": 1}
    assert parsed["run_dir"] == str(tmp_path / "run")
    assert parsed["trusted_log_root"] == str(tmp_path / "logs")


def test_main_runs_both_groups_after_first_failure_and_writes_summary(
    monkeypatch,
    tmp_path,
):
    runner = load_runner()
    calls = []

    def fake_run_group(name, command, console_log):
        calls.append((name, command, console_log))
        return runner.GroupResult(
            name=name,
            exit_code=7 if name == "without_awm" else 0,
            elapsed_seconds=1.25,
            successes=0 if name == "without_awm" else 3,
            failures=1 if name == "without_awm" else 0,
            reasons={"timeout": 1} if name == "without_awm" else {"correct_password": 3},
            run_dir=None,
            trusted_log_root=None,
            console_log=str(console_log),
        )

    monkeypatch.setattr(runner, "run_group", fake_run_group)
    monkeypatch.setattr(runner, "allocate_comparison_dir", lambda root: tmp_path)

    result = runner.main([])

    assert result == 1
    assert [call[0] for call in calls] == ["without_awm", "with_awm"]
    summary = json.loads(
        (tmp_path / "comparison_summary.json").read_text(encoding="utf-8")
    )
    assert summary["model"] == "gpt-5.6-sol"
    assert summary["reasoning_effort"] == "high"
    assert [group["name"] for group in summary["groups"]] == [
        "without_awm",
        "with_awm",
    ]
