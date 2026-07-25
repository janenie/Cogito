#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

log_file="$(mktemp -t cogito_home_player_wall_collision.XXXXXX.log)"
trap 'rm -f "$log_file"' EXIT

set +e
godot --headless --path . --script tests/dailyroutine/test_home_player_wall_collision.gd >"$log_file" 2>&1
status=$?
set -e

if grep -Eq 'SCRIPT ERROR|Parse Error|Failed to load script' "$log_file"; then
	cat "$log_file"
	exit 1
fi

if ! grep -q 'Home player wall collision test passed' "$log_file"; then
	cat "$log_file"
	exit "${status:-1}"
fi

echo "Home player wall collision test passed"
