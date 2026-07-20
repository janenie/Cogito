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

    def configure_memory(self, memory_path):
        if self.memory_path == memory_path:
            return
        self.memory_path = memory_path
        self.memory = (
            MemoryStore.load(memory_path) if self.resume else MemoryStore.empty()
        )
        self._pending_step = None

    def handle_observation(self, observation):
        if not self._decision_lock.acquire(blocking=False):
            return self._error(observation, RuntimeError())
        try:
            allowed_wire_fields = OBSERVATION_FIELDS | {"type", "protocol_version"}
            if not isinstance(observation, dict) or not set(observation).issubset(allowed_wire_fields):
                raise ObservationValidationError("observation has invalid wire fields")
            safe_observation = validate_observation(
                {field: observation[field] for field in OBSERVATION_FIELDS if field in observation}
            )
            if self._pending_step is not None:
                completed_step = deepcopy(self._pending_step)
                completed_step["last_action_results"] = deepcopy(
                    safe_observation["last_action_results"]
                )
                self.memory.record_step(completed_step)
                self._pending_step = None
                if self.memory_path is not None:
                    self.memory.save(self.memory_path)
            messages = build_messages(safe_observation, self.memory.to_prompt_dict())
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
            self.memory.apply_updates(decision["memory_updates"], observation_id)
            self._pending_step = {
                "observation_id": observation_id,
                "reason": decision["reason"],
                "actions": deepcopy(decision["actions"]),
            }
            if self.memory_path is not None:
                self.memory.save(self.memory_path)
            return {
                "type": "action_batch",
                "protocol_version": 1,
                "observation_id": observation_id,
                "reason": decision["reason"],
                "actions": decision["actions"],
            }
        except Exception as exc:
            return self._error(observation, exc)
        finally:
            self._decision_lock.release()

    @staticmethod
    def _error(observation, exc):
        return {
            "type": "error",
            "protocol_version": 1,
            "observation_id": observation.get("observation_id"),
            "code": "decision_failed",
            "message": type(exc).__name__,
        }
