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

grep -q 'stdio MCP' ai_play/README.md
grep -q 'observe' ai_play/README.md
grep -q 'act' ai_play/README.md
grep -q 'stop' ai_play/README.md
grep -q -- '-- --ai-play' ai_play/README.md
if grep -nE 'AI_PLAY_API_KEY|OpenAI\(|AI_PLAY_MODEL|memory\.json|RunLogger|AgentLoop' ai_play/README.md; then
  echo "legacy credential/model documentation found" >&2
  exit 1
fi
