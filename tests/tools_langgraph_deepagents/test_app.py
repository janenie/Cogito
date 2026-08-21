import asyncio
from contextlib import asynccontextmanager
import io
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from tools.ai_play_orchestrator_common import RunPaths
from tools_langgraph_deepagents.app import (
    AppDependencies,
    continue_until_supervisor_finishes,
    run,
)
from tools_langgraph_deepagents.console import render_event
from tools_langgraph_deepagents.credentials import YibuCredentials
from tools_langgraph_deepagents.runtime import PreparedRun


@pytest.mark.asyncio
async def test_agent_final_is_continued_while_supervisor_is_running():
    prompts: list[str] = []
    second_started = asyncio.Event()

    class Agent:
        async def astream(self, payload, config, stream_mode):
            prompts.append(payload["messages"][0].content)
            yield {"model": {"messages": [AIMessage(content="update")]}}
            if len(prompts) > 1:
                second_started.set()
                await asyncio.Event().wait()

    class Supervisor:
        returncode = None

        async def wait(self):
            await second_started.wait()
            self.returncode = 0
            return 0

    result = await continue_until_supervisor_finishes(
        agent=Agent(),
        supervisor=Supervisor(),
        graph_config={"configurable": {"thread_id": "thread"}},
        first_prompt="start",
        continuation_prompt="continue",
        render=lambda _event: None,
    )

    assert result == 0
    assert prompts == ["start", "continue"]


