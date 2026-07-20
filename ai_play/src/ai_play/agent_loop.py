from __future__ import annotations

import threading
from copy import deepcopy

from .action_schema import validate_decision
from .memory import MemoryStore
from .observation_schema import OBSERVATION_FIELDS, ObservationValidationError, validate_observation
from .prompts import build_messages


class AgentLoop:
    def __init__(self, api_client, memory, memory_path=None, resume=False):
        self.api_client = api_client
        self.memory = memory
        self.memory_path = memory_path
        self.resume = resume
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
        if not self._decision_lock.acquire(blocking=False):
            return self._error(observation, RuntimeError())
        try:
            if self._staged_batch is not None:
                raise RuntimeError("action batch awaiting delivery")
            allowed_wire_fields = OBSERVATION_FIELDS | {"type", "protocol_version"}
            if not isinstance(observation, dict) or not set(observation).issubset(allowed_wire_fields):
                raise ObservationValidationError("observation has invalid wire fields")
            safe_observation = validate_observation(
                {field: observation[field] for field in OBSERVATION_FIELDS if field in observation}
            )
            staged_memory = deepcopy(self.memory)
            if self._pending_step is not None:
                completed_step = deepcopy(self._pending_step)
                completed_step["last_action_results"] = deepcopy(
                    safe_observation["last_action_results"]
                )
                staged_memory.record_step(completed_step)
            messages = build_messages(safe_observation, staged_memory.to_prompt_dict())
            proposal = self.api_client.decide(messages)
            interface = safe_observation["interface"]
            visible_actions = [
                interaction.get("action")
                for interaction in interface.get("available_interactions", [])
                if isinstance(interaction, dict)
                and isinstance(interaction.get("action"), str)
            ]
            decision = validate_decision(
                proposal,
                visible_actions,
                interface.get("is_open") is True,
            )
            observation_id = safe_observation["observation_id"]
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
            self._staged_batch = {
                "observation_id": observation_id,
                "memory": staged_memory,
                "pending_step": next_pending_step,
            }
            return packet
        except Exception as exc:
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
            except Exception:
                self._staged_batch = None
                return False
            self.memory = staged["memory"]
            self._pending_step = staged["pending_step"]
            self._staged_batch = None
            return True

    def discard_action_batch(self, observation_id):
        with self._decision_lock:
            if (
                self._staged_batch is None
                or self._staged_batch["observation_id"] != observation_id
            ):
                return False
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
