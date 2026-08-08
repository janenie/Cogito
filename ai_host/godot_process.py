from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Mapping

from .config import HostConfig


SAFE_GODOT_ENV_NAMES = (
    "PATH",
    "PATHEXT",
    "SystemRoot",
    "WINDIR",
    "ComSpec",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XDG_RUNTIME_DIR",
    "DBUS_SESSION_BUS_ADDRESS",
    "LD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
)


def build_godot_env(
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if base_env is None else base_env
    env: dict[str, str] = {}
    for name in SAFE_GODOT_ENV_NAMES:
        value = source.get(name)
        if value is None:
            value = next(
                (
                    candidate
                    for candidate_name, candidate in source.items()
                    if candidate_name.casefold() == name.casefold()
                ),
                None,
            )
        if value is not None:
            env[name] = value
    return env


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
            env=build_godot_env(),
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
