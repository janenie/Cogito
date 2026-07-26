import asyncio
from pathlib import Path

from ai_host.config import HostConfig
from ai_host.godot_process import GodotAttemptProcess, build_godot_command


def test_build_godot_command_enables_ai_play_for_scenario():
    config = HostConfig()

    assert build_godot_command(config, attempt_id=1) == [
        "godot",
        "--path",
        ".",
        "dailyroutine/scenes/home_daily_routine.tscn",
        "--",
        "--ai-play",
        "--ai-play-scenario=daily_routine_cleanup",
        "--ai-play-seed=1001",
    ]


def test_build_godot_command_uses_distinct_seed_per_attempt():
    config = HostConfig()

    attempt_one = build_godot_command(config, attempt_id=1)
    attempt_two = build_godot_command(config, attempt_id=2)

    assert "--ai-play-seed=1001" in attempt_one
    assert "--ai-play-seed=1002" in attempt_two


def test_build_godot_command_uses_overrides():
    config = HostConfig(
        scenario_id="find_key",
        scene_path=Path("addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"),
        godot_command="/opt/godot",
    )

    command = build_godot_command(config, attempt_id=7)
    assert command[0] == "/opt/godot"
    assert command[3] == "addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
    assert command[6] == "--ai-play-scenario=find_key"
    assert command[7] == "--ai-play-seed=1007"


def test_stop_terminates_then_kills_if_needed():
    events = []

    class FakeProcess:
        returncode = None

        def terminate(self):
            events.append("terminate")

        def kill(self):
            events.append("kill")
            self.returncode = -9

        async def wait(self):
            events.append("wait")
            await asyncio.sleep(10)

    process = GodotAttemptProcess(HostConfig())
    process.process = FakeProcess()

    asyncio.run(process.stop(timeout=0.001))

    assert events == ["terminate", "wait", "kill", "wait"]
