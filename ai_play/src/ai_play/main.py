from __future__ import annotations

import argparse
import sys

from .agent_loop import AgentLoop
from .api_client import ApiClient
from .bridge_server import serve
from .config import Config
from .memory import MemoryStore
from .run_logger import RunLogger


def main(argv=None, config=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

    if config is None:
        config = Config.from_env()
    memory_path = None
    if config.data_dir is not None:
        memory_dir = config.data_dir / "ai_play"
        memory_dir.mkdir(parents=True, exist_ok=True)
        memory_path = memory_dir / "memory.json"
    memory = (
        MemoryStore.load(memory_path)
        if args.resume and memory_path is not None
        else MemoryStore.empty()
    )
    run_logger = RunLogger.create(config.log_root, config.model)
    try:
        agent_loop = AgentLoop(
            ApiClient(config),
            memory,
            memory_path=memory_path,
            resume=args.resume,
            run_logger=run_logger,
        )
        print(f"{config.ws_host}:{config.ws_port} {config.model}")
        print(f"AI_PLAY logs: {run_logger.run_dir}")
        serve(config, agent_loop)
    finally:
        run_logger.close()


def _run_cli(argv=None) -> int:
    try:
        config = Config.from_env()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    main(argv, config=config)
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_cli())
