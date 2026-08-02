from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from threading import Lock
import unicodedata


_CANDIDATE_KEYS = {
    "goal_pattern",
    "workflow",
    "landmarks",
    "avoid",
    "failure_review",
}
_WORKFLOW_KEYS = {"step", "precondition", "success_signal"}
_LANDMARK_KEYS = {"relation"}
_FAILURE_REVIEW_KEYS = {"stage", "bottlenecks", "optimizations"}
_ELIGIBLE_STATUSES = {"success", "failure"}
_TERMINAL_STATUSES = _ELIGIBLE_STATUSES | {
    "stopped",
    "disconnected",
    "shutdown",
}
_FORBIDDEN_FRAGMENTS = (
    "://",
    "res://",
    "game_script",
    "code_read",
    "developer note",
    "开发者笔记",
    "node/",
    "tests/",
    "test_",
    ".py",
    ".gd",
    ".tscn",
    ".tres",
    "spec/",
    "docs/scope",
)
_SIX_DIGITS_RE = re.compile(r"[0-9]{6}")
_COORDINATE_RE = re.compile(
    r"\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?"
    r"(?:\s*,\s*-?\d+(?:\.\d+)?)?\s*\)"
)
_TIMED_ACTION_RE = re.compile(r"\b\d+(?:\.\d+)?\s*ms\b", re.IGNORECASE)
_ABSOLUTE_POS_RE = re.compile(
    r"\b(?:position|coordinate|坐标)\s*[:=]?\s*-?\d",
    re.IGNORECASE,
)
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\")
_UNIX_PATH_RE = re.compile(r"(^|\s)/(?:tmp|var|home|users|mnt|private)/", re.IGNORECASE)


class WorkflowMemoryError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class _Attempt:
    number: int
    scenario_id: str
    status: str = "in_progress"
    terminal_reason: str | None = None
    consumed: bool = False


class SessionWorkflowMemory:
    """Validated procedural memory scoped to one MCP server process."""

    def __init__(self):
        self._lock = Lock()
        self._scenario_id: str | None = None
        self._active_attempt: _Attempt | None = None
        self._completed: list[_Attempt] = []
        self._version = 0
        self._goal_pattern: str | None = None
        self._workflow: list[dict] = []
        self._landmarks: list[dict] = []
        self._avoid: list[str] = []
        self._failure_reviews: list[dict] = []

    def start_attempt(self, scenario_id: str) -> int:
        with self._lock:
            if self._active_attempt is not None:
                raise WorkflowMemoryError("attempt_in_progress")
            if self._scenario_id not in (None, scenario_id):
                raise WorkflowMemoryError("scenario_mismatch")
            self._scenario_id = scenario_id
            number = len(self._completed) + 1
            self._active_attempt = _Attempt(number, scenario_id)
            return number

    def finish_attempt(self, status: str, terminal_reason: str) -> None:
        if status not in _TERMINAL_STATUSES:
            raise WorkflowMemoryError("invalid_attempt_status")
        with self._lock:
            if self._active_attempt is None:
                return
            self._active_attempt.status = status
            self._active_attempt.terminal_reason = terminal_reason
            if status not in _ELIGIBLE_STATUSES:
                self._active_attempt.consumed = True
            self._completed.append(self._active_attempt)
            self._active_attempt = None

    def read(self, scenario_id: str) -> dict:
        with self._lock:
            if self._scenario_id is None:
                raise WorkflowMemoryError("scenario_not_ready")
            if scenario_id != self._scenario_id:
                raise WorkflowMemoryError("scenario_mismatch")
            snapshot = None if self._version == 0 else self._snapshot_locked()
            return {
                "status": "ready",
                "scope": "current_orchestrator_session",
                "scenario": scenario_id,
                "version": self._version,
                "completed_runs": sum(
                    attempt.status in _ELIGIBLE_STATUSES
                    for attempt in self._completed
                ),
                "memory": deepcopy(snapshot),
            }

    def update(self, candidate: dict) -> dict:
        safe = validate_workflow_candidate(candidate)
        with self._lock:
            attempt = self._next_eligible_unconsumed_locked()
            if attempt is None:
                if self._active_attempt is not None:
                    raise WorkflowMemoryError("attempt_in_progress")
                if (
                    self._completed
                    and self._completed[-1].status not in _ELIGIBLE_STATUSES
                ):
                    raise WorkflowMemoryError("attempt_not_eligible")
                raise WorkflowMemoryError("attempt_already_updated")

            accepted = {
                "workflow": 0,
                "landmarks": 0,
                "avoid": 0,
                "failure_reviews": 0,
            }
            if attempt.status == "success":
                if safe["failure_review"] is not None:
                    raise WorkflowMemoryError("invalid_workflow_memory")
                self._goal_pattern = safe["goal_pattern"]
                accepted["workflow"] = _merge_unique(
                    self._workflow,
                    safe["workflow"],
                )
                accepted["landmarks"] = _merge_unique(
                    self._landmarks,
                    safe["landmarks"],
                )
            elif safe["failure_review"] is not None:
                trusted_review = {
                    "terminal_reason": attempt.terminal_reason,
                    **safe["failure_review"],
                }
                accepted["failure_reviews"] = _append_bounded_unique(
                    self._failure_reviews,
                    trusted_review,
                    max_items=3,
                )
            accepted["avoid"] = _merge_unique(self._avoid, safe["avoid"])
            attempt.consumed = True
            self._version += 1
            return {
                "status": "updated",
                "version": self._version,
                "accepted": accepted,
            }

    def _next_eligible_unconsumed_locked(self) -> _Attempt | None:
        return next(
            (
                attempt
                for attempt in self._completed
                if attempt.status in _ELIGIBLE_STATUSES
                and not attempt.consumed
            ),
            None,
        )

    def _snapshot_locked(self) -> dict:
        eligible = [
            attempt
            for attempt in self._completed
            if attempt.status in _ELIGIBLE_STATUSES
            and attempt.consumed
        ]
        successes = sum(
            attempt.status == "success"
            for attempt in eligible
        )
        confidence = successes / len(eligible) if eligible else 0.0
        return {
            "goal_pattern": self._goal_pattern,
            "workflow": deepcopy(self._workflow),
            "landmarks": deepcopy(self._landmarks),
            "avoid": list(self._avoid),
            "failure_reviews": deepcopy(self._failure_reviews),
            "confidence": round(confidence, 2),
        }


