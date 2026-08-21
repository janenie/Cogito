from __future__ import annotations

import asyncio
import sys

from tools_langgraph_deepagents.app import run
from tools_langgraph_deepagents.config import parse_args


def main() -> int:
    try:
        return asyncio.run(run(parse_args(sys.argv[1:])))
    except KeyboardInterrupt:
        return 130
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
