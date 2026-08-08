#!/usr/bin/env bash
set -euo pipefail

godot --headless --path . --script tests/ai_play/test_ai_play_find_key_round.gd
godot --headless --path . --script tests/ai_play/test_cogito_keypad_result.gd
godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd -- --ai-play --ai-play-scenario=find_key --ai-play-round-seed=0
