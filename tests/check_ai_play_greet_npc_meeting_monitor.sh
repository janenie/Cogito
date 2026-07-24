#!/usr/bin/env bash
set -euo pipefail

log_file="$(mktemp -t cogito_greet_npc_meeting_headless.XXXXXX.log)"
trap 'rm -f "$log_file"' EXIT

if ! godot --headless --path . --script tests/ai_play/test_ai_play_greet_npc_meeting_monitor.gd -- --ai-play-scenario=greet_npc_meeting >"$log_file" 2>&1; then
	cat "$log_file"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|invalid UID' "$log_file"; then
	cat "$log_file"
	exit 1
fi

if ! grep -q 'AIPlay greet-npc-meeting monitor test passed' "$log_file"; then
	cat "$log_file"
	exit 1
fi

echo "AIPlay greet-npc-meeting monitor test passed"
