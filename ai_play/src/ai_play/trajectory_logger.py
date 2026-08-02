from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
from threading import Lock


SCENARIO_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


class LogPersistenceError(RuntimeError):
    """Raised when a gameplay trajectory cannot be persisted safely."""


@dataclass(frozen=True)
class ToolCallToken:
    run_sequence: int
    attempt: int
    event_index: int


@dataclass
class _AttemptState:
    directory: Path
    data: dict


class TrajectoryLogger:
    MAX_ATTEMPTS = 4
    ALLOWED_TOOLS = {"observe", "act", "stop"}
    TERMINAL_STATUSES = {"success", "failure", "stopped"}

    def __init__(self, root, now=None):
        self.root = Path(root).expanduser()
        self._now = now or (lambda: datetime.now().astimezone())
        self._lock = Lock()
        self._run_sequence = 0
        self._run_dir = None
        self._run = None
        self._current_attempt = None
        self._attempt_states = {}
        self._failed = False
        self._closed = False

    @property
    def current_attempt_number(self):
        with self._lock:
            if self._current_attempt is None:
                return None
            return self._current_attempt[1]

    def start_attempt(self, scenario_id):
        scenario_id = _validate_scenario_id(scenario_id)
        with self._lock:
            self._require_available_locked()
            if (
                self._run is not None
                and self._run["scenario_id"] != scenario_id
            ):
                raise ValueError("scenario_mismatch")
            try:
                if (
                    self._run is None
                    or self._run["status"] != "in_progress"
                    or len(self._run["attempts"]) >= self.MAX_ATTEMPTS
                ):
                    self._create_run_locked(scenario_id)

                attempt_number = len(self._run["attempts"]) + 1
                attempt_dir = self._run_dir / f"attempt-{attempt_number:02d}"
                attempt_dir.mkdir(mode=0o700)
                (attempt_dir / "imgs").mkdir(mode=0o700)
                attempt = {
                    "trajectory": [],
                    "result": {
                        "total_steps": 0,
                        "status": "in_progress",
                    },
                }
                key = (self._run_sequence, attempt_number)
                self._attempt_states[key] = _AttemptState(attempt_dir, attempt)
                self._current_attempt = key
                self._run["attempts"].append({
                    "attempt": attempt_number,
                    "status": "in_progress",
                    "total_steps": 0,
                    "terminal_reason": None,
                })
                self._write_attempt_locked(self._attempt_states[key])
                self._write_run_locked()
                return attempt_dir
            except Exception as error:
                self._fail_locked(error)

    def begin_tool_call(self, tool, request):
        with self._lock:
            self._require_available_locked()
            if tool not in self.ALLOWED_TOOLS or self._current_attempt is None:
                return None
            state = self._attempt_states[self._current_attempt]
            if state.data["result"]["status"] != "in_progress":
                return None
            try:
                event_index = len(state.data["trajectory"]) + 1
                entry = {
                    "event_index": event_index,
                    "tool": tool,
                    "requested_at": self._timestamp(),
                    "completed_at": None,
                    "request": deepcopy(request),
                    "response": None,
                    "images": [],
                }
                if tool == "act":
                    state.data["result"]["total_steps"] += 1
                    entry["act_step"] = state.data["result"]["total_steps"]
                state.data["trajectory"].append(entry)
                self._sync_attempt_summary_locked(state)
                self._write_attempt_locked(state)
                self._write_run_locked()
                return ToolCallToken(
                    self._current_attempt[0],
                    self._current_attempt[1],
                    event_index,
                )
            except Exception as error:
                self._fail_locked(error)

    def complete_tool_call(
        self,
        token,
        is_error,
        structured_content,
        image_bytes=None,
    ):
        if token is None:
            return
        with self._lock:
            self._require_available_locked()
            try:
                key = (token.run_sequence, token.attempt)
                state = self._attempt_states[key]
                entry = state.data["trajectory"][token.event_index - 1]
                if entry["event_index"] != token.event_index:
                    raise ValueError("invalid tool call token")

                images = []
                if image_bytes is not None:
                    if not isinstance(image_bytes, bytes):
                        raise TypeError("image_bytes must be bytes")
                    observation = structured_content.get("observation")
                    observation_id = (
                        observation.get("observation_id")
                        if isinstance(observation, dict)
                        else None
                    )
                    observation_suffix = (
                        f"obs{observation_id:06d}"
                        if type(observation_id) is int
                        else "no-observation"
                    )
                    relative = (
                        f"imgs/{token.event_index:06d}-"
                        f"{entry['tool']}-{observation_suffix}.jpg"
                    )
                    self._atomic_write_bytes(
                        state.directory / relative,
                        image_bytes,
                    )
                    images.append(relative)

                entry["completed_at"] = self._timestamp()
                entry["response"] = {
                    "is_error": bool(is_error),
                    "structured_content": deepcopy(structured_content),
                }
                entry["images"] = images
                self._write_attempt_locked(state)
            except Exception as error:
                self._fail_locked(error)

    def finish_attempt(self, status, terminal_reason):
        if status not in self.TERMINAL_STATUSES:
            raise ValueError("invalid trajectory status")
        if type(terminal_reason) is not str or not terminal_reason:
            raise ValueError("invalid terminal reason")
        with self._lock:
            self._require_available_locked()
            if self._current_attempt is None:
                return
            state = self._attempt_states[self._current_attempt]
            if state.data["result"]["status"] != "in_progress":
                return
            try:
                state.data["result"]["status"] = status
                self._sync_attempt_summary_locked(state)
                self._current_attempt_summary_locked()["terminal_reason"] = (
                    terminal_reason
                )
                self._refresh_run_status_locked()
                self._write_attempt_locked(state)
                self._write_run_locked()
            except Exception as error:
                self._fail_locked(error)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._require_available_locked()
            try:
                if self._current_attempt is not None:
                    state = self._attempt_states[self._current_attempt]
                    if state.data["result"]["status"] == "in_progress":
                        state.data["result"]["status"] = "stopped"
                        self._sync_attempt_summary_locked(state)
                        self._current_attempt_summary_locked()[
                            "terminal_reason"
                        ] = "mcp_shutdown"
                        self._write_attempt_locked(state)
                if self._run is not None and self._run["status"] == "in_progress":
                    self._run["status"] = "stopped"
                    self._refresh_completed_attempts_locked()
                    self._write_run_locked()
                self._closed = True
            except Exception as error:
                self._fail_locked(error)

    def _create_run_locked(self, scenario_id):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        scenario_root = self.root / scenario_id
        scenario_root.mkdir(mode=0o700, exist_ok=True)
        os.chmod(scenario_root, 0o700)
        started_at = self._now()
        base_name = started_at.strftime("%Y%m%d-%H-%M")
        candidate = scenario_root / base_name
        suffix = 2
        while True:
            try:
                candidate.mkdir(mode=0o700)
                break
            except FileExistsError:
                candidate = scenario_root / f"{base_name}-{suffix:02d}"
                suffix += 1

        self._run_sequence += 1
        self._run_dir = candidate
        self._run = {
            "scenario_id": scenario_id,
            "started_at": started_at.isoformat(),
            "max_attempts": self.MAX_ATTEMPTS,
            "completed_attempts": 0,
            "status": "in_progress",
            "successful_attempt": None,
            "attempts": [],
        }
        self._current_attempt = None

    def _sync_attempt_summary_locked(self, state):
        attempt_number = int(state.directory.name.removeprefix("attempt-"))
        summary = self._run["attempts"][attempt_number - 1]
        summary["status"] = state.data["result"]["status"]
        summary["total_steps"] = state.data["result"]["total_steps"]
        self._refresh_completed_attempts_locked()

    def _current_attempt_summary_locked(self):
        return self._run["attempts"][self._current_attempt[1] - 1]

    def _refresh_completed_attempts_locked(self):
        self._run["completed_attempts"] = sum(
            item["status"] != "in_progress"
            for item in self._run["attempts"]
        )

    def _refresh_run_status_locked(self):
        self._refresh_completed_attempts_locked()
        current_number = self._current_attempt[1]
        status = self._run["attempts"][current_number - 1]["status"]
        if status == "success":
            self._run["status"] = "success"
            self._run["successful_attempt"] = current_number
            return
        if (
            len(self._run["attempts"]) == self.MAX_ATTEMPTS
            and self._run["completed_attempts"] == self.MAX_ATTEMPTS
        ):
            statuses = [item["status"] for item in self._run["attempts"]]
            self._run["status"] = (
                "failure"
                if all(item == "failure" for item in statuses)
                else "stopped"
            )

    def _write_attempt_locked(self, state):
        self._atomic_write_json(
            state.directory / "trajectory.json",
            state.data,
        )

    def _write_run_locked(self):
        self._atomic_write_json(self._run_dir / "run.json", self._run)

    def _timestamp(self):
        return self._now().isoformat()

    def _require_available_locked(self):
        if self._failed or self._closed:
            raise LogPersistenceError("logging_failed")

    def _fail_locked(self, error):
        self._failed = True
        if isinstance(error, LogPersistenceError):
            raise error
        raise LogPersistenceError("logging_failed") from error

    @staticmethod
    def _atomic_write_json(path, payload):
        TrajectoryLogger._atomic_write(
            path,
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
        )

    @staticmethod
    def _atomic_write_bytes(path, payload):
        TrajectoryLogger._atomic_write(path, payload)

    @staticmethod
    def _atomic_write(path, payload):
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, path)
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


def _validate_scenario_id(value):
    if type(value) is not str or SCENARIO_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("invalid scenario_id")
    return value
