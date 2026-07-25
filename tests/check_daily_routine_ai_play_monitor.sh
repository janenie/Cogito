#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

log_file="$(mktemp -t cogito_daily_routine_ai_play_monitor.XXXXXX.log)"
trap 'rm -f "$log_file"' EXIT

set +e
godot --headless --path . --script tests/dailyroutine/test_daily_routine_ai_play_monitor.gd >"$log_file" 2>&1
status=$?
set -e

if grep -Eq 'SCRIPT ERROR|Parse Error|Failed to load script' "$log_file"; then
	cat "$log_file"
	exit 1
fi

if ! grep -q 'Daily routine AI Play monitor test passed' "$log_file"; then
	cat "$log_file"
	exit "${status:-1}"
fi

echo "Daily routine AI Play monitor test passed"
