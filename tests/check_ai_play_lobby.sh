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
grep -q '^auto_start = false$' "$controller"
if grep -q 'auto_start = true' <<<"$controller_block"; then
	echo "Lobby must not override AIPlayController auto_start to true" >&2
	exit 1
fi
grep -q '^host = "127.0.0.1"$' addons/cogito/AIPlay/ai_play_controller.tscn
grep -q 'path="res://addons/cogito/AIPlay/ai_play_game_over_screen.tscn"' "$scene"
grep -q 'name="GameOverScreen" parent="AIPlayController/TerminalMonitor"' "$scene"
grep -q 'game_over_screen = NodePath("GameOverScreen")' "$scene"
grep -q 'scenario_id = "find_contract"' "$scene"
grep -q 'path="res://addons/cogito/AIPlay/ai_play_find_key_monitor.gd"' "$scene"
grep -q 'name="FindKeyMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q '^scenario_id = "find_key"$' "$scene"
test "$(grep -c 'name="Pickup_Key"' "$scene")" -eq 1
for marker in \
	DesktopDeskAnchor \
	LaptopDeskAnchor \
	ArchiveSofaAnchor \
	MeetingTableAnchor \
	TvCoffeeTableAnchor
do
	grep -q "name=\"$marker\" type=\"Marker3D\" parent=\"FindKeyMarkers\"" "$scene"
done
grep -q 'SCENARIO_ARG_PREFIX: String = "--ai-play-scenario="' \
	addons/cogito/AIPlay/ai_play_controller.gd
grep -q 'player = NodePath("../../Player")' "$scene"
grep -q 'task_card = NodePath("../../DEMO_HINTS/Hint_01_Welcome/ReadableComponent")' "$scene"
grep -q 'ceo_file_clue = NodePath("../../UPPER_OFFICE_CEO/ripped_page_a_pickup_ceo/ReadableComponent")' "$scene"
grep -q 'break_room_file_clue = NodePath("../../BREAK_ROOM/cabinetTelevisionDoors/contractfile/ReadableComponent")' "$scene"
grep -q 'cubicle_anchor = NodePath("../../CUBICLE_AREA/FindContractAnchor")' "$scene"
grep -q 'meeting_anchor = NodePath("../../MEETING_ROOM/FindContractAnchor")' "$scene"
grep -q 'laboratory_anchor = NodePath("../../MAIN_LOBBY/LAB_CONNECTOR/LaboratoryFindContractAnchor")' "$scene"
grep -q 'name="LaboratoryClueDesk" parent="MAIN_LOBBY/LAB_CONNECTOR"' "$scene"
grep -q 'name="LaboratoryFindContractAnchor" type="Marker3D" parent="MAIN_LOBBY/LAB_CONNECTOR"' "$scene"
grep -q 'name="FindContractAnchor" type="Marker3D" parent="MEETING_ROOM"' "$scene"
grep -q 'name="FindContractAnchor" type="Marker3D" parent="CUBICLE_AREA"' "$scene"
grep -A1 'name="FindContractAnchor" type="Marker3D" parent="CUBICLE_AREA"' "$scene" \
	| grep -q 'transform = Transform3D(0, 1, 0, -1, 0, 0, 0, 0, 1, 7.45, 1, -0.55)'
if grep -q 'name="CEOContractFile"' "$scene"; then
	echo "CEO office must use the ripped-page contract, not CEOContractFile" >&2
	exit 1
fi
if grep -q 'name="FindContract_CeoContract"' "$scene"; then
	echo "CEO office must use the physical contract file, not the old hint object" >&2
	exit 1
fi
if grep -q 'name="BreakRoomContractFile"' "$scene"; then
	echo "Break Room must use the RippedPageA contractfile" >&2
	exit 1
fi
grep -q 'name="ripped_page_a_pickup_ceo" parent="UPPER_OFFICE_CEO".*instance=ExtResource("ripped_page_a_readable")' "$scene"
grep -q 'name="contractfile" parent="BREAK_ROOM/cabinetTelevisionDoors".*instance=ExtResource("ripped_page_a_readable")' "$scene"
grep -q 'name="ReadableComponent".*instance=ExtResource("2_readable")' \
	addons/cogito/DemoScenes/DemoPrefabs/ripped_page_a_readable.tscn
grep -q 'interaction_text = "Read contract"' \
	addons/cogito/DemoScenes/DemoPrefabs/ripped_page_a_readable.tscn
if grep -q 'PickupComponent' \
	addons/cogito/DemoScenes/DemoPrefabs/ripped_page_a_readable.tscn
then
	echo "Readable ripped page must not include PickupComponent" >&2
	exit 1
fi

node_block_by_name() {
	local node_name="$1"
	awk -v node_name="$node_name" '
		/^\[node / {
			if (capture) exit
			capture = ($0 ~ ("^\\[node name=\"" node_name "\""))
		}
		capture { print }
	' "$scene"
}

assert_puzzle_object() {
	local node_name="$1"
	local root_block
	root_block="$(node_block_by_name "$node_name")"

	if grep -Eq '^(process_mode = 4|visible = false|collision_layer = 0|collision_mask = 0)$' \
		<<<"$root_block"
	then
		echo "$node_name must remain visible and interactable" >&2
		exit 1
	fi
}

for puzzle_object in \
	Hint_01_Welcome \
	FindContract_ComputerRecord \
	FindContract_AuditRecord \
	FindContract_ArchiveDecoyBox
do
	assert_puzzle_object "$puzzle_object"
done

grep -Fq 'const DATE_CANDIDATES: Array[String]' \
	addons/cogito/AIPlay/ai_play_find_contract_terminal.gd
grep -Fq 'const VERSION_CANDIDATES: Array[String]' \
	addons/cogito/AIPlay/ai_play_find_contract_terminal.gd
grep -Fq 'const ROUTES: Array[Array]' \
	addons/cogito/AIPlay/ai_play_find_contract_terminal.gd
test "$(grep -Ec '^[[:space:]]*"[0-9]{4}",$' \
	addons/cogito/AIPlay/ai_play_find_contract_terminal.gd)" -eq 8
test "$(grep -Ec '^[[:space:]]*"[0-9]{2}",$' \
	addons/cogito/AIPlay/ai_play_find_contract_terminal.gd)" -eq 8

for hint_name in \
	Hint_02_LampSwitch \
	Hint_03_AdvancedSwitch \
	Hint_04_Breakroom \
	Hint_05_Platform \
	Hint_06_AdvancedDoors \
	Hint_07_Keypad \
	Hint_08_Sittable_Static \
	Hint_09_Sittable_Auto \
	Hint_10_Sittable_Physics \
	Hint_11_Sittable_Vehicle
do
	hint_block="$(node_block_by_name "$hint_name")"
	for required_property in \
		'process_mode = 4' \
		'visible = false' \
		'collision_layer = 0' \
		'collision_mask = 0'
	do
		grep -Fqx "$required_property" <<<"$hint_block" || {
			echo "$hint_name is missing: $required_property" >&2
			exit 1
		}
	done
done

if ! tests/check_ai_play_secrets.sh; then
	echo "AI Play tracked files must not contain a credential" >&2
	exit 1
fi
