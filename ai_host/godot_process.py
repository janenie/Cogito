from __future__ import annotations

import asyncio
from pathlib import Path

from .config import HostConfig


def build_godot_command(config: HostConfig) -> list[str]:
    return [
        config.godot_command,
        "--path",
        ".",
        str(config.scene_path),
        "--",
        "--ai-play",
        f"--ai-play-scenario={config.scenario_id}",
    ]


class GodotAttemptProcess:
    def __init__(self, config: HostConfig, cwd: Path | None = None) -> None:
        self.config = config
        self.cwd = cwd or Path.cwd()
        self.process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            *build_godot_command(self.config),
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
