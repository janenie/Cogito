from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
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
_SCENARIO_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")
_TERMINAL_REASON_RE = re.compile(r"[a-z0-9][a-z0-9_:]*\Z")
_CHECKPOINT_KEYS = {
    "schema_version",
    "scenario_id",
    "active_attempt",
    "completed",
    "version",
    "goal_pattern",
    "workflow",
    "landmarks",
    "avoid",
    "failure_reviews",
}
_ATTEMPT_KEYS = {
    "number",
    "scenario_id",
    "status",
    "terminal_reason",
    "consumed",
}


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
    """Validated procedural memory scoped to one resumable orchestrator run."""

    def __init__(
        self,
        checkpoint_path: Path | None = None,
        *,
        preserve_unconsumed: bool = False,
    ):
        self._lock = Lock()
        self._preserve_unconsumed = preserve_unconsumed
        self._checkpoint_path = (
            checkpoint_path.expanduser().resolve()
            if checkpoint_path is not None
            else None
        )
        self._scenario_id: str | None = None
        self._active_attempt: _Attempt | None = None
        self._completed: list[_Attempt] = []
        self._version = 0
        self._goal_pattern: str | None = None
        self._workflow: list[dict] = []
        self._landmarks: list[dict] = []
        self._avoid: list[str] = []
        self._failure_reviews: list[dict] = []
        if self._checkpoint_path is not None and self._checkpoint_path.exists():
            self._load_checkpoint()

    def reopen_single_unlearned_attempt(self) -> bool:
        """Reopen one auto-consumed terminal for a checkpointed agent."""
        with self._lock:
            eligible = [
                attempt
                for attempt in self._completed
                if attempt.status in _ELIGIBLE_STATUSES
            ]
            has_memory = any(
                (
                    self._goal_pattern,
                    self._workflow,
                    self._landmarks,
                    self._avoid,
                    self._failure_reviews,
                )
            )
            if (
                self._active_attempt is not None
                or self._version != 0
                or has_memory
                or len(eligible) != 1
                or not eligible[0].consumed
            ):
                return False
            eligible[0].consumed = False
            self._persist_locked()
            return True

    def start_attempt(self, scenario_id: str) -> int:
        with self._lock:
            if self._active_attempt is not None:
                raise WorkflowMemoryError("attempt_in_progress")
            if self._scenario_id not in (None, scenario_id):
                raise WorkflowMemoryError("scenario_mismatch")
            self._scenario_id = scenario_id
            number = len(self._completed) + 1
            self._active_attempt = _Attempt(number, scenario_id)
            self._persist_locked()
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
            self._persist_locked()

    def read(self, scenario_id: str) -> dict:
        with self._lock:
            if self._scenario_id is None:
                raise WorkflowMemoryError("scenario_not_ready")
            if scenario_id != self._scenario_id:
                raise WorkflowMemoryError("scenario_mismatch")
            snapshot = None if self._version == 0 else self._snapshot_locked()
            return {
                "status": "ready",
                "scope": (
                    "resumable_orchestrator_run"
                    if self._checkpoint_path is not None
                    else "current_orchestrator_session"
                ),
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
            self._persist_locked()
            return {
                "status": "updated",
                "version": self._version,
                "accepted": accepted,
            }

    def _load_checkpoint(self) -> None:
        assert self._checkpoint_path is not None
        try:
            payload = json.loads(
                self._checkpoint_path.read_text(encoding="utf-8")
            )
            _require_exact_dict(payload, _CHECKPOINT_KEYS)
            if payload["schema_version"] != 1:
                raise ValueError("unsupported checkpoint schema")
            scenario_id = _validate_scenario_id(payload["scenario_id"])
            version = payload["version"]
            if type(version) is not int or version < 0:
                raise ValueError("invalid checkpoint version")
            completed = _validate_attempt_list(
                payload["completed"],
                scenario_id,
                allow_in_progress=False,
            )
            active_payload = payload["active_attempt"]
            active_attempt = (
                None
                if active_payload is None
                else _validate_attempt(
                    active_payload,
                    scenario_id,
                    allow_in_progress=True,
                )
            )
            if active_attempt is not None and active_attempt.status != "in_progress":
                raise ValueError("invalid active attempt status")
            attempts = completed + ([active_attempt] if active_attempt else [])
            if [attempt.number for attempt in attempts] != list(
                range(1, len(attempts) + 1)
            ):
                raise ValueError("invalid checkpoint attempt sequence")

            goal_pattern = payload["goal_pattern"]
            if goal_pattern is not None:
                goal_pattern = _normalize_text(goal_pattern, max_length=240)
            workflow = _validate_object_list(
                payload["workflow"],
                max_items=8,
                keys=_WORKFLOW_KEYS,
            )
            landmarks = _validate_object_list(
                payload["landmarks"],
                max_items=8,
                keys=_LANDMARK_KEYS,
            )
            avoid = _validate_text_list(
                payload["avoid"],
                max_items=12,
                require_items=False,
            )
            failure_reviews = _validate_failure_review_list(
                payload["failure_reviews"]
            )
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            WorkflowMemoryError,
        ) as error:
            raise WorkflowMemoryError(
                "invalid_workflow_memory_checkpoint"
            ) from error

        self._scenario_id = scenario_id
        self._completed = completed
        self._active_attempt = active_attempt
        self._version = version
        self._goal_pattern = goal_pattern
        self._workflow = workflow
        self._landmarks = landmarks
        self._avoid = avoid
        self._failure_reviews = failure_reviews

        changed = False
        if not self._preserve_unconsumed:
            for attempt in self._completed:
                if (
                    attempt.status in _ELIGIBLE_STATUSES
                    and not attempt.consumed
                ):
                    attempt.consumed = True
                    changed = True
        if self._active_attempt is not None:
            self._active_attempt.status = "shutdown"
            self._active_attempt.terminal_reason = "orchestrator_interrupted"
            self._active_attempt.consumed = True
            self._completed.append(self._active_attempt)
            self._active_attempt = None
            changed = True
        if changed:
            self._persist_locked()

    def _persist_locked(self) -> None:
        if self._checkpoint_path is None:
            return
        payload = {
            "schema_version": 1,
            "scenario_id": self._scenario_id,
            "active_attempt": _serialize_attempt(self._active_attempt),
            "completed": [
                _serialize_attempt(attempt) for attempt in self._completed
            ],
            "version": self._version,
            "goal_pattern": self._goal_pattern,
            "workflow": self._workflow,
            "landmarks": self._landmarks,
            "avoid": self._avoid,
            "failure_reviews": self._failure_reviews,
        }
        try:
            self._checkpoint_path.parent.mkdir(
                mode=0o700,
                parents=True,
                exist_ok=True,
            )
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{self._checkpoint_path.name}.",
                dir=self._checkpoint_path.parent,
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(payload, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary_name, 0o600)
                os.replace(temporary_name, self._checkpoint_path)
            except Exception:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
                raise
        except OSError as error:
            raise WorkflowMemoryError(
                "workflow_memory_checkpoint_failed"
            ) from error

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


