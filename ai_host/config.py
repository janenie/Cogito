from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HostConfig:
    scenario_id: str = "daily_routine_cleanup"
    scene_path: Path = Path("dailyroutine/scenes/home_daily_routine.tscn")
    max_attempts: int = 3
    adapter: str = "openai"
    api_mode: str = "responses"
    model: str = "gpt-5.6"
    run_dir: Path = Path("ai_host/runs/latest")
    godot_command: str = "godot"
    mcp_command: Path = Path("ai_play/start_ai.sh")
    agent_command: str | None = None
    codex_command: str = "codex"
    codex_reasoning_effort: str = "xhigh"
    max_agent_turns: int = 1020
    max_mcp_interactions: int = 1000


def parse_args(argv: list[str] | None = None) -> HostConfig:
    parser = argparse.ArgumentParser(
        description="Run Cogito AI Play for multiple fresh attempts."
    )
    parser.add_argument("--scenario", default="daily_routine_cleanup")
    parser.add_argument("--scene", default="dailyroutine/scenes/home_daily_routine.tscn")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--adapter",
        choices=["openai", "external-command", "codex-local"],
        default="openai",
    )
    parser.add_argument("--api-mode", choices=["responses", "chat"], default="responses")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL"))
    parser.add_argument("--run-dir", default="ai_host/runs/latest")
    parser.add_argument("--godot-command", default="godot")
    parser.add_argument("--mcp-command", default="ai_play/start_ai.sh")
    parser.add_argument("--agent-command", default=os.environ.get("AI_HOST_AGENT_COMMAND"))
    parser.add_argument("--codex-command", default=os.environ.get("AI_HOST_CODEX_COMMAND", "codex"))
    parser.add_argument(
        "--codex-reasoning-effort",
        choices=["low", "medium", "high", "xhigh", "max", "ultra"],
        default=os.environ.get("AI_HOST_CODEX_REASONING_EFFORT", "xhigh"),
    )
    parser.add_argument(
        "--max-agent-turns",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--max-mcp-interactions",
        type=int,
        default=int(os.environ.get("AI_HOST_MAX_MCP_INTERACTIONS", "1000")),
        help="Maximum MCP tool calls allowed per game attempt.",
    )
    args = parser.parse_args(argv)
    if args.max_attempts < 1:
        parser.error("--max-attempts must be >= 1")
    if args.max_mcp_interactions < 1:
        parser.error("--max-mcp-interactions must be >= 1")
    max_agent_turns = (
        int(os.environ.get("AI_HOST_MAX_AGENT_TURNS", str(args.max_mcp_interactions + 20)))
        if args.max_agent_turns is None
        else args.max_agent_turns
    )
    if max_agent_turns < 1:
        parser.error("--max-agent-turns must be >= 1")
    model = args.model
    if model is None:
        model = "gpt-5.6-sol" if args.adapter == "codex-local" else "gpt-5.6"
    return HostConfig(
        scenario_id=args.scenario,
        scene_path=Path(args.scene),
        max_attempts=args.max_attempts,
        adapter=args.adapter,
        api_mode=args.api_mode,
        model=model,
        run_dir=Path(args.run_dir),
        godot_command=args.godot_command,
        mcp_command=Path(args.mcp_command),
        agent_command=args.agent_command,
        codex_command=args.codex_command,
        codex_reasoning_effort=args.codex_reasoning_effort,
        max_agent_turns=max_agent_turns,
        max_mcp_interactions=args.max_mcp_interactions,
    )
