#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

scene="garden/scenes/garden_vertical_slice.tscn"
controller="addons/cogito/AIPlay/ai_play_garden_controller.tscn"

test -f "$scene"
test -f "$controller"
grep -q 'name="AIPlayController"' "$scene"
grep -q 'player = NodePath("../CogitoPlayer")' "$scene"
grep -q 'auto_start = false' "$scene"
grep -q 'host = "127.0.0.1"' "$scene"
grep -q 'name="Observer" parent="AIPlayController"' "$scene"
grep -q 'watering_state = NodePath("../..")' "$scene"
grep -q 'name="GardenMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q 'scenario_id = "garden_watering"' "$scene"
grep -q 'name="GameOverScreen" parent="AIPlayController/GardenMonitor"' "$scene"
grep -q '"garden_watering": \[' addons/cogito/AIPlay/ai_play_controller.gd
grep -q '"garden_watering": ScenarioDefinition(' ai_play/src/ai_play/scenarios.py
grep -q 'DEFAULT_SCENARIO_ACT_REQUEST_LIMIT = 150' ai_play/src/ai_play/scenarios.py
test "$(grep -c 'max_act_requests=DEFAULT_SCENARIO_ACT_REQUEST_LIMIT' ai_play/src/ai_play/scenarios.py)" -eq 11
grep -q '"garden_tasks_complete": "任务成功"' \
	addons/cogito/AIPlay/ai_play_game_over_screen.gd
grep -q '"garden_task_failed": "任务失败"' \
	addons/cogito/AIPlay/ai_play_game_over_screen.gd
