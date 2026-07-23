import json
from pathlib import Path

import pytest

from ai_play.game_context import GameContextError, load_game_context


AI_PLAY_ROOT = Path(__file__).resolve().parents[1]


def test_find_contract_context_has_expected_visual_assets_without_solution():
    context = load_game_context("find_contract", AI_PLAY_ROOT)

    assert context.game_id == "find_contract"
    assert len(context.assets) == 11
    assert "正确密码" in context.goal["success_condition"]
    assert "解锁" in context.goal["success_condition"]
    assert context.goal["limitations"] == "你最多走1000步，所以请仔细规划。"
    assert context.reference_image_path.name == "reference_atlas.jpg"
    assert context.reference_image_path.is_file()
    rendered = json.dumps(context.to_prompt_dict(), ensure_ascii=False)
    assert "FriendlyHumanNPC / BasicInteraction" in rendered
    assert "083001" not in rendered


def test_every_manifest_image_exists():
    context = load_game_context("find_contract", AI_PLAY_ROOT)

    for asset in context.assets.values():
        assert (AI_PLAY_ROOT / "assets" / "find_contract" / asset["img"]).is_file()


@pytest.mark.parametrize("game_id", ["../find_contract", "Find-Contract", ""])
def test_game_id_rejects_paths_and_unsupported_characters(game_id):
    with pytest.raises(GameContextError):
        load_game_context(game_id, AI_PLAY_ROOT)
