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
grep -q 'path="res://addons/cogito/AIPlay/ai_play_put_book_monitor.gd"' "$scene"
grep -q 'name="PutBookMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q '^scenario_id = "put_book"$' "$scene"
grep -q 'name="PutBook_CarryableBook" parent="ARCHIVE".*instance=ExtResource("carryable_books")' "$scene"
grep -q 'path="res://addons/cogito/DemoScenes/DemoPrefabs/ai_play_put_book_destination.tscn"' "$scene"
grep -q 'name="PutBookDestination" parent="UPPER_OFFICE_CEO".*instance=ExtResource("ai_play_put_book_destination")' "$scene"
grep -q 'ceo_door = NodePath("../../UPPER_OFFICE_CEO/WindowedDoor/FrontDoor")' "$scene"
grep -q 'destination = NodePath("../../UPPER_OFFICE_CEO/PutBookDestination")' "$scene"
grep -q 'path="res://addons/cogito/AIPlay/ai_play_greet_npc_meeting_monitor.gd"' "$scene"
grep -q 'name="GreetNPCMeetingMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q '^scenario_id = "greet_npc_meeting"$' "$scene"
grep -q 'npc = NodePath("../../FriendlyHumanNPC")' "$scene"
grep -q 'conference_door = NodePath("../../MEETING_ROOM/ConferenceDoor/FrontDoor")' "$scene"
grep -q 'meeting_room = NodePath("../../MEETING_ROOM")' "$scene"
test "$(grep -c 'name="Pickup_Key"' "$scene")" -eq 1
for marker in \
	LaptopDeskAnchor \
	ArchiveSofaAnchor \
	MeetingTableAnchor \
	TvCoffeeTableAnchor
do
	grep -q "name=\"$marker\" type=\"Marker3D\" parent=\"FindKeyMarkers\"" "$scene"
done
grep -q 'SCENARIO_ARG_PREFIX: String = "--ai-play-scenario="' \
	addons/cogito/AIPlay/ai_play_controller.gd
grep -q 'EXIT_ON_GAME_OVER_ARG: String = "--ai-play-exit-on-game-over"' \
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

grep -q 'path="res://addons/cogito/AIPlay/ai_play_repair_lighting_circuit_monitor.gd"' "$scene"
grep -q 'path="res://addons/cogito/AIPlay/ai_play_repair_lighting_circuit_setup.tscn"' "$scene"
grep -q 'name="RepairLightingCircuitMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q '^scenario_id = "repair_lighting_circuit"$' "$scene"
grep -q 'name="RepairLightingCircuitSetup" parent="\." instance=ExtResource("ai_play_repair_lighting_circuit_setup")' "$scene"
grep -q 'control_switch_a = NodePath("../../GenericSwitch")' "$scene"
grep -q 'task_card = NodePath("../../DEMO_HINTS/Hint_01_Welcome/ReadableComponent")' "$scene"
grep -q 'game_over_screen = NodePath("../TerminalMonitor/GameOverScreen")' "$scene"
grep -q 'entrance_lamp = NodePath("../../ENTRANCE_AREA/lampRoundFloor")' "$scene"
grep -q 'ceo_lamp = NodePath("../../UPPER_OFFICE_CEO/lampRoundFloor")' "$scene"
grep -q 'break_room_lamp = NodePath("../../RepairLightingCircuitSetup/BreakRoomLamp")' "$scene"
test "$(grep -o 'lampSquareCeiling\(8\|9\|10\|11\|12\|13\)' "$scene" | sort -u | wc -l | tr -d ' ')" -eq 6

grep -q 'func _prepare_lobby_task_presentation()' \
	addons/cogito/AIPlay/ai_play_controller.gd

setup="addons/cogito/AIPlay/ai_play_repair_lighting_circuit_setup.tscn"
test -f "$setup"
for node_name in \
	TitleLabel SwitchLabelA SwitchLabelB SwitchLabelC SwitchLabelD \
	ControlSwitchB ControlSwitchC ControlSwitchD BreakerHeadingLabel \
	BreakerEntrance BreakerEntranceLabel BreakerCEO BreakerCEOLabel \
	BreakerLobby BreakerLobbyLabel BreakerBreakRoom BreakerBreakRoomLabel \
	VerifyButton VerifyLabel PanelSpawn TaskCardAnchor BreakRoomLamp
