from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import time
from threading import Condition, Lock

from .action_schema import ActionValidationError, validate_action_batch
from .observation_schema import (
    ObservationValidationError,
    prepare_mcp_observation,
    validate_action_results,
    validate_observation,
)
from .scenarios import (
    DEFAULT_SCENARIO_ID,
    is_allowed_game_over,
    scenario_act_request_limit,
)
from .trajectory_logger import LogPersistenceError


PROTOCOL_VERSION = 3
SAFE_INTEGER_MAX = 9_007_199_254_740_991


class SessionError(RuntimeError):
    """Raised when an MCP operation cannot be completed safely."""


@dataclass(frozen=True)
class SessionResult:
    status: str
    observation: dict | None = None
    action_results: list[dict] | None = None
    game_over: dict | None = None


class GameSession:
    def __init__(self, config, trajectory_logger=None):
        self.config = config
        self._trajectory_logger = trajectory_logger
        self._log_attempt_active = False
        self._log_closed = False
        self._condition = Condition(Lock())
        self._send_packet = None
        self._latest_observation = None
        self._pending_observation_id = None
        self._pending_results = None
        self._pending_next_observation = None
        self._game_over = None
        self._stopped_result = None
        self._stop_waiting = False
        self._state = "waiting_for_game"
        self._act_request_count = 0
        self._request_limit_pending = False
        self._end_game_sent = False
        self._scenario_id = None

    @property
    def act_request_count(self):
        with self._condition:
            return self._act_request_count

    @property
    def scenario_id(self):
        with self._condition:
            return self._scenario_id

    @property
    def act_request_limit(self):
        with self._condition:
            return self._act_request_limit_locked()

    def attach(self, send_packet, scenario_id=DEFAULT_SCENARIO_ID):
        with self._condition:
            if self._send_packet is not None:
                raise SessionError("controller_busy")
            if self._state in {"stopped", "game_over"}:
                raise SessionError(self._state)
            if (
                self._scenario_id is not None
                and self._scenario_id != scenario_id
            ):
                raise SessionError("scenario_mismatch")
            self._start_log_attempt_locked()
            self._scenario_id = scenario_id
            self._act_request_count = 0
            self._request_limit_pending = False
            self._end_game_sent = False
            self._send_packet = send_packet
            self._state = (
                "ready" if self._latest_observation is not None else "waiting_for_observation"
            )
            self._condition.notify_all()

    def wait_for_scenario(self, timeout=None):
        deadline = _deadline(timeout or self.config.wait_timeout_seconds)
        with self._condition:
            while self._scenario_id is None:
                remaining = _remaining(deadline)
                if remaining <= 0:
                    raise SessionError("game_not_connected")
                self._condition.wait(timeout=remaining)
            return self._scenario_id

    def detach(self, reason):
        log_status = None
        with self._condition:
            self._send_packet = None
            self._clear_pending_locked()
            self._stop_waiting = False
            if self._stopped_result is not None:
                self._state = "stopped"
            elif self._game_over is None:
                self._state = "disconnected"
            else:
                self._state = "game_over"
            log_status = self._claim_log_finish_locked("stopped")
            self._condition.notify_all()
        if log_status is not None:
            self._finish_log_attempt(log_status)
        if reason == "mcp_shutdown":
            self._close_log()

    def receive_observation(self, value):
        try:
            safe = validate_observation(value)
        except ObservationValidationError as error:
            raise SessionError("invalid_observation") from error

        with self._condition:
            if self._state in {"stopped", "game_over"}:
                raise SessionError(self._state)
            if self._pending_observation_id is not None:
                if self._pending_next_observation is not None:
                    raise SessionError("duplicate_observation")
                if safe["observation_id"] == self._pending_observation_id:
                    raise SessionError("stale_observation")
                self._pending_next_observation = safe
            else:
                self._latest_observation = safe
                if self._send_packet is not None:
                    self._state = "ready"
            self._condition.notify_all()

    def receive_action_results(self, observation_id, results):
        observation_id = _require_observation_id(observation_id)
        try:
            safe_results = validate_action_results(results)
        except ObservationValidationError as error:
            raise SessionError("invalid_action_results") from error

        with self._condition:
            if self._pending_observation_id is None:
                raise SessionError("unexpected_action_results")
            if observation_id != self._pending_observation_id:
                raise SessionError("action_results_observation_mismatch")
            if self._pending_results is not None:
                raise SessionError("duplicate_action_results")
            self._pending_results = safe_results
            self._condition.notify_all()

    def receive_game_over(self, packet):
        safe = _validate_game_over(packet, self._scenario_id)
        log_status = None
        with self._condition:
            if self._game_over is not None:
                if safe == self._game_over:
                    return
                raise SessionError("duplicate_game_over")
            if self._pending_observation_id is not None:
                if safe["observation_id"] != self._pending_observation_id:
                    raise SessionError("game_over_observation_mismatch")
            elif (
                self._latest_observation is not None
                and safe["observation_id"] != self._latest_observation["observation_id"]
            ):
                raise SessionError("game_over_observation_mismatch")
            self._game_over = safe
            self._state = "game_over"
            log_status = self._claim_log_finish_locked(safe["outcome"])
            self._condition.notify_all()
        if log_status is not None:
            self._finish_log_attempt(log_status)

    def receive_stop(self, packet):
        safe, results = _validate_stop(packet, expected_reason="escape_stop")
        log_status = None
        with self._condition:
            self._clear_pending_locked()
            self._stopped_result = SessionResult(
                status="stopped",
                action_results=results,
            )
            self._stop_waiting = False
            self._state = "stopped"
            log_status = self._claim_log_finish_locked("stopped")
            self._condition.notify_all()
        if log_status is not None:
            self._finish_log_attempt(log_status)
        return self._copy_result(self._stopped_result)

    def receive_stop_ack(self, packet):
        if not isinstance(packet, dict) or set(packet) != {
            "type",
            "protocol_version",
            "observation_id",
            "results",
        }:
            raise SessionError("invalid_stop_ack")
        if packet.get("type") != "stop_ack" or packet.get("protocol_version") != PROTOCOL_VERSION:
            raise SessionError("invalid_stop_ack")
        observation_id = _require_observation_id(packet.get("observation_id"), optional=True)
        try:
            results = validate_action_results(packet["results"])
        except ObservationValidationError as error:
            raise SessionError("invalid_stop_ack") from error

        log_status = None
        with self._condition:
            if self._pending_observation_id is not None and (
                observation_id != self._pending_observation_id
            ):
                raise SessionError("stop_ack_observation_mismatch")
            self._clear_pending_locked()
            self._stopped_result = SessionResult(
                status="stopped",
                action_results=results,
            )
            self._stop_waiting = False
            self._state = "stopped"
            log_status = self._claim_log_finish_locked("stopped")
            self._condition.notify_all()
        if log_status is not None:
            self._finish_log_attempt(log_status)

    def observe(self, timeout=None):
        deadline = _deadline(timeout or self.config.wait_timeout_seconds)
        with self._condition:
            while True:
                if self._state == "game_over":
                    return self._copy_result(SessionResult(
                        status="game_over",
                        game_over=self._game_over,
                    ))
                if self._state == "stopped":
                    return self._copy_result(self._stopped_result or SessionResult("stopped"))
                if self._state == "disconnected":
                    return SessionResult(status="disconnected")
                if (
                    self._latest_observation is not None
                    and self._state not in {"executing", "stopping", "ending"}
                ):
                    return SessionResult(
                        status="ready",
                        observation=deepcopy(self._latest_observation),
                    )
                remaining = _remaining(deadline)
                if remaining <= 0:
                    raise SessionError("observation_timeout")
                self._condition.wait(timeout=remaining)

    def act(self, observation_id, actions, timeout=None):
        deadline = _deadline(timeout or self.config.wait_timeout_seconds)
        with self._condition:
            request_number = self._record_act_request_locked()

        try:
            result = self._execute_act(observation_id, actions, deadline)
        except SessionError:
            if request_number < self._act_request_limit():
                raise
            return self._request_limit_result(deadline, [])
        if (
            request_number < self._act_request_limit()
            or result.status == "game_over"
        ):
            return result
        return self._request_limit_result(
            deadline,
            result.action_results or [],
        )

    def _execute_act(self, observation_id, actions, deadline):
        with self._condition:
            observation_id = _require_observation_id(observation_id)
            self._require_ready_action_state_locked(observation_id)
            try:
                validate_action_batch(
                    actions,
                    self._available_interactions(self._latest_observation),
                    self._interface_open(self._latest_observation),
                )
            except ActionValidationError as error:
                raise SessionError(str(error)) from error

            self._pending_observation_id = observation_id
            self._pending_results = None
            self._pending_next_observation = None
            self._state = "executing"
            packet = {
                "type": "action_batch",
                "protocol_version": PROTOCOL_VERSION,
                "observation_id": observation_id,
                "actions": deepcopy(actions),
            }
            sender = self._send_packet
            if sender is None:
                self._clear_pending_locked()
                self._state = "disconnected"
                raise SessionError("transport_unavailable")
            try:
                sent = sender(packet)
            except Exception as error:
                self._send_packet = None
                self._clear_pending_locked()
                self._state = "disconnected"
                raise SessionError("transport_unavailable") from error
            if sent is not True:
                self._send_packet = None
                self._clear_pending_locked()
                self._state = "disconnected"
                raise SessionError("transport_unavailable")

            while True:
                if self._pending_next_observation is not None:
                    return self._complete_turn_locked()
                if self._game_over is not None:
                    return self._complete_terminal_turn_locked()
                if self._state in {"stopped", "disconnected"}:
                    raise SessionError(self._state)
                remaining = _remaining(deadline)
                if remaining <= 0:
                    self._clear_pending_locked()
                    self._state = "ready" if self._send_packet is not None else "disconnected"
                    raise SessionError("action_timeout")
                self._condition.wait(timeout=remaining)

    def _request_limit_result(self, deadline, action_results):
        with self._condition:
            if self._game_over is not None:
                return SessionResult(
                    status="game_over",
                    action_results=deepcopy(action_results),
                    game_over=deepcopy(self._game_over),
                )

            observation_id = self._pending_observation_id
            if observation_id is None and self._latest_observation is not None:
                observation_id = self._latest_observation["observation_id"]
            if not self._end_game_sent:
                packet = {
                    "type": "end_game",
                    "protocol_version": PROTOCOL_VERSION,
                    "observation_id": observation_id,
                    "outcome": "failure",
                    "reason": "max_requests",
                }
                sender = self._send_packet
                if sender is None:
                    self._state = "disconnected"
                    raise SessionError("disconnected")
                self._end_game_sent = True
                self._state = "ending"
                try:
                    sent = sender(packet)
                except Exception as error:
                    self._send_packet = None
                    self._state = "disconnected"
                    self._condition.notify_all()
                    raise SessionError("transport_unavailable") from error
                if sent is not True:
                    self._send_packet = None
                    self._state = "disconnected"
                    self._condition.notify_all()
                    raise SessionError("transport_unavailable")

            while True:
                if self._game_over is not None:
                    results = action_results
                    if not results and self._pending_results is not None:
                        results = self._pending_results
                    return SessionResult(
                        status="game_over",
                        action_results=deepcopy(results),
                        game_over=deepcopy(self._game_over),
                    )
                if self._state in {"stopped", "disconnected"}:
                    raise SessionError(self._state)
                remaining = _remaining(deadline)
                if remaining <= 0:
                    raise SessionError("action_timeout")
                self._condition.wait(timeout=remaining)

    def _record_act_request_locked(self):
        if self._state in {"stopped", "game_over"}:
            raise SessionError(self._state)
        if self._request_limit_pending:
            raise SessionError("request_limit_reached")
        self._act_request_count += 1
        if self._act_request_count >= self._act_request_limit_locked():
            self._request_limit_pending = True
        return self._act_request_count

    def _act_request_limit(self):
        with self._condition:
            return self._act_request_limit_locked()

    def _act_request_limit_locked(self):
        if self._scenario_id is None:
            return self.config.max_act_requests
        return scenario_act_request_limit(
            self._scenario_id,
            self.config.max_act_requests,
        )

    def stop(self, timeout=None):
        deadline = _deadline(timeout or self.config.stop_timeout_seconds)
        with self._condition:
            if self._stopped_result is not None:
                return self._copy_result(self._stopped_result)
            if self._stop_waiting:
                return self._wait_for_stop_locked(deadline)

            sender = self._send_packet
            observation_id = self._pending_observation_id
            if observation_id is None and self._latest_observation is not None:
                observation_id = self._latest_observation["observation_id"]
            packet = {
                "type": "stop_request",
                "protocol_version": PROTOCOL_VERSION,
                "observation_id": observation_id,
                "reason": "mcp_stop",
            }
            self._stop_waiting = True
            self._state = "stopping"
            if sender is None:
                self._clear_pending_locked()
                self._stop_waiting = False
                self._stopped_result = SessionResult(status="stopped", action_results=[])
                self._state = "stopped"
                self._condition.notify_all()
                return self._copy_result(self._stopped_result)
            try:
                sent = sender(packet)
            except Exception:
                sent = False
            if sent is not True:
                self._send_packet = None
                self._clear_pending_locked()
                self._stop_waiting = False
                self._stopped_result = SessionResult(status="stopped", action_results=[])
                self._state = "stopped"
                self._condition.notify_all()
                return self._copy_result(self._stopped_result)
            return self._wait_for_stop_locked(deadline)

    def to_mcp_payload(self, result):
        payload = {
            "status": result.status,
            "action_results": deepcopy(result.action_results or []),
            "game_over": deepcopy(result.game_over),
            "observation": None,
        }
        image_bytes = None
        if result.observation is not None:
            public, image_bytes = prepare_mcp_observation(result.observation)
            payload["observation"] = public
        return payload, image_bytes

    def _require_ready_action_state_locked(self, observation_id):
        if self._state == "game_over":
            raise SessionError("game_over")
        if self._state == "stopped":
            raise SessionError("stopped")
        if self._state == "disconnected":
            raise SessionError("disconnected")
        if self._pending_observation_id is not None:
            raise SessionError("action_in_flight")
        if self._latest_observation is None:
            raise SessionError("waiting_for_observation")
        if observation_id != self._latest_observation["observation_id"]:
            raise SessionError("stale_observation")
        if self._send_packet is None:
            raise SessionError("transport_unavailable")

    def _complete_turn_locked(self):
        observation = self._pending_next_observation
        results = self._pending_results or []
        self._latest_observation = observation
        self._clear_pending_locked()
        self._state = "ready"
        self._condition.notify_all()
        return SessionResult(
            status="ready",
            observation=deepcopy(observation),
            action_results=deepcopy(results),
        )

    def _complete_terminal_turn_locked(self):
        results = deepcopy(self._pending_results) if self._pending_results is not None else []
        game_over = deepcopy(self._game_over)
        self._clear_pending_locked()
        self._state = "game_over"
        self._condition.notify_all()
        return SessionResult(
            status="game_over",
            action_results=results,
            game_over=game_over,
        )

    def _wait_for_stop_locked(self, deadline):
        while True:
            if self._stopped_result is not None:
                return self._copy_result(self._stopped_result)
            if self._state == "disconnected":
                self._stop_waiting = False
                self._stopped_result = SessionResult(status="stopped", action_results=[])
                self._state = "stopped"
                return self._copy_result(self._stopped_result)
            remaining = _remaining(deadline)
            if remaining <= 0:
                self._clear_pending_locked()
                self._stop_waiting = False
                self._stopped_result = SessionResult(status="stopped", action_results=[])
                self._state = "stopped"
                self._condition.notify_all()
                raise SessionError("stop_timeout")
            self._condition.wait(timeout=remaining)

    def _clear_pending_locked(self):
        self._pending_observation_id = None
        self._pending_results = None
        self._pending_next_observation = None

    def _start_log_attempt_locked(self):
        if self._trajectory_logger is None:
            return
        try:
            self._trajectory_logger.start_attempt()
        except LogPersistenceError as error:
            raise SessionError("logging_failed") from error
        self._log_attempt_active = True

    def _claim_log_finish_locked(self, status):
        if not self._log_attempt_active:
            return None
        self._log_attempt_active = False
        return status

    def _finish_log_attempt(self, status):
        try:
            self._trajectory_logger.finish_attempt(status)
        except LogPersistenceError as error:
            raise SessionError("logging_failed") from error

    def _close_log(self):
        if self._trajectory_logger is None or self._log_closed:
            return
        self._log_closed = True
        try:
            self._trajectory_logger.close()
        except LogPersistenceError as error:
            raise SessionError("logging_failed") from error

    @staticmethod
    def _available_interactions(observation):
        return {
            item["action"] for item in observation["interface"]["available_interactions"]
        }

    @staticmethod
    def _interface_open(observation):
        return observation["interface"]["is_open"]

    @staticmethod
    def _copy_result(result):
        return deepcopy(result)


