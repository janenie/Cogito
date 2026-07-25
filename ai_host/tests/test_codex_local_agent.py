import asyncio
import json
from pathlib import Path

from ai_host.agents.codex_local import (
    CodexLocalAgent,
    build_codex_exec_command,
    report_schema,
)
from ai_host.attempt_state import AttemptContext, ReflectionMemory
from ai_host.config import HostConfig


def test_codex_command_uses_empty_workspace_and_mcp_overrides(tmp_path):
    attempt_dir = tmp_path / "attempt_1"
    workspace_dir = attempt_dir / "codex_workspace"
    prompt_file = attempt_dir / "prompt.txt"
    report_file = attempt_dir / "report.json"
    schema_file = attempt_dir / "report_schema.json"

    command = build_codex_exec_command(
        config=HostConfig(
            adapter="codex-local",
            codex_command="codex",
            model="gpt-5.1-codex",
            codex_reasoning_effort="xhigh",
        ),
        workspace_dir=workspace_dir,
        prompt_file=prompt_file,
        report_file=report_file,
        schema_file=schema_file,
        repo_root=Path("/repo/Cogito"),
        python_command=Path("/repo/Cogito/.venv/bin/python"),
    )

    assert command[:2] == ["codex", "exec"]
    assert "--cd" in command
    assert str(workspace_dir.resolve()) in command
    assert str(Path("/repo/Cogito")) not in command[command.index("--cd") + 1]
    assert "--skip-git-repo-check" in command
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "--output-last-message" in command
    assert str(report_file.resolve()) in command
    assert command[-1] == "-"
    assert any("mcp_servers.cogito_ai_play.command" in item for item in command)
    assert any("mcp_servers.cogito_ai_play.env" in item for item in command)
    assert 'model_reasoning_effort="xhigh"' in command


def test_codex_local_agent_reads_cli_last_message_report(tmp_path):
    fake_codex = tmp_path / "fake_codex.py"
    fake_codex.write_text(
        "import json, pathlib, sys\n"
        "prompt = sys.stdin.read()\n"
        "assert 'Cogito game' in prompt\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])\n"
        "out.write_text(json.dumps({"
        "'attempt_id': 1,"
        "'outcome': 'success',"
        "'reason': 'cleanup_complete',"
        "'summary': 'completed via mcp',"
        "'mistakes': [],"
        "'next_strategy': []"
        "}))\n",
        encoding="utf-8",
    )
    config = HostConfig(
        adapter="codex-local",
        codex_command=f"python3 {fake_codex}",
        run_dir=tmp_path,
    )
    context = AttemptContext(
        attempt_id=1,
        max_attempts=3,
        scenario_id="daily_routine_cleanup",
        run_dir=tmp_path,
        reflection=ReflectionMemory(),
    )

    result = asyncio.run(CodexLocalAgent(config).run_attempt(context, None))

    assert result.outcome == "success"
    assert result.reason == "cleanup_complete"
    assert (tmp_path / "attempt_1" / "codex_workspace").is_dir()
    assert json.loads((tmp_path / "attempt_1" / "report.json").read_text())["summary"] == "completed via mcp"


def test_report_schema_requires_every_declared_property_for_strict_outputs():
    schema = report_schema()

    assert set(schema["required"]) == set(schema["properties"])
