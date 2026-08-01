#!/usr/bin/env bash
set -euo pipefail

selected_log="$(mktemp -t cogito_meeting_briefing_selected.XXXXXX.log)"
isolation_log="$(mktemp -t cogito_meeting_briefing_isolation.XXXXXX.log)"
trap 'rm -f "$selected_log" "$isolation_log"' EXIT

if ! godot --headless --path . \
	--script tests/ai_play/test_ai_play_arrange_meeting_briefings_monitor.gd \
	-- --ai-play-scenario=arrange_meeting_briefings >"$selected_log" 2>&1
then
	cat "$selected_log"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|Parse Error|Compile Error|invalid UID|FAILED:' "$selected_log" \
	|| ! grep -q 'AIPlay meeting-briefing selected test passed' "$selected_log"
then
	cat "$selected_log"
	exit 1
fi

if ! godot --headless --path . \
	--script tests/ai_play/test_ai_play_arrange_meeting_briefings_monitor.gd \
	>"$isolation_log" 2>&1
then
	cat "$isolation_log"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|Parse Error|Compile Error|invalid UID|FAILED:' "$isolation_log" \
	|| ! grep -q 'AIPlay meeting-briefing isolation test passed' "$isolation_log"
then
	cat "$isolation_log"
	exit 1
fi

echo "AIPlay meeting-briefing selected and isolation tests passed"
