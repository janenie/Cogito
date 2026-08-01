#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

log_file="$(mktemp -t cogito_ai_play_game_over_screen.XXXXXX.log)"
trap 'rm -f "$log_file"' EXIT

godot_bin="${GODOT_BIN:-godot}"
"$godot_bin" --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd >"$log_file" 2>&1 &
godot_pid=$!
deadline=$((SECONDS + 40))

while kill -0 "$godot_pid" 2>/dev/null; do
	if (( SECONDS >= deadline )); then
		kill -TERM "$godot_pid" 2>/dev/null || true
		wait "$godot_pid" || true
		cat "$log_file"
		exit 1
	fi
	sleep 1
done

set +e
wait "$godot_pid"
status=$?
set -e

if (( status != 0 )) || grep -Eq 'SCRIPT ERROR|Parse Error|Failed to load script|ERROR:' "$log_file"; then
	cat "$log_file"
	exit 1
fi

if ! grep -Fxq 'AIPlay game-over screen tests passed' "$log_file"; then
	cat "$log_file"
	exit 1
fi

echo "AIPlay game-over screen tests passed"
