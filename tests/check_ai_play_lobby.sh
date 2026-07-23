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

readable_block_by_parent() {
	local parent_path="$1"
	awk -v parent_path="$parent_path" '
		/^\[node / {
			if (capture) exit
			capture = ($0 ~ "^\\[node name=\"ReadableComponent\"" && $0 ~ ("parent=\"" parent_path "\""))
		}
		capture { print }
	' "$scene"
}

assert_puzzle_hint() {
	local node_name="$1"
	local parent_path="$2"
	local title="$3"
	local interaction_text="$4"
	local content_probe="$5"
	local root_block
	local readable_block
	root_block="$(node_block_by_name "$node_name")"
	readable_block="$(readable_block_by_parent "$parent_path")"

	if grep -Eq '^(process_mode = 4|visible = false|collision_layer = 0|collision_mask = 0)$' \
		<<<"$root_block"
	then
		echo "$node_name must remain visible and interactable" >&2
		exit 1
	fi
	grep -Fq "readable_title = \"$title\"" <<<"$readable_block" || {
		echo "$node_name is missing puzzle title: $title" >&2
		exit 1
	}
	grep -Fq "interaction_text = \"$interaction_text\"" <<<"$readable_block" || {
		echo "$node_name is missing interaction text: $interaction_text" >&2
		exit 1
	}
	grep -Fq "$content_probe" <<<"$readable_block" || {
		echo "$node_name is missing its historical puzzle content" >&2
		exit 1
	}
}

while IFS='|' read -r node_name parent_path title interaction_text content_probe; do
	assert_puzzle_hint \
		"$node_name" \
		"$parent_path" \
		"$title" \
		"$interaction_text" \
		"$content_probe"
done <<'PUZZLE_HINTS'
Hint_01_Welcome|DEMO_HINTS/Hint_01_Welcome|档案室门禁任务|Read task|找到 6 位密码，打开 ARCHIVE 的密码盘。
FindContract_ComputerRecord|CUBICLE_AREA/FindContract_ComputerRecord|合同检索系统|Read terminal|备注：档案室访问码不只使用日期。
FindContract_AuditRecord|MEETING_ROOM/FindContract_AuditRecord|LUMEN Renewal 审核会|Read audit note|签署日期四位 + 合同版本两位
FindContract_CeoContract|UPPER_OFFICE_CEO/FindContract_CeoContract|LUMEN Renewal Contract|Read contract|签署日期：08/30
FindContract_ArchiveDecoyBox|ARCHIVE/FindContract_ArchiveDecoyBox|旧包装箱|Inspect box|真正的合同不在档案室门边。
PUZZLE_HINTS

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
