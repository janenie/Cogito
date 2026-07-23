from __future__ import annotations

import re
import threading
from copy import deepcopy

from .action_schema import validate_decision
from .api_client import parse_model_json
from .memory import MemoryStore
from .observation_schema import OBSERVATION_FIELDS, ObservationValidationError, validate_observation
from .probe_interaction_harness import build_probe_interaction_harness
from .prompts import build_messages


REDACTED_VALUE = "[REDACTED]"
MODEL_NUMERIC_TEXT = re.compile(r"(?<![0-9])[0-9]{1,6}(?![0-9])")


def _submitted_digit_values(value):
    if not isinstance(value, dict) or not isinstance(value.get("actions"), list):
        return []
    return [
        action["digits"]
        for action in value["actions"]
        if isinstance(action, dict)
        and action.get("type") == "enter_digits"
        and isinstance(action.get("digits"), str)
        and action["digits"]
    ]


def _redact_for_log(value, sensitive_values):
    if isinstance(value, dict):
        return {
            key: (
                REDACTED_VALUE
                if key == "digits" and isinstance(child, str)
                else _redact_for_log(child, sensitive_values)
            )
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_for_log(child, sensitive_values) for child in value]
    if isinstance(value, str):
        redacted = MODEL_NUMERIC_TEXT.sub(REDACTED_VALUE, value)
        for sensitive in sensitive_values:
            redacted = redacted.replace(sensitive, REDACTED_VALUE)
        return redacted
    return deepcopy(value)


