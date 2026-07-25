#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
scene="dailyroutine/scenes/home_daily_routine.tscn"
grep -q 'name="AIPlayController"' "$scene"
grep -q 'auto_start = false' "$scene"
grep -q 'host = "127.0.0.1"' "$scene"
grep -q 'name="DailyRoutineMonitor" type="Node" parent="AIPlayController"' "$scene"
grep -q 'scenario_id = "daily_routine_cleanup"' "$scene"
grep -q 'manager = NodePath("../../DailyRoutineManager")' "$scene"
grep -q 'name="GameOverScreen" parent="AIPlayController/DailyRoutineMonitor"' "$scene"
