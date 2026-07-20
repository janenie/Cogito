#!/usr/bin/env bash
set -euo pipefail

scene="addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
controller="addons/cogito/AIPlay/ai_play_controller.tscn"

test -f "$controller"
grep -q 'path="res://addons/cogito/AIPlay/ai_play_controller.tscn"' "$scene"
test "$(grep -c 'name="AIPlayController"' "$scene")" -eq 1
controller_block="$(awk '
	/^\[node / {
		if (capture) exit
		capture = ($0 ~ /name="AIPlayController"/)
	}
	capture { print }
' "$scene")"
grep -q 'player = NodePath("../Player")' <<<"$controller_block"
grep -q 'auto_start = false' <<<"$controller_block"
grep -q '^host = "127.0.0.1"$' addons/cogito/AIPlay/ai_play_controller.tscn

if ! tests/check_ai_play_secrets.sh; then
	echo "AI Play tracked files must not contain a credential" >&2
	exit 1
fi
