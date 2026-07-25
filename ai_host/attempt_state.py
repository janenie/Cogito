from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReflectionMemory:
    mistakes: list[str] = field(default_factory=list)
    strategy: list[str] = field(default_factory=list)


@dataclass
class AttemptContext:
    attempt_id: int
    max_attempts: int
    scenario_id: str
    run_dir: Path
    reflection: ReflectionMemory


@dataclass
class AttemptResult:
    attempt_id: int
    outcome: str
    reason: str
    summary: str = ""
    mistakes: list[str] = field(default_factory=list)
    next_strategy: list[str] = field(default_factory=list)
    steps_used: int | None = None

    @property
    def success(self) -> bool:
        return self.outcome == "success"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AttemptResult":
        return cls(
            attempt_id=int(value["attempt_id"]),
            outcome=str(value["outcome"]),
            reason=str(value["reason"]),
            summary=str(value.get("summary", "")),
            mistakes=[str(item) for item in value.get("mistakes", [])],
            next_strategy=[str(item) for item in value.get("next_strategy", [])],
            steps_used=(
                int(value["steps_used"]) if value.get("steps_used") is not None else None
            ),
        )


@dataclass
class FinalReport:
    attempts: list[AttemptResult]
    run_dir: Path

    @property
    def success(self) -> bool:
        return any(attempt.success for attempt in self.attempts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }

    def write(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "final_report.json").write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"
        )
