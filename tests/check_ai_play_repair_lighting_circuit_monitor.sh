#!/usr/bin/env bash
set -euo pipefail

selected_log="$(mktemp -t cogito_lighting_circuit_selected.XXXXXX.log)"
isolation_log="$(mktemp -t cogito_lighting_circuit_isolation.XXXXXX.log)"
trap 'rm -f "$selected_log" "$isolation_log"' EXIT

if ! godot --headless --path . \
	--script tests/ai_play/test_ai_play_repair_lighting_circuit_monitor.gd \
	-- --ai-play-scenario=repair_lighting_circuit >"$selected_log" 2>&1
then
	cat "$selected_log"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|invalid UID' "$selected_log" \
	|| ! grep -q 'AIPlay lighting-circuit selected test passed' "$selected_log"
then
	cat "$selected_log"
	exit 1
fi

if ! godot --headless --path . \
	--script tests/ai_play/test_ai_play_repair_lighting_circuit_monitor.gd \
	>"$isolation_log" 2>&1
then
	cat "$isolation_log"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|invalid UID' "$isolation_log" \
	|| ! grep -q 'AIPlay lighting-circuit isolation test passed' "$isolation_log"
then
	cat "$isolation_log"
	exit 1
fi

echo "AIPlay lighting-circuit selected and isolation tests passed"
