from __future__ import annotations

import asyncio
import json
import shlex
import sys
from pathlib import Path

from ai_host.attempt_state import AttemptContext, AttemptResult
from ai_host.config import HostConfig
from ai_host.reflection import build_attempt_instructions


class CodexLocalAgent:
    def __init__(self, config: HostConfig) -> None:
        self.config = config

    async def run_attempt(
        self,
        context: AttemptContext,
        mcp_client: object | None,
    ) -> AttemptResult:
        attempt_dir = context.run_dir / f"attempt_{context.attempt_id}"
        workspace_dir = attempt_dir / "codex_workspace"
        prompt_file = attempt_dir / "prompt.txt"
        report_file = attempt_dir / "report.json"
        schema_file = attempt_dir / "report_schema.json"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(_codex_prompt(context), encoding="utf-8")
        schema_file.write_text(
            json.dumps(report_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        command = build_codex_exec_command(
            config=self.config,
            workspace_dir=workspace_dir,
            prompt_file=prompt_file,
            report_file=report_file,
            schema_file=schema_file,
            repo_root=Path.cwd(),
            python_command=Path(sys.executable),
        )
        stdout_file = attempt_dir / "codex_stdout.log"
        stderr_file = attempt_dir / "codex_stderr.log"
        with stdout_file.open("wb") as stdout, stderr_file.open("wb") as stderr:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=workspace_dir,
                stdin=asyncio.subprocess.PIPE,
                stdout=stdout,
                stderr=stderr,
            )
            await process.communicate(prompt_file.read_bytes())
            return_code = process.returncode

        if return_code != 0 and not report_file.is_file():
            return AttemptResult(
                attempt_id=context.attempt_id,
                outcome="unknown",
                reason="codex_command_failed",
                summary=f"codex exited with code {return_code}",
            )
        if not report_file.is_file():
            return AttemptResult(
                attempt_id=context.attempt_id,
                outcome="unknown",
                reason="missing_report",
            )
        try:
            value = json.loads(report_file.read_text(encoding="utf-8"))
            return AttemptResult.from_dict(value)
        except Exception as error:
            return AttemptResult(
                attempt_id=context.attempt_id,
                outcome="unknown",
                reason="invalid_report",
                summary=f"{type(error).__name__}: {error}",
            )


def build_codex_exec_command(
    *,
    config: HostConfig,
    workspace_dir: Path,
    prompt_file: Path,
    report_file: Path,
    schema_file: Path,
    repo_root: Path,
    python_command: Path,
) -> list[str]:
    ai_play_src = repo_root / "ai_play" / "src"
    command = [*shlex.split(config.codex_command), "exec"]
    if config.model:
        command.extend(["--model", config.model])
    command.extend([
        "--cd",
        str(workspace_dir.resolve()),
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--sandbox",
        "read-only",
        "--output-schema",
        str(schema_file.resolve()),
        "--output-last-message",
        str(report_file.resolve()),
        "-c",
        f'model_reasoning_effort="{config.codex_reasoning_effort}"',
        "-c",
        f'mcp_servers.cogito_ai_play.command="{python_command}"',
        "-c",
        'mcp_servers.cogito_ai_play.args=["-m","ai_play.mcp_server"]',
        "-c",
        f'mcp_servers.cogito_ai_play.env={{PYTHONPATH="{ai_play_src}"}}',
        "-",
    ])
    return command


def _codex_prompt(context: AttemptContext) -> str:
    instructions = build_attempt_instructions(
        scenario_id=context.scenario_id,
        attempt_id=context.attempt_id,
        max_attempts=context.max_attempts,
        memory=context.reflection,
    )
    return (
        f"{instructions}\n\n"
        "You are playing a Cogito game through the configured MCP server named "
        "`cogito_ai_play`. Use only the MCP tools for game information and actions. "
        "Do not inspect local files, source code, node paths, or repository contents. "
        "Your local working directory is intentionally empty and is not part of the game. "
        f"You may use at most {context.max_attempts} attempts overall; this is attempt "
        f"{context.attempt_id}. Continue using MCP tools until the game reaches a terminal "
        "success, failure, stopped, or disconnected state, or until you cannot make progress. "
        "Respect the host's MCP interaction budget. Your final response must be only JSON "
        "matching the provided output schema."
    )


def report_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "attempt_id",
            "outcome",
            "reason",
            "summary",
            "mistakes",
            "next_strategy",
            "steps_used",
        ],
        "properties": {
            "attempt_id": {"type": "integer"},
            "outcome": {
                "type": "string",
                "enum": ["success", "failure", "stopped", "unknown"],
            },
            "reason": {"type": "string"},
            "summary": {"type": "string"},
            "mistakes": {"type": "array", "items": {"type": "string"}},
            "next_strategy": {"type": "array", "items": {"type": "string"}},
            "steps_used": {"type": ["integer", "null"]},
        },
    }
