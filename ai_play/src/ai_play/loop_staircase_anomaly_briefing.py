from __future__ import annotations

from copy import deepcopy


PUBLIC_BRIEFING = {
    "game_id": "loop_staircase_anomaly",
    "title": "Looping Staircase Anomaly",
    "background": (
        "This is a first-person looping stairwell reasoning task. The player "
        "cycles through floors 2F to 9F across five observation loops. Each loop "
        "reveals one new clue; the visible clue order changes from run to run. "
        "The task is to identify the one matching room, not to navigate to a "
        "physical destination. The true exit floor is determined by the clues "
        "accumulated across the whole run."
    ),
    "objective": (
        "Observe each floor like a human player, keep notes about its furniture, "
        "wall decorations, visible floor label, and other stable room details, "
        "then use the clue trail to eliminate wrong rooms until only one true "
        "exit floor remains after the fifth loop."
    ),
    "success_condition": "Select the only floor that satisfies all five cumulative clues.",
    "failure_condition": (
        "Select an incorrect floor, or reach the maximum act request count."
    ),
    "rules": [
        'Use act action {"type":"press_key","key":"up"} to switch to the next floor.',
        'Use act action {"type":"press_key","key":"down"} to switch to the previous floor.',
        'Use act action {"type":"press_key","key":"space"} only when choosing the current floor as the answer.',
        "Do not use move or sprint in this task; the floor switch is controlled by Up/Down keys.",
        "Observe 2F through 9F carefully in each loop.",
        "Press Up on 9F to return to 2F and advance the loop.",
        "There are five observation loops; one new clue appears in each loop.",
        "The visible clue order can change each run, so read the current clue instead of memorizing a fixed script.",
        "For every floor, record the visible furniture and objects, wall decorations, and floor label.",
        "Compare what you recorded across loops; some room details may change while the relevant evidence remains constrained by the clues.",
        "Keep a running candidate set from the clues and remove floors that contradict any clue.",
        "Do not decide from a single screenshot or from the current floor number alone.",
        "Static room appearance can distract from the clue trail.",
        "Wrong floor choices immediately fail the run.",
        "After each key action or loop transition, use the observation returned by act before deciding; do not repeat observe.",
    ],
    "objects": [
        {
            "id": "floor_landings",
            "meaning": (
                "Each floor landing is a room candidate. The current loop clue is "
                "visible in the scene, and the room itself contains furniture, "
                "objects, wall decorations, and a visible floor label that should "
                "be remembered across loops."
            ),
            "actions": {
                "observe": (
                    "Read the current clue, inspect the room details, update your "
                    "notes for this floor, and revise your candidate set before "
                    "pressing Up or Down."
                ),
            },
        },
        {
            "id": "loop_trigger",
            "meaning": "The top stairwell trigger returns the player to 2F and advances the loop count.",
            "actions": {
                "press_key": 'Press {"type":"press_key","key":"up"} after observing 9F.',
            },
        },
        {
            "id": "answer_choices",
            "meaning": "Final interactable choices for 2F through 9F.",
            "actions": {
                "press_key": 'Use Up/Down to show the inferred true floor, then press {"type":"press_key","key":"space"}.',
            },
        },
    ],
}


def load_loop_staircase_anomaly_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
