from __future__ import annotations

import asyncio

from .config import parse_args
from .openai_key import ensure_openai_api_key
from .runner import run_host


def main() -> None:
    config = parse_args()
    if config.adapter == "openai":
        ensure_openai_api_key()
    report = asyncio.run(run_host(config))
    print(f"ai_host finished: success={report.success} attempts={len(report.attempts)}")
    print(f"report: {config.run_dir / 'final_report.json'}")


if __name__ == "__main__":
    main()
