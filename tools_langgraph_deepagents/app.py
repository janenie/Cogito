from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from tools.ai_play_orchestrator_common import (
    DEFAULT_WS_PORT,
    build_supervisor_command,
    build_supervisor_env,
    build_trusted_mcp_env,
)
from tools_langgraph_deepagents.agent import build_game_agent
from tools_langgraph_deepagents.config import REPO_ROOT
from tools_langgraph_deepagents.console import render_event
from tools_langgraph_deepagents.credentials import load_yibu_credentials
from tools_langgraph_deepagents.mcp_tools import (
    MCP_SERVER_NAME,
    build_mcp_client,
    load_player_tools,
)
from tools_langgraph_deepagents.model import build_yibu_chat_model
from tools_langgraph_deepagents.prompt import build_system_prompt
from tools_langgraph_deepagents.runtime import (
    confirm_external_run,
    prepare_run,
    supervisor_process,
)


FIRST_PROMPT = (
    "Start the supervised game now. Follow the system loop autonomously "
    "until all requested formal runs are complete."
)
CONTINUATION_PROMPT = (
    "The supervisor is still running and the requested formal-terminal "
    "count is not complete. Continue from the current public game state; "
    "do not repeat briefing and do not ask the user for guidance."
)


@dataclass(frozen=True)
class AppDependencies:
    confirm: Callable[..., bool] = confirm_external_run
    load_credentials: Callable[..., Any] = load_yibu_credentials
    prepare: Callable[..., Any] = prepare_run
    build_mcp_client: Callable[..., Any] = build_mcp_client
    load_tools: Callable[..., Any] = load_player_tools
    open_checkpointer: Callable[..., Any] = (
        AsyncSqliteSaver.from_conn_string
    )
    build_model: Callable[..., Any] = build_yibu_chat_model
    build_agent: Callable[..., Any] = build_game_agent
    supervisor_context: Callable[..., Any] = supervisor_process
    render: Callable[[Any], None] = render_event


async def _stream_once(
    agent: Any,
    graph_config: dict[str, Any],
    prompt: str,
    render: Callable[[Any], None],
) -> None:
    payload = {"messages": [HumanMessage(content=prompt)]}
    async for event in agent.astream(
        payload,
        graph_config,
        stream_mode="updates",
    ):
        render(event)


async def continue_until_supervisor_finishes(
    *,
    agent: Any,
    supervisor: Any,
    graph_config: dict[str, Any],
    first_prompt: str,
    continuation_prompt: str,
    render: Callable[[Any], None],
) -> int:
    prompt = first_prompt
    while supervisor.returncode is None:
        agent_task = asyncio.create_task(
            _stream_once(agent, graph_config, prompt, render)
        )
        supervisor_task = asyncio.create_task(supervisor.wait())
        try:
            done, _pending = await asyncio.wait(
                {agent_task, supervisor_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
        except BaseException:
            agent_task.cancel()
            supervisor_task.cancel()
            await asyncio.gather(
                agent_task,
                supervisor_task,
                return_exceptions=True,
            )
            raise
        if supervisor_task in done:
            agent_task.cancel()
            with suppress(asyncio.CancelledError):
                await agent_task
            return supervisor_task.result()
        supervisor_task.cancel()
        with suppress(asyncio.CancelledError):
            await supervisor_task
        await agent_task
        prompt = continuation_prompt
    return supervisor.returncode


async def _stop_mcp_session(session: Any) -> None:
    stop_task = asyncio.create_task(session.call_tool("stop", {}))
    try:
        await asyncio.shield(asyncio.wait_for(stop_task, timeout=5.0))
    except asyncio.CancelledError:
        with suppress(Exception):
            await stop_task
        raise
    except Exception:
        stop_task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await stop_task


async def run(
    args: Any,
    *,
    dependencies: AppDependencies | None = None,
) -> int:
    deps = dependencies or AppDependencies()
    credentials = deps.load_credentials(
        args.yibu_credentials,
        args.credential_name,
    )
    if not deps.confirm(
        confirmed=args.confirm_external_run,
        model=args.model,
        scenario=args.scenario,
        runs=args.runs,
    ):
        print("External run cancelled; no child process was started.")
        return 2

    prepared = deps.prepare(args)
    workflow_memory_enabled = args.workflow_memory == "enabled"
    mcp_env = build_trusted_mcp_env(
        prepared.paths.log_root,
        DEFAULT_WS_PORT,
        workflow_memory_path=prepared.workflow_memory_path,
    )
    supervisor_env = build_supervisor_env(
        prepared.paths.runtime_dir / "godot_environment"
    )
    supervisor_command = build_supervisor_command(
        python_bin=args.python_bin,
        runs=prepared.remaining_runs,
        scenario=args.scenario,
        scene=prepared.scene,
        godot_bin=args.godot_bin,
        max_retries=args.max_retries,
        timeout_seconds=args.timeout_seconds,
        benchmark_cycle_seed=args.benchmark_cycle_seed,
        attempt_offset=prepared.completed_runs,
    )
    client = deps.build_mcp_client(
        python_bin=args.python_bin,
        repo_root=REPO_ROOT,
        env=mcp_env,
    )

    print(f"[deepagents] run_dir={prepared.paths.run_dir}", flush=True)
    print(
        "[deepagents] progress="
        f"{prepared.completed_runs}/{args.runs} "
        f"remaining={prepared.remaining_runs}",
        flush=True,
    )
    graph_config = {
        "configurable": {"thread_id": prepared.thread_id},
        "recursion_limit": 9_999,
    }
    supervisor_log = prepared.paths.log_root / "supervisor.log"

    async with client.session(MCP_SERVER_NAME) as session:
        stop_sent = False
        try:
            tools = await deps.load_tools(
                client,
                session,
                workflow_memory_enabled=workflow_memory_enabled,
            )
            async with deps.open_checkpointer(
                str(prepared.checkpoint_path)
            ) as checkpointer:
                model = deps.build_model(
                    credentials,
                    model=args.model,
                    timeout_seconds=args.model_timeout_seconds,
                    max_retries=args.model_max_retries,
                    max_output_tokens=args.max_output_tokens,
                )
                agent = deps.build_agent(
                    model=model,
                    tools=tools,
                    system_prompt=build_system_prompt(
                        runs=args.runs,
                        workflow_memory_enabled=workflow_memory_enabled,
                    ),
                    checkpointer=checkpointer,
                )
                with supervisor_log.open("a", encoding="utf-8") as output:
                    async with deps.supervisor_context(
                        supervisor_command,
                        cwd=REPO_ROOT,
                        env=supervisor_env,
                        output=output,
                    ) as supervisor:
                        try:
                            exit_code = (
                                await continue_until_supervisor_finishes(
                                    agent=agent,
                                    supervisor=supervisor,
                                    graph_config=graph_config,
                                    first_prompt=FIRST_PROMPT,
                                    continuation_prompt=CONTINUATION_PROMPT,
                                    render=deps.render,
                                )
                            )
                            return exit_code if exit_code in {0, 1} else 2
                        finally:
                            stop_sent = True
                            await _stop_mcp_session(session)
        finally:
            if not stop_sent:
                await _stop_mcp_session(session)
