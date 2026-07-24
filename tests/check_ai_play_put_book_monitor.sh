#!/usr/bin/env bash
set -euo pipefail

log_file="$(mktemp -t cogito_put_book_headless.XXXXXX.log)"
trap 'rm -f "$log_file"' EXIT

if ! godot --headless --path . --script tests/ai_play/test_ai_play_put_book_monitor.gd -- --ai-play-scenario=put_book >"$log_file" 2>&1; then
	cat "$log_file"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|invalid UID' "$log_file"; then
	cat "$log_file"
	exit 1
fi

if ! grep -q 'AIPlay put-book monitor test passed' "$log_file"; then
	cat "$log_file"
	exit 1
fi

echo "AIPlay put-book monitor test passed"
