from __future__ import annotations

from pathlib import Path

from ai_host.attempt_state import AttemptContext, AttemptResult
from ai_host.config import HostConfig


_DISABLED_MESSAGE = (
    "legacy codex-local adapter is disabled; use "
    "tools/ai_play_codex_orchestrator.py"
)


class CodexLocalAgent:
    def __init__(self, config: HostConfig) -> None:
        self.config = config

    async def run_attempt(
        self,
        context: AttemptContext,
        mcp_client: object | None,
    ) -> AttemptResult:
        raise RuntimeError(_DISABLED_MESSAGE)


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
    raise RuntimeError(_DISABLED_MESSAGE)


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
