from __future__ import annotations

import threading

from .action_schema import validate_decision
from .memory import MemoryStore
from .prompts import build_messages


class AgentLoop:
    def __init__(self, api_client, memory, memory_path=None, resume=False):
        self.api_client = api_client
        self.memory = memory
        self.memory_path = memory_path
        self.resume = resume
        self._decision_lock = threading.Lock()

    def configure_memory(self, memory_path):
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
            messages = build_messages(observation, self.memory.to_prompt_dict())
            proposal = self.api_client.decide(messages)
            interface = observation.get("interface", {})
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
            observation_id = observation.get("observation_id")
            self.memory.apply_updates(decision["memory_updates"], observation_id)
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
