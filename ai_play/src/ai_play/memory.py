from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any

from .action_schema import ActionValidationError, validate_decision


_SUPPORTED_KINDS = {"fact", "landmark", "goal", "question", "hypothesis", "failure"}
_TASK_LISTS = {
    "question": "questions",
    "hypothesis": "hypotheses",
    "failure": "failures",
}


@dataclass
class MemoryStore:
    working_memory: list[dict[str, Any]] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    spatial_memory: list[dict[str, Any]] = field(default_factory=list)
    task_state: dict[str, Any] = field(
        default_factory=lambda: {
            "goal": "",
            "questions": [],
            "hypotheses": [],
            "failures": [],
        }
    )

    @classmethod
    def empty(cls) -> "MemoryStore":
        return cls()

    def apply_updates(
        self,
        updates: list[dict[str, Any]],
        observation_id: int,
    ) -> None:
        expected_source = f"observation:{observation_id}"
        for update in updates:
            kind = update.get("kind")
            if kind not in _SUPPORTED_KINDS:
                continue
            if kind in {"fact", "landmark"} and update.get("source") != expected_source:
                continue

            text = update.get("text")
            if not isinstance(text, str):
                continue
            text = text[:300]
            if not self._normalize_text(text):
                continue

            if kind == "goal":
                self.task_state["goal"] = text
                continue

            entry = {"kind": kind, "text": text}
            if "source" in update:
                entry["source"] = update["source"]
            if "confidence" in update:
                entry["confidence"] = self._confidence(update)

            if kind == "fact":
                self._add_entry(self.facts, entry, 64)
            elif kind == "landmark":
                self._add_entry(self.spatial_memory, entry, 48)
            else:
                self._add_entry(self.task_state[_TASK_LISTS[kind]], entry, 24)

    def record_step(self, summary: dict[str, Any]) -> None:
        if not self._valid_working_step(summary):
            raise ValueError("malformed working memory step")
        self.working_memory.append(deepcopy(summary))
        self.working_memory = self.working_memory[-8:]

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "working_memory": self.working_memory,
            "facts": self.facts,
            "spatial_memory": self.spatial_memory,
            "task_state": self.task_state,
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        temporary_path = path.with_name(f".{path.name}.tmp")
        serialized = json.dumps(
            self.to_prompt_dict(), ensure_ascii=False, indent=2, allow_nan=False
        )
        temporary_path.write_text(
            serialized,
            encoding="utf-8",
        )
        temporary_path.replace(path)

    @classmethod
    def load(cls, path: Path) -> "MemoryStore":
        path = Path(path)
        if not path.exists():
            return cls.empty()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("malformed memory data") from error

        cls._validate_data(data)
        return cls(
            working_memory=data["working_memory"],
            facts=data["facts"],
            spatial_memory=data["spatial_memory"],
            task_state=data["task_state"],
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.split()).casefold()

    @staticmethod
    def _confidence(entry: dict[str, Any]) -> float:
        value = entry.get("confidence", 0.0)
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0.0 <= value <= 1.0
        ):
            return float(value)
        return 0.0

    @classmethod
    def _add_entry(
        cls,
        entries: list[dict[str, Any]],
        entry: dict[str, Any],
        limit: int,
    ) -> None:
        identity = (entry["kind"], cls._normalize_text(entry["text"]))
        for index, existing in enumerate(entries):
            existing_identity = (
                existing.get("kind"),
                cls._normalize_text(existing.get("text", "")),
            )
            if identity == existing_identity:
                if cls._confidence(entry) > cls._confidence(existing):
                    entries[index] = entry
                return
        entries.append(entry)
        del entries[:-limit]

    @classmethod
    def _validate_data(cls, data: Any) -> None:
        if not isinstance(data, dict) or set(data) != {
            "working_memory",
            "facts",
            "spatial_memory",
            "task_state",
        }:
            raise ValueError("malformed memory data")
        if (
            not isinstance(data["working_memory"], list)
            or len(data["working_memory"]) > 8
            or not all(cls._valid_working_step(step) for step in data["working_memory"])
        ):
            raise ValueError("malformed working memory")
        if not cls._valid_entry_list(
            data["facts"],
            64,
            expected_kind="fact",
            require_runtime_source=True,
        ):
            raise ValueError("malformed facts")
        if not cls._valid_entry_list(
            data["spatial_memory"],
            48,
            expected_kind="landmark",
            require_runtime_source=True,
        ):
            raise ValueError("malformed spatial memory")

        task_state = data["task_state"]
        if not isinstance(task_state, dict) or set(task_state) != {
            "goal",
            "questions",
            "hypotheses",
            "failures",
        }:
            raise ValueError("malformed task state")
        if not isinstance(task_state["goal"], str) or len(task_state["goal"]) > 300:
            raise ValueError("malformed goal")
        for kind, key in _TASK_LISTS.items():
            if not cls._valid_entry_list(task_state[key], 24, expected_kind=kind):
                raise ValueError(f"malformed {key}")

    @classmethod
    def _valid_entry_list(
        cls,
        entries: Any,
        limit: int,
        expected_kind: str | None = None,
        require_text: bool = True,
        require_runtime_source: bool = False,
    ) -> bool:
        if not isinstance(entries, list) or len(entries) > limit:
            return False
        identities = set()
        for entry in entries:
            if not isinstance(entry, dict):
                return False
            if expected_kind is not None and entry.get("kind") != expected_kind:
                return False
            if require_text:
                text = entry.get("text")
                if (
                    not isinstance(text, str)
                    or len(text) > 300
                    or not cls._normalize_text(text)
                ):
                    return False
                identity = (entry.get("kind"), cls._normalize_text(text))
                if identity in identities:
                    return False
                identities.add(identity)
            elif "text" in entry and (
                not isinstance(entry["text"], str) or len(entry["text"]) > 300
            ):
                return False
            if "confidence" in entry:
                confidence = entry["confidence"]
                if (
                    isinstance(confidence, bool)
                    or not isinstance(confidence, (int, float))
                    or not math.isfinite(confidence)
                    or not 0.0 <= confidence <= 1.0
                ):
                    return False
            if require_runtime_source:
                source = entry.get("source")
                prefix = "observation:"
                if not isinstance(source, str) or not source.startswith(prefix):
                    return False
                observation_id = source[len(prefix):]
                if not observation_id.isascii() or not observation_id.isdigit():
                    return False
        return True

    @staticmethod
    def _valid_working_step(step: Any) -> bool:
        if not isinstance(step, dict) or set(step) != {
            "observation_id", "reason", "actions", "last_action_results",
        }:
            return False
        observation_id = step["observation_id"]
        if type(observation_id) is not int or not 0 <= observation_id <= 9_007_199_254_740_991:
            return False
        try:
            validate_decision(
                {"reason": step["reason"], "memory_updates": [], "actions": step["actions"]},
                {"interact", "interact2"},
                True,
            )
        except ActionValidationError:
            return False
        results = step["last_action_results"]
        if not isinstance(results, list) or len(results) > 3:
            return False
        for result in results:
            if (
                not isinstance(result, dict)
                or "status" not in result
                or not set(result).issubset({"status", "type", "error", "reason"})
                or result["status"] not in {
                    "completed", "cancelled", "error", "blocked", "stopped",
                }
            ):
                return False
            status = result["status"]
            fields = set(result)
            if (
                (status == "completed" and fields != {"status", "type"})
                or (status == "error" and fields != {"status", "error"})
                or (
                    status == "cancelled"
                    and fields not in ({"status"}, {"status", "reason"})
                )
                or (status in {"blocked", "stopped"} and fields != {"status", "type"})
            ):
                return False
            if status == "blocked" and result["type"] not in {"move", "sprint"}:
                return False
            if status == "stopped" and result["type"] != "stop":
                return False
            if any(
                not isinstance(value, str) or not value or len(value) > 200
                for value in result.values()
            ):
                return False
        return True
