import asyncio
from pathlib import Path

import pytest

from ai_host.agents.codex_local import (
    CodexLocalAgent,
    build_codex_exec_command,
    report_schema,
)
from ai_host.attempt_state import AttemptContext, ReflectionMemory
from ai_host.config import HostConfig


def test_legacy_codex_command_builder_is_disabled(tmp_path):
    attempt_dir = tmp_path / "attempt_1"
    workspace_dir = attempt_dir / "codex_workspace"
    prompt_file = attempt_dir / "prompt.txt"
    report_file = attempt_dir / "report.json"
    schema_file = attempt_dir / "report_schema.json"

    with pytest.raises(RuntimeError, match="codex-local adapter is disabled"):
        build_codex_exec_command(
            config=HostConfig(adapter="codex-local"),
            workspace_dir=workspace_dir,
            prompt_file=prompt_file,
            report_file=report_file,
            schema_file=schema_file,
            repo_root=Path("/repo/Cogito"),
            python_command=Path("/repo/Cogito/.venv/bin/python"),
        )


def test_codex_local_agent_is_disabled_before_writing_artifacts(tmp_path):
    config = HostConfig(
        adapter="codex-local",
        run_dir=tmp_path,
    )
    context = AttemptContext(
        attempt_id=1,
        max_attempts=3,
        scenario_id="daily_routine_cleanup",
        run_dir=tmp_path,
        reflection=ReflectionMemory(),
    )

    with pytest.raises(RuntimeError, match="codex-local adapter is disabled"):
        asyncio.run(CodexLocalAgent(config).run_attempt(context, None))
    assert not (tmp_path / "attempt_1").exists()


def test_report_schema_requires_every_declared_property_for_strict_outputs():
    schema = report_schema()

    assert set(schema["required"]) == set(schema["properties"])
