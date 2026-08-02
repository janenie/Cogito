from __future__ import annotations

from contextlib import suppress

from .agents.codex_local import CodexLocalAgent
from .agents.external_command import ExternalCommandAgent
from .agents.openai_responses import OpenAIResponsesAgent
from .attempt_state import AttemptContext, AttemptResult, FinalReport, ReflectionMemory
from .config import HostConfig
from .godot_process import GodotAttemptProcess
from .mcp_client import McpGameClient
from .reflection import sanitize_items, sanitize_reflection


def default_agent_factory(config: HostConfig):
    if config.adapter == "codex-local":
        raise RuntimeError(
            "legacy codex-local adapter is disabled; use "
            "tools/ai_play_codex_orchestrator.py"
        )
    if config.adapter == "external-command":
        return ExternalCommandAgent(config)
    return OpenAIResponsesAgent(config)


async def run_host(
    config: HostConfig,
    *,
    agent_factory=default_agent_factory,
    godot_factory=GodotAttemptProcess,
    mcp_client_factory=None,
) -> FinalReport:
    if config.adapter == "codex-local":
        raise RuntimeError(
            "legacy codex-local adapter is disabled; use "
            "tools/ai_play_codex_orchestrator.py"
        )
    config.run_dir.mkdir(parents=True, exist_ok=True)
    attempts: list[AttemptResult] = []
    reflection = ReflectionMemory()

    for attempt_id in range(1, config.max_attempts + 1):
        try:
            godot = godot_factory(config, attempt_id=attempt_id)
        except TypeError:
            godot = godot_factory(config)
        if mcp_client_factory is not None:
            mcp_client = mcp_client_factory(config)
        elif config.adapter == "openai":
            mcp_client = McpGameClient(config)
        else:
            mcp_client = None
        agent = agent_factory(config)
        context = AttemptContext(
            attempt_id=attempt_id,
            max_attempts=config.max_attempts,
            scenario_id=config.scenario_id,
            run_dir=config.run_dir,
            reflection=reflection,
        )
        try:
            await godot.start()
            if mcp_client is not None and hasattr(mcp_client, "connect"):
                await mcp_client.connect()
            result = await agent.run_attempt(context, mcp_client)
        except Exception as error:
            result = AttemptResult(
                attempt_id=attempt_id,
                outcome="unknown",
                reason="host_exception",
                summary=f"{type(error).__name__}: {error}",
            )
        finally:
            if mcp_client is not None and hasattr(mcp_client, "stop"):
                with suppress(Exception):
                    await mcp_client.stop()
            await godot.stop()

        result = _sanitize_attempt_result(result)
        attempts.append(result)
        if result.success:
            break
        reflection = ReflectionMemory(
            mistakes=result.mistakes,
            strategy=result.next_strategy,
        )

    report = FinalReport(attempts=attempts, run_dir=config.run_dir)
    report.write()
    return report


def _sanitize_attempt_result(result: AttemptResult) -> AttemptResult:
    result.summary = sanitize_reflection(result.summary)
    result.mistakes = sanitize_items(result.mistakes)
    result.next_strategy = sanitize_items(result.next_strategy)
    return result
