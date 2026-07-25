from __future__ import annotations

import asyncio
import json
import shlex
from pathlib import Path

from ai_host.attempt_state import AttemptContext, AttemptResult
from ai_host.config import HostConfig
from ai_host.reflection import build_attempt_instructions


class ExternalCommandAgent:
    def __init__(self, config: HostConfig) -> None:
        self.config = config

    async def run_attempt(
        self,
        context: AttemptContext,
        mcp_client: object | None,
    ) -> AttemptResult:
        attempt_dir = context.run_dir / f"attempt_{context.attempt_id}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = attempt_dir / "prompt.txt"
        report_file = attempt_dir / "report.json"
        prompt_file.write_text(
            _external_prompt(context, report_file),
            encoding="utf-8",
        )

        if not self.config.agent_command:
            return AttemptResult(
                attempt_id=context.attempt_id,
                outcome="unknown",
                reason="missing_agent_command",
            )

        command = self.config.agent_command.format(
            repo_root=Path.cwd(),
            prompt_file=prompt_file,
            report_file=report_file,
            run_dir=context.run_dir,
            attempt_id=context.attempt_id,
        )
        process = await asyncio.create_subprocess_exec(*shlex.split(command))
        await process.wait()

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


def _external_prompt(context: AttemptContext, report_file: Path) -> str:
    instructions = build_attempt_instructions(
        scenario_id=context.scenario_id,
        attempt_id=context.attempt_id,
        max_attempts=context.max_attempts,
        memory=context.reflection,
    )
    return (
        f"{instructions}\n\n"
        "Play the configured Cogito MCP game autonomously.\n"
        "At the end, write this JSON report file exactly:\n"
        f"{report_file}\n\n"
        "Required JSON schema:\n"
        '{"attempt_id":1,"outcome":"success|failure|stopped|unknown",'
        '"reason":"cleanup_complete|cleanup_incomplete|max_requests|...",'
        '"summary":"short public summary","mistakes":["..."],'
        '"next_strategy":["..."]}\n'
    )