do
	grep -q "name=\"$node_name\"" "$setup"
done
if grep -q 'name="PanelBacking"' "$setup"; then
	echo "lighting setup must not add a black panel backing" >&2
	exit 1
fi
grep -A4 '^\[node name="RepairLightingCircuitSetup"' "$setup" | grep -q '^process_mode = 4$'
grep -A4 '^\[node name="RepairLightingCircuitSetup"' "$setup" | grep -q '^visible = false$'

setup_node_block() {
	local setup_node_name="$1"
	awk -v setup_node_name="$setup_node_name" '
		/^\[node / {
			if (capture) exit
			capture = ($0 ~ ("^\\[node name=\"" setup_node_name "\""))
		}
		capture { print }
	' "$setup"
}

setup_interaction_block() {
	local setup_parent_name="$1"
	awk -v setup_parent_name="$setup_parent_name" '
		/^\[node / {
			if (capture) exit
			capture = ($0 ~ /^\[node name="BasicInteraction"/ && $0 ~ ("parent=\"" setup_parent_name "\""))
		}
		capture { print }
	' "$setup"
}

for inert_control in \
	ControlSwitchB ControlSwitchC ControlSwitchD \
	BreakerEntrance BreakerCEO BreakerLobby BreakerBreakRoom VerifyButton
do
	grep -q '^collision_layer = 0$' <<<"$(setup_node_block "$inert_control")"
	grep -q '^is_disabled = true$' <<<"$(setup_interaction_block "$inert_control")"
done
grep -q '^collision_layer = 0$' <<<"$(setup_node_block BreakRoomLamp)"
grep -q '^is_disabled = true$' <<<"$(setup_interaction_block BreakRoomLamp)"

grep -q 'path="res://addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_monitor.gd"' "$scene"
grep -q 'path="res://addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_setup.tscn"' "$scene"
grep -q 'name="ArrangeMeetingBriefingsMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q '^scenario_id = "arrange_meeting_briefings"$' "$scene"
grep -q 'name="ArrangeMeetingBriefingsSetup" parent="\." instance=ExtResource("ai_play_arrange_meeting_briefings_setup")' "$scene"
grep -q 'setup = NodePath("../../ArrangeMeetingBriefingsSetup")' "$scene"
grep -q 'player = NodePath("../../Player")' "$scene"
grep -q 'task_card = NodePath("../../DEMO_HINTS/Hint_01_Welcome/ReadableComponent")' "$scene"
grep -q 'game_over_screen = NodePath("../TerminalMonitor/GameOverScreen")' "$scene"
grep -q 'verify_button = NodePath("../../ArrangeMeetingBriefingsSetup/VerifyButton")' "$scene"
grep -q 'player_spawn = NodePath("../../ArrangeMeetingBriefingsSetup/PlayerSpawn")' "$scene"
grep -q 'task_card_anchor = NodePath("../../ArrangeMeetingBriefingsSetup/TaskCardAnchor")' "$scene"

meeting_setup="addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_setup.tscn"
test -f "$meeting_setup"
for node_name in \
	PlayerSpawn TaskCardAnchor \
	RecordCEO RecordArchive RecordBreakRoom \
	FolderAtlas FolderBirch FolderCrown FolderDelta \
	SeatTVSide SeatDoorSide SeatOppositeTV SeatInnerWall \
	ClockwiseLabel VerifyButton VerifyLabel
do
	grep -q "name=\"$node_name\"" "$meeting_setup"
done
grep -A4 '^\[node name="ArrangeMeetingBriefingsSetup"' "$meeting_setup" \
	| grep -q '^process_mode = 4$'
grep -A4 '^\[node name="ArrangeMeetingBriefingsSetup"' "$meeting_setup" \
	| grep -q '^visible = false$'

meeting_setup_node_block() {
	local meeting_node_name="$1"
	awk -v meeting_node_name="$meeting_node_name" '
		/^\[node / {
			if (capture) exit
			capture = ($0 ~ ("^\\[node name=\"" meeting_node_name "\""))
		}
		capture { print }
	' "$meeting_setup"
}

meeting_setup_child_block() {
	local child_name="$1"
	local parent_name="$2"
	awk -v child_name="$child_name" -v parent_name="$parent_name" '
		/^\[node / {
			if (capture) exit
			capture = ($0 ~ ("^\\[node name=\"" child_name "\"") && $0 ~ ("parent=\"" parent_name "\""))
		}
		capture { print }
	' "$meeting_setup"
}

for record_name in RecordCEO RecordArchive RecordBreakRoom
do
	grep -q '^collision_layer = 0$' \
		<<<"$(meeting_setup_node_block "$record_name")"
	grep -q '^is_disabled = true$' \
		<<<"$(meeting_setup_child_block ReadableComponent "$record_name")"
done

for folder_name in FolderAtlas FolderBirch FolderCrown FolderDelta
do
	folder_block="$(meeting_setup_node_block "$folder_name")"
	grep -q '^process_mode = 4$' <<<"$folder_block"
	grep -q '^collision_layer = 0$' <<<"$folder_block"
	grep -q '^collision_mask = 0$' <<<"$folder_block"
	grep -q '^is_disabled = true$' \
		<<<"$(meeting_setup_child_block CarryableComponent "$folder_name")"
	grep -q '^text = "\(李明\|王芳\|陈宇\|赵宁\)"$' \
		<<<"$(meeting_setup_child_block NameLabel "$folder_name")"
done

for seat_name in SeatTVSide SeatDoorSide SeatOppositeTV SeatInnerWall
do
	seat_block="$(meeting_setup_node_block "$seat_name")"
	grep -q '^collision_layer = 0$' <<<"$seat_block"
	grep -q '^collision_mask = 0$' <<<"$seat_block"
	grep -q '^is_disabled = true$' \
		<<<"$(meeting_setup_child_block SeatInteraction "$seat_name")"
	grep -q 'name="SnapAnchor" type="Marker3D" parent=' \
		<<<"$(meeting_setup_child_block SnapAnchor "$seat_name")"
done

grep -q '^collision_layer = 0$' \
	<<<"$(meeting_setup_node_block VerifyButton)"
grep -q '^is_disabled = true$' \
	<<<"$(meeting_setup_child_block BasicInteraction VerifyButton)"
grep -q '^text = "↻  CLOCKWISE"$' \
	<<<"$(meeting_setup_node_block ClockwiseLabel)"
grep -q '^text = "TASK CARD"$' \
	<<<"$(meeting_setup_node_block TaskCardLabel)"
grep -q '^text = "CEO OFFICE\\nMEETING RECORD"$' \
	<<<"$(meeting_setup_node_block RecordCEOLabel)"
grep -q '^text = "ARCHIVE\\nMEETING RECORD"$' \
	<<<"$(meeting_setup_node_block RecordArchiveLabel)"
grep -q '^text = "BREAK ROOM\\nMEETING RECORD"$' \
	<<<"$(meeting_setup_node_block RecordBreakRoomLabel)"
grep -q '^text = "TV SIDE"$' \
	<<<"$(meeting_setup_child_block SeatLabel SeatTVSide)"
grep -q '^text = "DOOR SIDE"$' \
	<<<"$(meeting_setup_child_block SeatLabel SeatDoorSide)"
grep -q '^text = "OPPOSITE TV"$' \
	<<<"$(meeting_setup_child_block SeatLabel SeatOppositeTV)"
grep -q '^text = "INNER WALL"$' \
	<<<"$(meeting_setup_child_block SeatLabel SeatInnerWall)"
grep -q '^text = "VERIFY"$' \
	<<<"$(meeting_setup_node_block VerifyLabel)"

if ! tests/check_ai_play_secrets.sh; then
	echo "AI Play tracked files must not contain a credential" >&2
	exit 1
fi
