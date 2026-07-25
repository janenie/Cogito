from __future__ import annotations

import re

from .attempt_state import ReflectionMemory

FORBIDDEN_PATTERNS = [
    re.compile(r"res://\S*"),
    re.compile(r"/Users/\S*"),
    re.compile(r"NodePath\([^)]*\)"),
    re.compile(r"\bglobal_position\b"),
    re.compile(
        r"\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*\)"
    ),
]


def sanitize_reflection(text: str) -> str:
    sanitized = text
    for pattern in FORBIDDEN_PATTERNS:
        sanitized = pattern.sub("[removed]", sanitized)
    return sanitized.strip()


def sanitize_items(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        sanitized = sanitize_reflection(item)
        if sanitized:
            result.append(sanitized)
    return result


def build_attempt_instructions(
    *,
    scenario_id: str,
    attempt_id: int,
    max_attempts: int,
    memory: ReflectionMemory,
) -> str:
    lines = [
        f"Scenario: {scenario_id}.",
        f"Attempt {attempt_id} of {max_attempts}.",
        "Every attempt starts a fresh Godot process with a fresh random seed.",
        "previous object positions are invalid; do not reuse coordinates or exact locations.",
        "Use only MCP tools, public briefing, screenshots, HUD text, visible prompts, and action results.",
        "Carry over only process-level strategy.",
    ]
    strategy = sanitize_items(memory.strategy)
    if attempt_id > 1 and strategy:
        lines.append("Previous strategy:")
        lines.extend(f"- {item}" for item in strategy)
    return "\n".join(lines)
