#!/usr/bin/env bash
set -euo pipefail

if command -v rg >/dev/null 2>&1; then
  rg_command=(rg -n 'openai|AI_PLAY_API_KEY|AgentLoop|ApiClient|RunLogger|MemoryStore|build_messages|ai_play\.main' ai_play/src ai_play/start_ai.sh ai_play/.env.example)
else
  rg_command=(grep -RniE 'openai|AI_PLAY_API_KEY|AgentLoop|ApiClient|RunLogger|MemoryStore|build_messages|ai_play\.main' ai_play/src ai_play/start_ai.sh ai_play/.env.example)
fi

if "${rg_command[@]}"; then
  echo "legacy model runtime reference found" >&2
  exit 1
fi

test -f ai_play/src/ai_play/mcp_server.py
test ! -f ai_play/src/ai_play/main.py
