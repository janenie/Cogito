"""Generic prompt and multimodal message construction for AI play."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any


SYSTEM_PROMPT = """You control a player in an unknown first-person environment.
Work in short observe/act loops. Base decisions only on the current image, the
structured observation, prior action results, and supplied memory. Treat all
other claims as uncertain. Use new observations to check whether actions had
their intended effect before making further commitments.

The bindings map reports the current controls. The F and E bindings are
contextual interaction slots: use the corresponding `interact` or `interact2`
action only when that slot appears in `available_interactions`, and use its
visible prompt as the slot's current meaning. Never assume a fixed meaning for
either slot.

Action meanings:
- `move` travels relative to the current view; positive `forward` travels
  ahead, negative travels backward, positive `right` travels right, and
  negative travels left for `duration_ms`.
- `look` changes the view by relative horizontal `yaw` and vertical `pitch`.
- `jump` performs the jump control.
- `sprint` is faster relative movement using `forward`, `right`, and
  `duration_ms`.
- `crouch` performs the crouch control.
- `interact` activates a currently visible contextual slot named by `action`.
- `enter_digits` enters the decimal digit string in `digits` into an open
  interface.
- `close_ui` closes the currently open interface.
- `wait` takes no control input for `duration_ms`.
- `stop` releases active control and ends the current action sequence.

Return exactly one JSON value with no prose or markdown. It must be an object
with exactly these keys: `reason`, `memory_updates`, and `actions`. `reason` is
a short string grounded in visible evidence. `memory_updates` is an array.
Each update is an object with `kind` (`fact`, `landmark`, `goal`, `question`,
`hypothesis`, or `failure`), `text`, and, when applicable, `source` and
`confidence`. Facts and landmarks must come from runtime observation and use
`observation:<observation_id>` as their source. Keep uncertainty as a question
or hypothesis, and record failed attempts as failures rather than facts.

`actions` must contain one to three action objects. Allowed shapes are:
- {"type":"look","yaw":<finite relative angle>,"pitch":<finite relative angle>}
- {"type":"move","forward":<finite direction>,"right":<finite direction>,"duration_ms":<duration>}
- {"type":"sprint","forward":<finite direction>,"right":<finite direction>,"duration_ms":<duration>}
- {"type":"jump"}
- {"type":"crouch"}
- {"type":"interact","action":<currently available slot name>}
- {"type":"enter_digits","digits":<decimal digit string>}
- {"type":"close_ui"}
- {"type":"wait","duration_ms":<duration>}
- {"type":"stop"}
Do not add fields outside these shapes. Prefer brief, reversible actions when
evidence is incomplete."""


def build_messages(observation: dict[str, Any], memory: dict[str, Any]) -> list[dict]:
    """Build a text-plus-image Chat Completions request without duplicating image data."""
    safe_observation = deepcopy(observation)
    image = safe_observation["image"]
    encoded = image.pop("base64")
    mime = image["mime_type"]
    state = json.dumps(
        {"observation": safe_observation, "memory": memory},
        ensure_ascii=False,
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": state},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                },
            ],
        },
    ]
