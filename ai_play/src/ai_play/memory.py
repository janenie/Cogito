from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


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
        saved_summary = dict(summary)
        if isinstance(saved_summary.get("text"), str):
            saved_summary["text"] = saved_summary["text"][:300]
        self.working_memory.append(saved_summary)
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
        temporary_path.write_text(
            json.dumps(self.to_prompt_dict(), ensure_ascii=False, indent=2),
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
        if isinstance(value, (int, float)) and not isinstance(value, bool):
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
        if not cls._valid_entry_list(data["working_memory"], 8, require_text=False):
            raise ValueError("malformed working memory")
        if not cls._valid_entry_list(data["facts"], 64, expected_kind="fact"):
            raise ValueError("malformed facts")
        if not cls._valid_entry_list(data["spatial_memory"], 48, expected_kind="landmark"):
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

    @staticmethod
    def _valid_entry_list(
        entries: Any,
        limit: int,
        expected_kind: str | None = None,
        require_text: bool = True,
    ) -> bool:
        if not isinstance(entries, list) or len(entries) > limit:
            return False
        for entry in entries:
            if not isinstance(entry, dict):
                return False
            if expected_kind is not None and entry.get("kind") != expected_kind:
                return False
            if require_text and (
                not isinstance(entry.get("text"), str) or len(entry["text"]) > 300
            ):
                return False
        return True
