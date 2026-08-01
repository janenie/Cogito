"""Typed, bounded MCP inputs exposed to game-playing models."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, StringConstraints


SAFE_INTEGER_MAX = 9_007_199_254_740_991


class _StrictToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LookAction(_StrictToolInput):
    """Turn one semantic camera axis by a positive number of degrees."""

    type: Literal["look"]
    direction: Literal["left", "right", "up", "down"]
    degrees: Annotated[
        float,
        Field(ge=1, le=45, description="Positive semantic turn amount."),
    ]


class MoveAction(_StrictToolInput):
    """Walk using signed local forward and right axes."""

    type: Literal["move"]
    forward: Annotated[
        float,
        Field(ge=-1, le=1, description="-1 backward, +1 forward."),
    ]
    right: Annotated[
        float,
        Field(ge=-1, le=1, description="-1 left, +1 right."),
    ]
    duration_ms: Annotated[
        float,
        Field(ge=50, le=250, description="Hold duration in milliseconds."),
    ]


class SprintAction(_StrictToolInput):
    """Sprint using signed local forward and right axes."""

    type: Literal["sprint"]
    forward: Annotated[
        float,
        Field(ge=-1, le=1, description="-1 backward, +1 forward."),
    ]
    right: Annotated[
        float,
        Field(ge=-1, le=1, description="-1 left, +1 right."),
    ]
    duration_ms: Annotated[
        float,
        Field(ge=50, le=250, description="Hold duration in milliseconds."),
    ]


class JumpAction(_StrictToolInput):
    type: Literal["jump"]


class CrouchAction(_StrictToolInput):
    type: Literal["crouch"]


class InteractAction(_StrictToolInput):
    """Trigger one interaction currently listed by the observation."""

    type: Literal["interact"]
    action: Literal["interact", "interact2"]


class EnterDigitsAction(_StrictToolInput):
    """Enter one to six ASCII digits while an interface is open."""

    type: Literal["enter_digits"]
    digits: Annotated[str, StringConstraints(pattern=r"^[0-9]{1,6}$")]


class CloseUIAction(_StrictToolInput):
    type: Literal["close_ui"]


class WaitAction(_StrictToolInput):
    """Wait without holding player input."""

    type: Literal["wait"]
    duration_ms: Annotated[float, Field(ge=50, le=2000)]


class ProbeInteractionAction(_StrictToolInput):
    """Probe one normalized screen point as a single-action batch."""

    type: Literal["probe_interaction"]
    target_x: Annotated[float, Field(ge=0, le=1)]
    target_y: Annotated[float, Field(ge=0, le=1)]


ActionInput = Union[
    LookAction,
    MoveAction,
    SprintAction,
    JumpAction,
    CrouchAction,
    InteractAction,
    EnterDigitsAction,
    CloseUIAction,
    WaitAction,
    ProbeInteractionAction,
]
ActionBatchInput = SkipValidation[
    Annotated[
        list[ActionInput],
        Field(min_length=1, max_length=3),
    ]
]
ObservationIdInput = SkipValidation[
    Annotated[
        int,
        Field(ge=0, le=SAFE_INTEGER_MAX),
    ]
]


PublicText = SkipValidation[
    Annotated[
        str,
        StringConstraints(min_length=1, max_length=240),
    ]
]


class WorkflowStepInput(_StrictToolInput):
    step: PublicText
    precondition: PublicText
    success_signal: PublicText


class LandmarkInput(_StrictToolInput):
    relation: PublicText


WorkflowInput = SkipValidation[
    Annotated[
        list[WorkflowStepInput],
        Field(max_length=8),
    ]
]
LandmarksInput = SkipValidation[
    Annotated[
        list[LandmarkInput],
        Field(max_length=8),
    ]
]
AvoidInput = SkipValidation[
    Annotated[
        list[Annotated[str, StringConstraints(min_length=1, max_length=240)]],
        Field(min_length=1, max_length=12),
    ]
]