def _deadline(timeout):
    return time.monotonic() + float(timeout)


def _remaining(deadline):
    return deadline - time.monotonic()


def _require_observation_id(value, optional=False):
    if value is None and optional:
        return None
    if (
        type(value) is not int
        or not 0 <= value <= SAFE_INTEGER_MAX
    ):
        raise SessionError("invalid_observation_id")
    return value


def _validate_game_over(packet, scenario_id):
    fields = {"type", "protocol_version", "observation_id", "outcome", "reason"}
    if not isinstance(packet, dict) or set(packet) != fields:
        raise SessionError("invalid_game_over")
    if packet["type"] != "game_over" or packet["protocol_version"] != PROTOCOL_VERSION:
        raise SessionError("invalid_game_over")
    if not is_allowed_game_over(
        scenario_id,
        packet["outcome"],
        packet["reason"],
    ):
        raise SessionError("invalid_game_over")
    observation_id = _require_observation_id(
        packet["observation_id"],
        optional=packet["reason"] == "max_requests",
    )
    return {
        "type": "game_over",
        "protocol_version": PROTOCOL_VERSION,
        "observation_id": observation_id,
        "outcome": packet["outcome"],
        "reason": packet["reason"],
    }


def _validate_stop(packet, expected_reason):
    fields = {"type", "protocol_version", "observation_id", "reason", "results"}
    if not isinstance(packet, dict) or set(packet) != fields:
        raise SessionError("invalid_stop")
    if packet["type"] != "stop" or packet["protocol_version"] != PROTOCOL_VERSION:
        raise SessionError("invalid_stop")
    observation_id = _require_observation_id(packet["observation_id"], optional=True)
    if packet["reason"] != expected_reason:
        raise SessionError("invalid_stop")
    try:
        results = validate_action_results(packet["results"])
    except ObservationValidationError as error:
        raise SessionError("invalid_stop") from error
    return {
        "type": "stop",
        "protocol_version": PROTOCOL_VERSION,
        "observation_id": observation_id,
        "reason": expected_reason,
        "results": results,
    }, results
