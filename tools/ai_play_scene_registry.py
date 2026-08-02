"""Trusted scenario-to-scene defaults shared by AI Play launchers."""

DEFAULT_SCENE = "addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
SCENARIO_SCENES = {
    "find_contract": DEFAULT_SCENE,
    "find_key": DEFAULT_SCENE,
    "put_book": DEFAULT_SCENE,
    "greet_npc_meeting": DEFAULT_SCENE,
    "daily_routine_cleanup": "dailyroutine/scenes/home_daily_routine.tscn",
    "garden_watering": "garden/scenes/garden_vertical_slice.tscn",
    "repair_lighting_circuit": DEFAULT_SCENE,
    "arrange_meeting_briefings": DEFAULT_SCENE,
    "conveyor_profit": "conveyor_profit/scenes/conveyor_profit_preview.tscn",
    "loop_staircase_anomaly": (
        "addons/cogito/DemoScenes/LoopStaircase/loop_staircase_anomaly.tscn"
    ),
    "laboratory_experiment": "addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn",
}
SUPPORTED_SCENARIOS = tuple(SCENARIO_SCENES)


def resolve_scene(scenario: str, explicit_scene: str | None) -> str:
    """Return an explicit scene or the trusted default for a scenario."""
    if scenario not in SCENARIO_SCENES:
        raise ValueError(f"unsupported AI Play scenario: {scenario}")
    if explicit_scene:
        return explicit_scene
    return SCENARIO_SCENES[scenario]
