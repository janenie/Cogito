from ai_host.attempt_state import ReflectionMemory
from ai_host.reflection import build_attempt_instructions, sanitize_reflection


def test_sanitize_reflection_removes_forbidden_internal_details():
    text = """
    Use res://hidden/path and NodePath("../../Secret").
    The object was at global_position (1.2, 0.0, -3.4) under /Users/jan/workspace.
    Next time check HUD before finishing and open fridge before assuming cleanup is complete.
    """

    sanitized = sanitize_reflection(text)

    assert "res://" not in sanitized
    assert "NodePath" not in sanitized
    assert "global_position" not in sanitized
    assert "/Users/" not in sanitized
    assert "(1.2, 0.0, -3.4)" not in sanitized
    assert "check HUD before finishing" in sanitized
    assert "open fridge before assuming cleanup is complete" in sanitized


def test_attempt_one_has_no_previous_reflection():
    instructions = build_attempt_instructions(
        scenario_id="daily_routine_cleanup",
        attempt_id=1,
        max_attempts=3,
        memory=ReflectionMemory(),
    )

    assert "Attempt 1 of 3" in instructions
    assert "Previous strategy" not in instructions
    assert "fresh random seed" in instructions


def test_later_attempt_gets_sanitized_strategy():
    memory = ReflectionMemory(
        strategy=[
            "search rooms systematically",
            "check HUD before finishing",
            "open fridge before assuming cleanup is complete",
        ]
    )

    instructions = build_attempt_instructions(
        scenario_id="daily_routine_cleanup",
        attempt_id=2,
        max_attempts=3,
        memory=memory,
    )

    assert "Attempt 2 of 3" in instructions
    assert "Previous strategy" in instructions
    assert "search rooms systematically" in instructions
    assert "previous object positions are invalid" in instructions
