from __future__ import annotations

import threading
from copy import deepcopy

from .action_schema import validate_decision
from .api_client import parse_model_json
from .memory import MemoryStore
from .observation_schema import OBSERVATION_FIELDS, ObservationValidationError, validate_observation
from .prompts import SYSTEM_PROMPT, build_log_messages, build_messages


class AgentLoop:
    def __init__(
        self,
        api_client,
        memory,
        memory_path=None,
        resume=False,
        run_logger=None,
    ):
        self.api_client = api_client
        self.memory = memory
        self.memory_path = memory_path
        self.resume = resume
        self.run_logger = run_logger
        self._decision_lock = threading.Lock()
        self._pending_step = None
        self._staged_batch = None

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
            messages = build_messages(safe_observation, prompt_memory)
            if self.run_logger is None:
                proposal = self.api_client.decide(messages)
            else:
                logged_observation = deepcopy(safe_observation)
                logged_observation["image"].pop("base64", None)
                stage = "model_input_log"
                self.run_logger.write_event(
                    "model_input",
                    round_ref,
                    model=self.api_client.config.model,
                    image_path=round_ref.image_path,
                    system_prompt=SYSTEM_PROMPT,
                    observation=logged_observation,
                    memory=prompt_memory,
                    messages=build_log_messages(messages, round_ref.image_path),
                )
                stage = "api"
                completion = self.api_client.complete(messages)
                stage = "model_output_log"
                self.run_logger.write_event(
                    "model_output",
                    round_ref,
                    raw_content=completion.raw_content,
                    latency_ms=completion.latency_ms,
                )
                stage = "parse"
                proposal = parse_model_json(completion.raw_content)
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
            if self.run_logger is not None:
                stage = "decision_log"
                self.run_logger.write_event(
                    "decision_validated",
                    round_ref,
                    decision=decision,
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
                "reason": decision["reason"],
                "actions": decision["actions"],
            }
            if self.run_logger is not None:
                stage = "dispatch_request_log"
                self.run_logger.write_event(
                    "action_dispatch_requested",
                    round_ref,
                    reason=decision["reason"],
                    memory_updates=decision["memory_updates"],
                    actions=decision["actions"],
                )
            self._staged_batch = {
                "observation_id": observation_id,
                "memory": staged_memory,
                "pending_step": next_pending_step,
                "round_ref": round_ref,
                "packet": deepcopy(packet),
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
                    staged["memory"].save(self.memory_path)
                if self.run_logger is not None:
                    packet = staged["packet"]
                    self.run_logger.write_event(
                        "action_dispatched",
                        staged["round_ref"],
                        reason=packet["reason"],
                        actions=packet["actions"],
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