def validate_workflow_candidate(candidate: object) -> dict:
    try:
        _require_exact_dict(candidate, _CANDIDATE_KEYS)
        goal_pattern = _normalize_text(
            candidate["goal_pattern"],
            max_length=240,
        )
        workflow = _validate_object_list(
            candidate["workflow"],
            max_items=8,
            keys=_WORKFLOW_KEYS,
        )
        landmarks = _validate_object_list(
            candidate["landmarks"],
            max_items=8,
            keys=_LANDMARK_KEYS,
        )
        avoid = _validate_text_list(
            candidate["avoid"],
            max_items=12,
            require_items=True,
        )
        failure_review = _validate_failure_review(candidate["failure_review"])
    except (KeyError, TypeError, ValueError, WorkflowMemoryError) as error:
        if (
            isinstance(error, WorkflowMemoryError)
            and error.code == "invalid_workflow_memory"
        ):
            raise
        raise WorkflowMemoryError("invalid_workflow_memory") from error
    return {
        "goal_pattern": goal_pattern,
        "workflow": workflow,
        "landmarks": landmarks,
        "avoid": avoid,
        "failure_review": failure_review,
    }


def _validate_failure_review(value: object) -> dict | None:
    if value is None:
        return None
    _require_exact_dict(value, _FAILURE_REVIEW_KEYS)
    return {
        "stage": _normalize_text(value["stage"], max_length=240),
        "bottlenecks": _validate_text_list(
            value["bottlenecks"],
            max_items=3,
            require_items=True,
        ),
        "optimizations": _validate_text_list(
            value["optimizations"],
            max_items=4,
            require_items=True,
        ),
    }


def _validate_object_list(
    value: object,
    *,
    max_items: int,
    keys: set[str],
) -> list[dict]:
    if (
        not isinstance(value, list)
        or len(value) > max_items
    ):
        raise WorkflowMemoryError("invalid_workflow_memory")
    safe = []
    for item in value:
        _require_exact_dict(item, keys)
        safe.append({
            key: _normalize_text(item[key], max_length=240)
            for key in sorted(keys)
        })
    return safe


def _validate_text_list(
    value: object,
    *,
    max_items: int,
    require_items: bool,
) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) > max_items
        or (require_items and not value)
    ):
        raise WorkflowMemoryError("invalid_workflow_memory")
    return [
        _normalize_text(item, max_length=240)
        for item in value
    ]


def _require_exact_dict(value: object, keys: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise WorkflowMemoryError("invalid_workflow_memory")


def _normalize_text(value: object, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise WorkflowMemoryError("invalid_workflow_memory")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise WorkflowMemoryError("invalid_workflow_memory")
    text = " ".join(unicodedata.normalize("NFC", value).split())
    if not text or len(text) > max_length or _is_unsafe_text(text):
        raise WorkflowMemoryError("invalid_workflow_memory")
    return text


def _is_unsafe_text(text: str) -> bool:
    folded = text.casefold()
    return (
        any(fragment in folded for fragment in _FORBIDDEN_FRAGMENTS)
        or _SIX_DIGITS_RE.search(text) is not None
        or _COORDINATE_RE.search(text) is not None
        or _TIMED_ACTION_RE.search(text) is not None
        or _ABSOLUTE_POS_RE.search(text) is not None
        or _WINDOWS_PATH_RE.search(text) is not None
        or _UNIX_PATH_RE.search(text) is not None
    )


def _merge_unique(target: list, additions: list) -> int:
    accepted = 0
    for item in additions:
        if item not in target:
            target.append(deepcopy(item))
            accepted += 1
    return accepted


def _append_bounded_unique(
    target: list,
    item: object,
    *,
    max_items: int,
) -> int:
    if item in target:
        return 0
    target.append(deepcopy(item))
    del target[:-max_items]
    return 1
