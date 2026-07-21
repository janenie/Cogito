"""Append-only, run-scoped audit logging for AI play."""

from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any


_UNSAFE_MODEL_CHARACTER = re.compile(r"[^A-Za-z0-9_-]")


def sanitize_model_name(model: str) -> str:
    sanitized = _UNSAFE_MODEL_CHARACTER.sub("_", model)
    return sanitized or "model"


@dataclass(frozen=True)
class RoundRef:
    round_idx: int
    observation_id: int
    image_path: str


def _contains_base64_image(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and key.casefold() == "base64":
                return True
            if _contains_base64_image(child):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_base64_image(child) for child in value)
    return (
        isinstance(value, str)
        and value.startswith("data:image/")
        and ";base64," in value[:64]
    )


class RunLogger:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.jsonl_path = run_dir / "gemini_godot.jsonl"
        self._image_dir = run_dir / "img"
        self._image_dir.mkdir()
        self._stream = self.jsonl_path.open(
            "a", encoding="utf-8", buffering=1
        )
        self._lock = threading.Lock()
        self._next_round_idx = 1
        self._rounds_by_observation: dict[int, RoundRef] = {}

    @classmethod
    def create(
        cls,
        root: Path,
        model: str,
        now: datetime | None = None,
    ) -> "RunLogger":
        started_at = now or datetime.now().astimezone()
        model_dir = Path(root).expanduser() / sanitize_model_name(model)
        model_dir.mkdir(parents=True, exist_ok=True)
        stem = started_at.strftime("%Y%m%d-%H-%M")
        suffix = 1
        while True:
            name = stem if suffix == 1 else f"{stem}-{suffix:02d}"
            run_dir = model_dir / name
            try:
                run_dir.mkdir()
            except FileExistsError:
                suffix += 1
                continue
            return cls(run_dir)

    def begin_round(self, observation_id: int, image: dict) -> RoundRef:
        with self._lock:
            if observation_id in self._rounds_by_observation:
                raise ValueError("duplicate observation_id")
            if not isinstance(image, dict) or image.get("mime_type") != "image/jpeg":
                raise ValueError("round image must use image/jpeg")
            encoded = image.get("base64")
            if not isinstance(encoded, str):
                raise ValueError("round image base64 must be text")
            try:
                jpeg_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as error:
                raise ValueError("invalid base64 image") from error

            round_idx = self._next_round_idx
            relative_path = f"img/{round_idx:06d}.jpg"
            target = self.run_dir / relative_path
            temporary = target.with_suffix(".jpg.part")
            try:
                temporary.write_bytes(jpeg_bytes)
                temporary.replace(target)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise

            round_ref = RoundRef(round_idx, observation_id, relative_path)
            self._rounds_by_observation[observation_id] = round_ref
            self._next_round_idx += 1
            return round_ref

    def write_event(
        self,
        event: str,
        round_ref: RoundRef | None = None,
        **fields,
    ) -> None:
        if not isinstance(event, str) or not event:
            raise ValueError("event must be nonblank text")
        if _contains_base64_image(fields):
            raise ValueError("base64 image data is forbidden in JSONL")
        payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        }
        if round_ref is not None:
            payload.update(
                round_idx=round_ref.round_idx,
                observation_id=round_ref.observation_id,
            )
        payload.update(deepcopy(fields))
        line = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        with self._lock:
            self._stream.write(line + "\n")
            self._stream.flush()

    def round_for_observation(self, observation_id: int) -> RoundRef | None:
        with self._lock:
            return self._rounds_by_observation.get(observation_id)

    def finish_round(self, observation_id: int) -> RoundRef | None:
        with self._lock:
            return self._rounds_by_observation.pop(observation_id, None)

    def close(self) -> None:
        with self._lock:
            if not self._stream.closed:
                self._stream.close()