def test_console_never_prints_base64_or_raw_tool_payload():
    output = io.StringIO()
    event = {
        "model": {
            "messages": [
                AIMessage(
                    content=[
                        {
                            "type": "text",
                            "text": (
                                "visible caption "
                                "data:image/jpeg;base64,VERY_SECRET_BASE64"
                            ),
                        },
                        {
                            "type": "image",
                            "base64": "VERY_SECRET_BASE64",
                            "mime_type": "image/jpeg",
                        },
                    ],
                    tool_calls=[
                        {
                            "name": "act",
                            "args": {"secret": "DO_NOT_PRINT"},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content=(
                        '{"status":"ready","observation":'
                        '{"observation_id":7},"secret":"DO_NOT_PRINT"}'
                    ),
                    tool_call_id="call-1",
                    name="act",
                ),
            ]
        }
    }

    render_event(event, output=output)
    rendered = output.getvalue()

    assert "visible caption" in rendered
    assert "[image image/jpeg]" in rendered
    assert "act" in rendered
    assert "observation_id=7" in rendered
    assert "VERY_SECRET_BASE64" not in rendered
    assert "DO_NOT_PRINT" not in rendered


@pytest.mark.asyncio
async def test_run_uses_one_session_and_stops_before_close(tmp_path: Path):
    events: list[str] = []
    commands: list[list[str]] = []
    second_started = asyncio.Event()
    run_dir = tmp_path / "run"
    runtime_dir = tmp_path / "runtime"
    log_root = run_dir / "trusted_mcplogs"
    player_workspace = runtime_dir / "player_workspace"
    for directory in (log_root, player_workspace):
        directory.mkdir(parents=True)
    paths = RunPaths(
        run_dir=run_dir,
        runtime_dir=runtime_dir,
        player_workspace=player_workspace,
        log_root=log_root,
        session_metadata=run_dir / "session.json",
    )
    prepared = PreparedRun(
        paths=paths,
        scene="scene.tscn",
        completed_runs=0,
        remaining_runs=3,
        thread_id="thread",
        checkpoint_path=run_dir / "checkpoint.sqlite",
        workflow_memory_path=log_root / "workflow_memory.json",
    )

    class Session:
        async def call_tool(self, name, arguments=None):
            events.append(f"tool:{name}")

    session = Session()

    class Client:
        @asynccontextmanager
        async def session(self, name):
            events.append(f"session-enter:{name}")
            try:
                yield session
            finally:
                events.append("session-exit")

    class Agent:
        async def astream(self, payload, config, stream_mode):
            events.append("agent-turn")
            yield {"model": {"messages": [AIMessage(content="done")]}}
            if events.count("agent-turn") > 1:
                second_started.set()
                await asyncio.Event().wait()

    class Supervisor:
        returncode = None

        async def wait(self):
            await second_started.wait()
            self.returncode = 0
            return 0

    @asynccontextmanager
    async def checkpointer(_path):
        events.append("checkpoint-enter")
        try:
            yield object()
        finally:
            events.append("checkpoint-exit")

    @asynccontextmanager
    async def supervisor_context(command, **_kwargs):
        commands.append(list(command))
        events.append("supervisor-enter")
        try:
            yield Supervisor()
        finally:
            events.append("supervisor-exit")

    dependencies = AppDependencies(
        confirm=lambda **_kwargs: True,
        load_credentials=lambda _path, _name: YibuCredentials(
            "test-only", "https://example.invalid/v1"
        ),
        prepare=lambda _args: prepared,
        build_mcp_client=lambda **_kwargs: Client(),
        load_tools=lambda *_args, **_kwargs: asyncio.sleep(
            0, result=[SimpleNamespace(name="briefing")]
        ),
        open_checkpointer=checkpointer,
        build_model=lambda *_args, **_kwargs: object(),
        build_agent=lambda **_kwargs: Agent(),
        supervisor_context=supervisor_context,
        render=lambda _event: None,
    )
    args = SimpleNamespace(
        yibu_credentials=Path("unused"),
        credential_name="ak",
        model="gemini-3.6-flash",
        scenario="find_contract",
        runs=3,
        confirm_external_run=True,
        python_bin=sys.executable,
        godot_bin="godot",
        max_retries=2,
        timeout_seconds=100,
        benchmark_cycle_seed=42,
        workflow_memory="enabled",
        model_timeout_seconds=30,
        model_max_retries=0,
        max_output_tokens=4096,
    )

    result = await run(args, dependencies=dependencies)

    assert result == 0
    assert events.count("session-enter:cogito_ai_play") == 1
    assert events.count("agent-turn") == 2
    assert all("codex" not in " ".join(command).lower() for command in commands)
    assert events.index("tool:stop") < events.index("supervisor-exit")
    assert events.index("supervisor-exit") < events.index("checkpoint-exit")
    assert events.index("checkpoint-exit") < events.index("session-exit")


@pytest.mark.asyncio
async def test_cancelled_run_stops_before_mcp_session_closes(tmp_path: Path):
    events: list[str] = []
    started = asyncio.Event()
    run_dir = tmp_path / "run"
    runtime_dir = tmp_path / "runtime"
    log_root = run_dir / "trusted_mcplogs"
    player_workspace = runtime_dir / "player_workspace"
    for directory in (log_root, player_workspace):
        directory.mkdir(parents=True)
    prepared = PreparedRun(
        paths=RunPaths(
            run_dir=run_dir,
            runtime_dir=runtime_dir,
            player_workspace=player_workspace,
            log_root=log_root,
            session_metadata=run_dir / "session.json",
        ),
        scene="scene.tscn",
        completed_runs=0,
        remaining_runs=1,
        thread_id="thread",
        checkpoint_path=run_dir / "checkpoint.sqlite",
        workflow_memory_path=log_root / "workflow_memory.json",
    )

    class Session:
        async def call_tool(self, name, arguments=None):
            events.append(f"tool:{name}")

    class Client:
        @asynccontextmanager
        async def session(self, _name):
            events.append("session-enter")
            try:
                yield Session()
            finally:
                events.append("session-exit")

    class Agent:
        async def astream(self, payload, config, stream_mode):
            started.set()
            yield {"model": {"messages": []}}
            await asyncio.Event().wait()

    class Supervisor:
        returncode = None

        async def wait(self):
            await asyncio.Event().wait()

    @asynccontextmanager
    async def passthrough(_value):
        yield object()

    @asynccontextmanager
    async def supervisor_context(_command, **_kwargs):
        events.append("supervisor-enter")
        try:
            yield Supervisor()
        finally:
            events.append("supervisor-exit")

    dependencies = AppDependencies(
        confirm=lambda **_kwargs: True,
        load_credentials=lambda *_args: YibuCredentials(
            "test-only", "https://example.invalid/v1"
        ),
        prepare=lambda _args: prepared,
        build_mcp_client=lambda **_kwargs: Client(),
        load_tools=lambda *_args, **_kwargs: asyncio.sleep(
            0, result=[SimpleNamespace(name="briefing")]
        ),
        open_checkpointer=passthrough,
        build_model=lambda *_args, **_kwargs: object(),
        build_agent=lambda **_kwargs: Agent(),
        supervisor_context=supervisor_context,
        render=lambda _event: None,
    )
    args = SimpleNamespace(
        yibu_credentials=Path("unused"),
        credential_name="ak",
        model="gemini-3.6-flash",
        scenario="find_contract",
        runs=1,
        confirm_external_run=True,
        python_bin=sys.executable,
        godot_bin="godot",
        max_retries=0,
        timeout_seconds=100,
        benchmark_cycle_seed=42,
        workflow_memory="disabled",
        model_timeout_seconds=30,
        model_max_retries=0,
        max_output_tokens=4096,
    )
    task = asyncio.create_task(run(args, dependencies=dependencies))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert events.index("tool:stop") < events.index("supervisor-exit")
    assert events.index("supervisor-exit") < events.index("session-exit")
