"""Trusted scenario-to-scene defaults shared by AI Play launchers."""

DEFAULT_SCENE = "addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
SCENARIO_SCENES = {
    "conveyor_profit": "conveyor_profit/scenes/conveyor_profit_preview.tscn",
}


def resolve_scene(scenario: str, explicit_scene: str | None) -> str:
    """Return an explicit scene or the trusted default for a scenario."""
    if explicit_scene:
        return explicit_scene
    return SCENARIO_SCENES.get(scenario, DEFAULT_SCENE)
