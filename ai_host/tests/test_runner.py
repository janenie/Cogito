import asyncio
from pathlib import Path

from ai_host.attempt_state import AttemptResult
from ai_host.config import HostConfig
from ai_host.runner import run_host


def test_runner_stops_after_first_success(tmp_path):
    events = []

    class FakeGodot:
        def __init__(self, config):
            self.config = config

        async def start(self):
            events.append("start")

        async def stop(self):
            events.append("stop")

    class FakeAgent:
        async def run_attempt(self, context, mcp_client):
            events.append(f"attempt-{context.attempt_id}")
            return AttemptResult(attempt_id=context.attempt_id, outcome="success", reason="cleanup_complete")

    report = asyncio.run(run_host(
        HostConfig(run_dir=tmp_path),
        agent_factory=lambda config: FakeAgent(),
        godot_factory=lambda config: FakeGodot(config),
        mcp_client_factory=lambda config: None,
    ))

    assert events == ["start", "attempt-1", "stop"]
    assert report.success
    assert len(report.attempts) == 1


def test_runner_restarts_and_passes_reflection_after_failure(tmp_path):
    seen_strategies = []

    class FakeGodot:
        def __init__(self, config):
            self.config = config

        async def start(self):
            pass

        async def stop(self):
            pass

    class FakeAgent:
        async def run_attempt(self, context, mcp_client):
            seen_strategies.append(list(context.reflection.strategy))
            if context.attempt_id == 1:
                return AttemptResult(
                    attempt_id=1,
                    outcome="failure",
                    reason="cleanup_incomplete",
                    mistakes=["submitted too early"],
                    next_strategy=["check HUD before finishing"],
                )
            return AttemptResult(attempt_id=2, outcome="success", reason="cleanup_complete")

    report = asyncio.run(run_host(
        HostConfig(run_dir=tmp_path),
        agent_factory=lambda config: FakeAgent(),
        godot_factory=lambda config: FakeGodot(config),
        mcp_client_factory=lambda config: None,
    ))

    assert seen_strategies == [[], ["check HUD before finishing"]]
    assert report.success
    assert len(report.attempts) == 2
    assert (tmp_path / "final_report.json").is_file()


def test_external_command_runner_does_not_create_default_mcp_client(tmp_path):
    seen_mcp_clients = []

    class FakeGodot:
        def __init__(self, config):
            self.config = config

        async def start(self):
            pass

        async def stop(self):
            pass

    class FakeAgent:
        async def run_attempt(self, context, mcp_client):
            seen_mcp_clients.append(mcp_client)
            return AttemptResult(
                attempt_id=context.attempt_id,
                outcome="success",
                reason="cleanup_complete",
            )

    asyncio.run(run_host(
        HostConfig(run_dir=tmp_path, adapter="external-command"),
        agent_factory=lambda config: FakeAgent(),
        godot_factory=lambda config: FakeGodot(config),
    ))

    assert seen_mcp_clients == [None]


def test_runner_sanitizes_attempt_reflection_before_carryover(tmp_path):
    seen_strategies = []

    class FakeGodot:
        def __init__(self, config):
            self.config = config

        async def start(self):
            pass

        async def stop(self):
            pass

    class FakeAgent:
        async def run_attempt(self, context, mcp_client):
            seen_strategies.append(list(context.reflection.strategy))
            if context.attempt_id == 1:
                return AttemptResult(
                    attempt_id=1,
                    outcome="failure",
                    reason="cleanup_incomplete",
                    next_strategy=["go to NodePath('../../Secret') then check HUD"],
                )
            return AttemptResult(
                attempt_id=2,
                outcome="failure",
                reason="cleanup_incomplete",
            )

    asyncio.run(run_host(
        HostConfig(run_dir=tmp_path, max_attempts=2),
        agent_factory=lambda config: FakeAgent(),
        godot_factory=lambda config: FakeGodot(config),
        mcp_client_factory=lambda config: None,
    ))

    assert "NodePath" not in seen_strategies[1][0]
    assert "check HUD" in seen_strategies[1][0]
