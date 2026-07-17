#!/usr/bin/env bash
set -euo pipefail

scene="addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"

if grep -q 'path="res://addons/cogito/CogitoNPC/cogito_npc.tscn"' "$scene"; then
	echo "lobby scene must not instance the original Cogito NPC" >&2
	exit 1
fi

if grep -q 'path="res://addons/cogito/DemoScenes/lobby_friendly_npc.gd"' "$scene"; then
	echo "lobby scene must not attach the original lobby NPC script" >&2
	exit 1
fi

if grep -q 'name="LobbyFriendlyNPC"' "$scene"; then
	echo "lobby scene must not contain the original LobbyFriendlyNPC node" >&2
	exit 1
fi

if grep -q 'name="LobbyFriendlyNPCPath"' "$scene"; then
	echo "lobby scene must not contain the original LobbyFriendlyNPCPath node" >&2
	exit 1
fi
