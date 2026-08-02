#!/usr/bin/env bash
set -euo pipefail

manager_log="$(mktemp -t cogito_loop_manager.XXXXXX.log)"
scene_log="$(mktemp -t cogito_loop_scene.XXXXXX.log)"
trap 'rm -f "$manager_log" "$scene_log"' EXIT

if ! godot --headless --path . \
	--script tests/ai_play/test_loop_staircase_manager.gd >"$manager_log" 2>&1
then
	cat "$manager_log"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|Parse Error|Compile Error|invalid UID|FAILED:' "$manager_log" \
	|| ! grep -q 'Loop staircase manager test passed' "$manager_log"
then
	cat "$manager_log"
	exit 1
fi

if ! godot --headless --path . \
	--script tests/ai_play/test_loop_staircase_scene.gd \
	-- --ai-play-scenario=loop_staircase_anomaly >"$scene_log" 2>&1
then
	cat "$scene_log"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|Parse Error|Compile Error|invalid UID|FAILED:' "$scene_log" \
	|| ! grep -q 'Loop staircase scene test passed' "$scene_log"
then
	cat "$scene_log"
	exit 1
fi

echo "Loop staircase manager and scene tests passed without script errors"