class AgentLoop:
    def __init__(
        self,
        api_client,
        memory,
        memory_path=None,
        resume=False,
        run_logger=None,
        game_context=None,
    ):
        self.api_client = api_client
        self.memory = memory
        self.memory_path = memory_path
        self.resume = resume
        self.run_logger = run_logger
        self.game_context = game_context
        api_config = getattr(api_client, "config", None)
        self.max_model_requests = getattr(
            api_config,
            "max_model_requests",
            1000,
        )
        self.model_request_count = 0
        self._decision_lock = threading.Lock()
        self._pending_step = None
        self._staged_batch = None
        self._game_over_recorded = False

    def configure_memory(self, memory_path):
        with self._decision_lock:
            self._pending_step = None
            self._staged_batch = None
            if self.memory_path == memory_path:
                return
            self.memory_path = memory_path
            self.memory = (
                MemoryStore.load(memory_path) if self.resume else MemoryStore.empty()
            )

    def handle_observation(self, observation):
        received_id = (
            observation.get("observation_id") if isinstance(observation, dict) else None
        )
        print(f"AI_PLAY received observation={received_id}", flush=True)
        if not self._decision_lock.acquire(blocking=False):
            return self._error(observation, RuntimeError())
        round_ref = None
        stage = "observation_validation"
        try:
            if self._staged_batch is not None:
                raise RuntimeError("action batch awaiting delivery")
            allowed_wire_fields = OBSERVATION_FIELDS | {"type", "protocol_version"}
            if not isinstance(observation, dict) or not set(observation).issubset(allowed_wire_fields):
                raise ObservationValidationError("observation has invalid wire fields")
            safe_observation = validate_observation(
                {field: observation[field] for field in OBSERVATION_FIELDS if field in observation}
            )
            if self.run_logger is not None:
                stage = "image_persistence"
                round_ref = self.run_logger.begin_round(
                    safe_observation["observation_id"],
                    safe_observation["image"],
                )
            staged_memory = deepcopy(self.memory)
            if self._pending_step is not None:
                completed_step = deepcopy(self._pending_step)
                completed_step["last_action_results"] = deepcopy(
                    safe_observation["last_action_results"]
                )
                staged_memory.record_step(completed_step)
            prompt_memory = staged_memory.to_prompt_dict()
            probe_harness = build_probe_interaction_harness(safe_observation)
            messages = build_messages(
                safe_observation,
                prompt_memory,
                self.game_context,
                probe_harness,
            )
            if self.model_request_count >= self.max_model_requests:
                return self._max_requests_packet(safe_observation["observation_id"])
            sensitive_values = []
            if self.run_logger is None:
                stage = "api"
                self.model_request_count += 1
                proposal = self.api_client.decide(messages)
            else:
                logged_observation = deepcopy(safe_observation)
                logged_observation["image"].pop("base64", None)
                stage = "model_input_log"
                model_input_fields = {
                    "model": self.api_client.config.model,
                    "image_path": round_ref.image_path,
                    "observation": logged_observation,
                    "memory": _redact_for_log(prompt_memory, []),
                    "probe_interaction_harness": deepcopy(probe_harness),
                }
                if self.game_context is not None:
                    model_input_fields["reference_atlas_path"] = (
                        self.game_context.reference_log_path
                    )
                self.run_logger.write_event(
                    "model_input",
                    round_ref,
                    **model_input_fields,
                )
                stage = "api"
                self.model_request_count += 1
                completion = self.api_client.complete(messages)
                stage = "parse"
                try:
                    proposal = parse_model_json(completion.raw_content)
                except Exception:
                    self.run_logger.write_event(
                        "model_output",
                        round_ref,
                        raw_content=completion.raw_content,
                        latency_ms=completion.latency_ms,
                    )
                    stage = "parse"
                    raise
                sensitive_values = _submitted_digit_values(proposal)
                stage = "model_output_log"
                self.run_logger.write_event(
                    "model_output",
                    round_ref,
                    raw_content=completion.raw_content,
                    latency_ms=completion.latency_ms,
                )
            interface = safe_observation["interface"]
            visible_actions = [
                interaction.get("action")
                for interaction in interface.get("available_interactions", [])
                if isinstance(interaction, dict)
                and isinstance(interaction.get("action"), str)
            ]
            stage = "decision_validation"
            decision = validate_decision(
                proposal,
                visible_actions,
                interface.get("is_open") is True,
            )
            observation_id = safe_observation["observation_id"]
            sensitive_values = _submitted_digit_values(decision)
            if self.run_logger is not None:
                stage = "decision_log"
                self.run_logger.write_event(
                    "decision_validated",
                    round_ref,
                    decision=_redact_for_log(decision, sensitive_values),
                )
            staged_memory.apply_updates(decision["memory_updates"], observation_id)
            next_pending_step = {
                "observation_id": observation_id,
                "reason": decision["reason"],
                "actions": deepcopy(decision["actions"]),
            }
            packet = {
                "type": "action_batch",
                "protocol_version": 1,
                "observation_id": observation_id,
                "request_count": self.model_request_count,
                "request_limit": self.max_model_requests,
                "reason": decision["reason"],
                "actions": decision["actions"],
            }
            if self.run_logger is not None:
                stage = "dispatch_request_log"
                self.run_logger.write_event(
                    "action_dispatch_requested",
                    round_ref,
                    reason=_redact_for_log(decision["reason"], sensitive_values),
                    memory_updates=_redact_for_log(
                        decision["memory_updates"],
                        sensitive_values,
                    ),
                    actions=_redact_for_log(decision["actions"], sensitive_values),
                )
            self._staged_batch = {
                "observation_id": observation_id,
                "memory": staged_memory,
                "pending_step": next_pending_step,
                "round_ref": round_ref,
                "packet": deepcopy(packet),
                "sensitive_values": sensitive_values,
            }
            action_types = [action["type"] for action in decision["actions"]]
            print(
                f"AI_PLAY prepared actions for observation={observation_id}: {action_types}",
                flush=True,
            )
            return packet
        except Exception as exc:
            print(
                f"AI_PLAY decision failed for observation={received_id}: {type(exc).__name__}",
                flush=True,
            )
            if self.run_logger is not None and round_ref is not None:
                try:
                    self.run_logger.write_event(
                        "round_error",
                        round_ref,
                        stage=stage,
                        error_type=type(exc).__name__,
                    )
                except Exception:
                    pass
                self.run_logger.finish_round(round_ref.observation_id)
            if self.model_request_count >= self.max_model_requests:
                return self._max_requests_packet(received_id)
            return self._error(observation, exc)
        finally:
            self._decision_lock.release()

    def commit_action_batch_sent(self, observation_id):
        with self._decision_lock:
            staged = self._staged_batch
            if staged is None or staged["observation_id"] != observation_id:
                return False
            try:
                if self.memory_path is not None:
                    save_redacted = getattr(staged["memory"], "save_redacted", None)
                    if callable(save_redacted):
                        save_redacted(self.memory_path)
                    else:
                        staged["memory"].save(self.memory_path)
                if self.run_logger is not None:
                    packet = staged["packet"]
                    self.run_logger.write_event(
                        "action_dispatched",
                        staged["round_ref"],
                        reason=_redact_for_log(
                            packet["reason"],
                            staged["sensitive_values"],
                        ),
                        actions=_redact_for_log(
                            packet["actions"],
                            staged["sensitive_values"],
                        ),
                    )
            except Exception:
                self._staged_batch = None
                return False
            self.memory = staged["memory"]
            self._pending_step = staged["pending_step"]
            self._staged_batch = None
            return True

    def record_action_results(self, observation_id, results):
        if self.run_logger is None:
            return True
        round_ref = self.run_logger.round_for_observation(observation_id)
        if round_ref is None:
            return False
        self.run_logger.write_event(
            "godot_result",
            round_ref,
            results=deepcopy(results),
        )
        self.run_logger.finish_round(observation_id)
        return True

    def record_stop(self, reason, observation_id=None, results=None):
        if self.run_logger is None:
            return
        round_ref = (
            self.run_logger.round_for_observation(observation_id)
            if observation_id is not None
            else None
        )
        self.run_logger.write_event(
            "session_stop",
            round_ref,
            reason=reason,
            results=deepcopy(results or []),
        )
        if observation_id is not None:
            self.run_logger.finish_round(observation_id)

    def record_game_over(self, observation_id, outcome, reason, request_count):
        with self._decision_lock:
            if self._game_over_recorded or self._pending_step is None:
                return False
            if self._pending_step["observation_id"] != observation_id:
                return False
            if request_count != self.model_request_count:
                return False
            if not self._is_valid_game_over(outcome, reason):
                return False
            self._record_game_over_event(
                observation_id,
                outcome,
                reason,
                request_count,
            )
            return True

    def discard_action_batch(self, observation_id):
        with self._decision_lock:
            if (
                self._staged_batch is None
                or self._staged_batch["observation_id"] != observation_id
            ):
                return False
            if self.run_logger is not None:
                round_ref = self._staged_batch["round_ref"]
                try:
                    self.run_logger.write_event(
                        "round_error",
                        round_ref,
                        stage="action_transport",
                        error_type="ActionBatchDiscarded",
                    )
                finally:
                    self.run_logger.finish_round(observation_id)
            self._staged_batch = None
            return True

    @staticmethod
    def _error(observation, exc):
        return {
            "type": "error",
            "protocol_version": 1,
            "observation_id": observation.get("observation_id"),
            "code": "decision_failed",
            "message": type(exc).__name__,
        }

    def _max_requests_packet(self, observation_id):
        self._record_game_over_event(
            observation_id,
            "failure",
            "max_requests",
            self.model_request_count,
        )
        return {
            "type": "game_over",
            "protocol_version": 1,
            "observation_id": observation_id,
            "outcome": "failure",
            "reason": "max_requests",
            "request_count": self.model_request_count,
        }

    @staticmethod
    def _is_valid_game_over(outcome, reason):
        return (outcome, reason) in {
            ("success", "correct_password"),
            ("failure", "wrong_password"),
            ("failure", "max_requests"),
        }

    def _record_game_over_event(
        self,
        observation_id,
        outcome,
        reason,
        request_count,
    ):
        if self._game_over_recorded:
            return
        self._game_over_recorded = True
        if self.run_logger is not None:
            round_ref = self.run_logger.round_for_observation(observation_id)
            fields = {
                "outcome": outcome,
                "reason": reason,
                "request_count": request_count,
            }
            if round_ref is None:
                fields["observation_id"] = observation_id
            self.run_logger.write_event("game_over", round_ref, **fields)
            self.run_logger.finish_round(observation_id)
        print(
            "AI_PLAY game over: "
            f"outcome={outcome} reason={reason} requests={request_count}",
            flush=True,
        )
