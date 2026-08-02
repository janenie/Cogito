import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ai_play.action_schema import CONVEYOR_INGREDIENT_IDS as ACTION_INGREDIENT_IDS
from ai_play.action_schema import CONVEYOR_ACTIONS
from ai_play.conveyor_profit_briefing import PUBLIC_BRIEFING
from ai_play.observation_schema import (
    CONVEYOR_INGREDIENT_IDS as OBSERVATION_INGREDIENT_IDS,
    CONVEYOR_RECIPE_IDS,
)


def test_python_and_godot_publish_the_same_catalog_ids():
    godot = shutil.which("godot")
    if godot is None:
        pytest.skip("Godot is unavailable")
    repository = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [
            godot,
            "--headless",
            "--path",
            str(repository),
            "--script",
            "tests/conveyor_profit/dump_public_catalog.gd",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    prefix = "CONVEYOR_PUBLIC_CATALOG="
    payload_line = next(
        line for line in result.stdout.splitlines() if line.startswith(prefix)
    )
    godot_catalog = json.loads(payload_line.removeprefix(prefix))
    briefing_ingredient_ids = set(PUBLIC_BRIEFING["ingredient_ids"])
    briefing_recipe_ids = {recipe["id"] for recipe in PUBLIC_BRIEFING["menu"]}

    assert set(godot_catalog["ingredient_ids"]) == briefing_ingredient_ids
    assert briefing_ingredient_ids == set(ACTION_INGREDIENT_IDS)
    assert briefing_ingredient_ids == set(OBSERVATION_INGREDIENT_IDS)
    assert briefing_ingredient_ids == set(godot_catalog["executor_ingredient_ids"])
    assert set(godot_catalog["executor_action_types"]) == set(CONVEYOR_ACTIONS)
    assert set(godot_catalog["recipe_ids"]) == briefing_recipe_ids
    assert briefing_recipe_ids == set(CONVEYOR_RECIPE_IDS)