def _serialize_attempt(attempt: _Attempt | None) -> dict | None:
    if attempt is None:
        return None
    return {
        "number": attempt.number,
        "scenario_id": attempt.scenario_id,
        "status": attempt.status,
        "terminal_reason": attempt.terminal_reason,
        "consumed": attempt.consumed,
    }


def _validate_scenario_id(value: object) -> str:
    if not isinstance(value, str) or _SCENARIO_ID_RE.fullmatch(value) is None:
        raise ValueError("invalid checkpoint scenario")
    return value


def _validate_attempt_list(
    value: object,
    scenario_id: str,
    *,
    allow_in_progress: bool,
) -> list[_Attempt]:
    if not isinstance(value, list):
        raise ValueError("invalid checkpoint attempts")
    return [
        _validate_attempt(
            item,
            scenario_id,
            allow_in_progress=allow_in_progress,
        )
        for item in value
    ]


def _validate_attempt(
    value: object,
    scenario_id: str,
    *,
    allow_in_progress: bool,
) -> _Attempt:
    _require_exact_dict(value, _ATTEMPT_KEYS)
    number = value["number"]
    status = value["status"]
    terminal_reason = value["terminal_reason"]
    consumed = value["consumed"]
    allowed_statuses = _TERMINAL_STATUSES | (
        {"in_progress"} if allow_in_progress else set()
    )
    if type(number) is not int or number < 1:
        raise ValueError("invalid checkpoint attempt number")
    if value["scenario_id"] != scenario_id:
        raise ValueError("invalid checkpoint attempt scenario")
    if status not in allowed_statuses:
        raise ValueError("invalid checkpoint attempt status")
    if status == "in_progress":
        if terminal_reason is not None or consumed is not False:
            raise ValueError("invalid active checkpoint attempt")
    elif (
        not isinstance(terminal_reason, str)
        or _TERMINAL_REASON_RE.fullmatch(terminal_reason) is None
        or type(consumed) is not bool
    ):
        raise ValueError("invalid completed checkpoint attempt")
    return _Attempt(
        number=number,
        scenario_id=scenario_id,
        status=status,
        terminal_reason=terminal_reason,
        consumed=consumed,
    )


def _validate_failure_review_list(value: object) -> list[dict]:
    if not isinstance(value, list) or len(value) > 3:
        raise ValueError("invalid checkpoint failure reviews")
    safe = []
    for item in value:
        _require_exact_dict(
            item,
            _FAILURE_REVIEW_KEYS | {"terminal_reason"},
        )
        terminal_reason = item["terminal_reason"]
        if (
            not isinstance(terminal_reason, str)
            or _TERMINAL_REASON_RE.fullmatch(terminal_reason) is None
        ):
            raise ValueError("invalid checkpoint terminal reason")
        review = _validate_failure_review({
            key: item[key] for key in _FAILURE_REVIEW_KEYS
        })
        assert review is not None
        safe.append({"terminal_reason": terminal_reason, **review})
    return safe


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
