#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
	echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/pip install -r ai_play/requirements.txt" >&2
	exit 1
fi

PYTHONPATH=ai_play/src .venv/bin/python -m ai_play.mcp_server "$@"
