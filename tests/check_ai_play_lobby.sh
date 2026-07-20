#!/usr/bin/env bash
set -euo pipefail

scene="addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
controller="addons/cogito/AIPlay/ai_play_controller.tscn"

test -f "$controller"
grep -q 'path="res://addons/cogito/AIPlay/ai_play_controller.tscn"' "$scene"
grep -q 'name="AIPlayController"' "$scene"
grep -q 'player = NodePath("../Player")' "$scene"
grep -q 'auto_start = false' "$scene"

if rg -n 'AI_PLAY_API_KEY=[^[:space:]]+' ai_play addons/cogito/AIPlay \
  -g '!*.example' -g '!test_*.py'; then
	echo "AI Play source must not contain a credential" >&2
	exit 1
fi

# Literal assignments are credentials; normal SDK wiring such as api_key=config.api_key is safe.
if rg -n "api_key[[:space:]]*=[[:space:]]*['\"]" ai_play/src addons/cogito/AIPlay; then
	echo "AI Play source must not contain a credential" >&2
	exit 1
fi
