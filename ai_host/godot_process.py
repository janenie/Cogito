from __future__ import annotations

import asyncio
from pathlib import Path

from .config import HostConfig


def build_godot_command(config: HostConfig, attempt_id: int = 1) -> list[str]:
    return [
        config.godot_command,
        "--path",
        ".",
        str(config.scene_path),
        "--",
        "--ai-play",
        f"--ai-play-scenario={config.scenario_id}",
        f"--ai-play-seed={1000 + attempt_id}",
    ]


class GodotAttemptProcess:
    def __init__(self, config: HostConfig, cwd: Path | None = None, attempt_id: int = 1) -> None:
        self.config = config
        self.cwd = cwd or Path.cwd()
        self.attempt_id = attempt_id
        self.process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            *build_godot_command(self.config, attempt_id=self.attempt_id),
            cwd=self.cwd,
        )

    async def stop(self, timeout: float = 5.0) -> None:
        if self.process is None:
            return
        if self.process.returncode is not None:
            return
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self.process.kill()
            await self.process.wait()
