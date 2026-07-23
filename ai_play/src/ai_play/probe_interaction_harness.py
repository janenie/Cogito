"""Derive bounded per-round guidance for the probe interaction skill."""

from __future__ import annotations

from typing import Any


SUCCESS_CONDITION = "current_available_interactions_non_empty"
STATUS = {
    "interface_open": ("resolve_open_interface", False),
    "aligned": ("use_available_interaction", True),
    "inconsistent": ("reobserve_before_interacting", False),
    "not_aligned": ("approach_or_choose_new_target", False),
    "ready_to_probe": ("locate_visible_candidate", False),
}
INTERACTION_ACTIONS = {"interact", "interact2"}


def build_probe_interaction_harness(
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Return the current probe state without mutating the observation."""
    interface = observation["interface"]
    available_actions = []
    for interaction in interface["available_interactions"]:
        action = interaction["action"]
        if action in INTERACTION_ACTIONS and action not in available_actions:
            available_actions.append(action)

    if interface["is_open"]:
        status = "interface_open"
    elif available_actions:
        status = "aligned"
    else:
        latest_probe_outcome = None
        for result in reversed(observation["last_action_results"]):
            if (
                result.get("status") == "completed"
                and result.get("type") == "probe_interaction"
            ):
                latest_probe_outcome = result.get("outcome")
                break
        if latest_probe_outcome == "aligned":
            status = "inconsistent"
        elif latest_probe_outcome == "not_found":
            status = "not_aligned"
        else:
            status = "ready_to_probe"

    required_next_step, success = STATUS[status]
    return {
        "status": status,
        "success": success,
        "success_condition": SUCCESS_CONDITION,
        "available_actions": available_actions,
        "required_next_step": required_next_step,
    }
