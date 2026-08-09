#!/usr/bin/env bash
set -euo pipefail

scene="addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
monitor="addons/cogito/AIPlay/ai_play_find_key_monitor.gd"

while IFS='|' read -r key_name parent_path
do
	grep -q "^\[node name=\"$key_name\" parent=\"$parent_path\"" "$scene"
	grep -q "^\[node name=\"FindKeyCandidates\" type=\"Node3D\" parent=\"$parent_path\"" "$scene"
	for candidate_index in 1 2 3
	do
		grep -q "^\[node name=\"Candidate$candidate_index\" type=\"Marker3D\" parent=\"$parent_path/FindKeyCandidates\"" "$scene"
	done
done <<'EOF'
MainLobbyKey|MAIN_LOBBY/LAB_CONNECTOR/LaboratoryClueDesk/AnimatableBody3D
CEOOfficeKey|UPPER_OFFICE_CEO/deskCorner/Drawer
ArchiveKey|ARCHIVE
MeetingRoomKey|MEETING_ROOM
BreakRoomKey|BREAK_ROOM
CubicleAreaKey|CUBICLE_AREA
EOF

if grep -Eq '(ceo_key|main_lobby_key)\.reparent\(' "$monitor"; then
	echo "find-key keys must not be reparented at runtime" >&2
	exit 1
fi
