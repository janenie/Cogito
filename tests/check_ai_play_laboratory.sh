#!/usr/bin/env bash
set -euo pipefail

test_log="$(mktemp -t cogito_laboratory.XXXXXX.log)"
trap 'rm -f "$test_log"' EXIT

if ! godot --headless --path . \
	--script tests/ai_play/test_ai_play_laboratory.gd \
	-- --ai-play-scenario=laboratory_experiment >"$test_log" 2>&1
then
	cat "$test_log"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|Parse Error|Compile Error|invalid UID|FAILED:' "$test_log" \
	|| ! grep -q 'AIPlay laboratory integration test passed' "$test_log"
then
	cat "$test_log"
	exit 1
fi

echo "AIPlay laboratory integration test passed without script errors"
