from __future__ import annotations

import argparse

from .agent_loop import AgentLoop
from .api_client import ApiClient
from .bridge_server import serve
from .config import Config
from .memory import MemoryStore


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)

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
    agent_loop = AgentLoop(
        ApiClient(config),
        memory,
        memory_path=memory_path,
        resume=args.resume,
    )
    print(f"{config.ws_host}:{config.ws_port} {config.model}")
    serve(config, agent_loop)


if __name__ == "__main__":
    main()
