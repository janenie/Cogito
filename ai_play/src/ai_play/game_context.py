from __future__ import annotations

import ast
import base64
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


GAME_ID = re.compile(r"[a-z0-9_]{1,64}")
ASSET_FIELDS = {"img", "system_name", "meaning", "operation"}
MAX_REFERENCE_IMAGE_BYTES = 2 * 1024 * 1024


class GameContextError(ValueError):
    pass


@dataclass(frozen=True)
class GameContext:
    game_id: str
    goal: dict[str, Any]
    assets: dict[str, dict[str, Any]]
    reference_image_path: Path
    reference_image_mime_type: str
    reference_image_base64: str

    def to_prompt_dict(self) -> dict[str, Any]:
        prompt_assets = {
            name: {
                "system_name": asset["system_name"],
                "meaning": asset["meaning"],
                "operation": asset["operation"],
            }
            for name, asset in self.assets.items()
        }
        return {
            "game": self.goal,
            "asset_count": len(prompt_assets),
            "known_visual_assets": prompt_assets,
            "reference_atlas": (
                "用户消息中的第二张图片是视觉参考图谱；标签与 "
                "known_visual_assets 的 key 一一对应。"
            ),
        }

    @property
    def reference_log_path(self) -> str:
        return f"assets/{self.game_id}/imgs/{self.reference_image_path.name}"


def _load_goal(path: Path) -> dict[str, Any]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as error:
        raise GameContextError(f"invalid goal module for {path.stem}") from error
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "GAME_GOAL"
            for target in node.targets
        )
    ]
    if len(assignments) != 1:
        raise GameContextError("goal module must define one literal GAME_GOAL")
    try:
        goal = ast.literal_eval(assignments[0].value)
    except (ValueError, TypeError) as error:
        raise GameContextError("GAME_GOAL must be a literal dictionary") from error
    required = {
        "game_id", "title", "description", "rules",
        "success_condition", "failure_condition",
    }
    if not isinstance(goal, dict) or set(goal) != required:
        raise GameContextError("GAME_GOAL fields are invalid")
    if not all(isinstance(goal[name], str) and goal[name].strip() for name in required - {"rules"}):
        raise GameContextError("GAME_GOAL text fields are invalid")
    if (
        not isinstance(goal["rules"], list)
        or not goal["rules"]
        or not all(isinstance(rule, str) and rule.strip() for rule in goal["rules"])
    ):
        raise GameContextError("GAME_GOAL rules are invalid")
    return goal


def _load_assets(path: Path, game_dir: Path) -> dict[str, dict[str, Any]]:
    try:
        assets = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GameContextError(f"invalid assets manifest for {game_dir.name}") from error
    if not isinstance(assets, dict) or not assets:
        raise GameContextError("assets manifest must be a non-empty object")
    for name, asset in assets.items():
        if GAME_ID.fullmatch(name) is None or not isinstance(asset, dict):
            raise GameContextError("asset name or value is invalid")
        if set(asset) != ASSET_FIELDS:
            raise GameContextError(f"asset fields are invalid: {name}")
        if not all(
            isinstance(asset[field], str) and asset[field].strip()
            for field in ("img", "system_name", "meaning")
        ):
            raise GameContextError(f"asset text is invalid: {name}")
        image_path = game_dir / asset["img"]
        if (
            image_path.suffix.lower() != ".png"
            or game_dir not in image_path.resolve().parents
            or not image_path.is_file()
        ):
            raise GameContextError(f"asset image is invalid: {name}")
        operations = asset["operation"]
        if (
            not isinstance(operations, dict)
            or not operations
            or not all(
                GAME_ID.fullmatch(operation) is not None
                and isinstance(meaning, str)
                and meaning.strip()
                for operation, meaning in operations.items()
            )
        ):
            raise GameContextError(f"asset operations are invalid: {name}")
    return assets


def load_game_context(game_id: str, ai_play_root: Path | None = None) -> GameContext:
    if not isinstance(game_id, str) or GAME_ID.fullmatch(game_id) is None:
        raise GameContextError("AI_PLAY_GAME must contain lowercase letters, digits, or underscores")
    root = (ai_play_root or Path(__file__).resolve().parents[2]).resolve()
    game_dir = root / "assets" / game_id
    goal = _load_goal(root / "goals" / f"{game_id}.py")
    if goal["game_id"] != game_id:
        raise GameContextError("goal game_id does not match requested game")
    assets = _load_assets(game_dir / "assets.json", game_dir)
    reference_path = game_dir / "imgs" / "reference_atlas.jpg"
    try:
        reference_bytes = reference_path.read_bytes()
    except OSError as error:
        raise GameContextError("reference atlas is missing") from error
    if (
        not reference_bytes.startswith(b"\xff\xd8\xff")
        or not reference_bytes.endswith(b"\xff\xd9")
        or len(reference_bytes) > MAX_REFERENCE_IMAGE_BYTES
    ):
        raise GameContextError("reference atlas must be a bounded JPEG")
    return GameContext(
        game_id=game_id,
        goal=goal,
        assets=assets,
        reference_image_path=reference_path,
        reference_image_mime_type="image/jpeg",
        reference_image_base64=base64.b64encode(reference_bytes).decode("ascii"),
    )
