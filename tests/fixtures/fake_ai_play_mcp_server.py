#!/usr/bin/env python3
import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP


parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--marker", type=Path, required=True)
args = parser.parse_args()

mcp = FastMCP(
    "Fake Cogito AI Play",
    host="127.0.0.1",
    port=args.port,
    streamable_http_path="/mcp",
    json_response=True,
)


@mcp.tool()
async def briefing():
    """Read the public game briefing."""
    args.marker.write_text("briefing-called", encoding="utf-8")
    return {"status": "ready", "briefing": {"goal": "integration test"}}


@mcp.tool()
async def observe():
    """Read the latest public observation."""
    return {"status": "ready", "observation_id": 1}


@mcp.tool()
async def act(observation_id: int, actions: list[dict]):
    """Execute one test action."""
    return {"status": "failure", "observation_id": observation_id}


mcp.run(transport="streamable-http")
