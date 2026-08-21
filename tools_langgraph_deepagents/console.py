from __future__ import annotations

import json
import re
import sys
from typing import Any, TextIO

from langchain_core.messages import AIMessage, ToolMessage


IMAGE_TYPES = frozenset({"image", "image_url", "input_image"})
DATA_URL_RE = re.compile(
    r"data:[^;,\s]+;base64,[A-Za-z0-9+/=_-]+",
    re.IGNORECASE,
)
BEARER_RE = re.compile(r"\bBearer\s+\S+", re.IGNORECASE)
LONG_BASE64_RE = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{64,}")


def _redact_text(value: str) -> str:
    value = DATA_URL_RE.sub("[image data redacted]", value)
    value = BEARER_RE.sub("Bearer [redacted]", value)
    return LONG_BASE64_RE.sub("[base64 redacted]", value)


def _assistant_lines(content: Any) -> list[str]:
    if isinstance(content, str):
        return [_redact_text(content)] if content.strip() else []
    if not isinstance(content, list):
        return []
    lines: list[str] = []
    for block in content:
        if isinstance(block, str) and block.strip():
            lines.append(_redact_text(block))
        elif isinstance(block, dict):
            if block.get("type") in IMAGE_TYPES:
                mime_type = block.get("mime_type", "image")
                lines.append(f"[image {mime_type}]")
            elif (
                block.get("type") in {"text", "output_text"}
                and isinstance(block.get("text"), str)
                and block["text"].strip()
            ):
                lines.append(_redact_text(block["text"]))
    return lines


def _json_payload(content: Any) -> dict[str, Any] | None:
    candidates: list[str] = []
    if isinstance(content, str):
        candidates.append(content)
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                candidates.append(block["text"])
    for candidate in reversed(candidates):
        try:
            payload = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _find_key(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _find_key(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find_key(value, key)
            if found is not None:
                return found
    return None


def _render_message(message: Any, output: TextIO) -> None:
    if isinstance(message, AIMessage):
        for line in _assistant_lines(message.content):
            output.write(f"[agent] {line}\n")
        for tool_call in message.tool_calls:
            name = tool_call.get("name")
            if isinstance(name, str):
                output.write(f"[tool] {name}\n")
        return
    if not isinstance(message, ToolMessage):
        return
    name = message.name or "game_tool"
    status = message.status or "success"
    summary = [f"[result] tool={name}", f"status={status}"]
    payload = _json_payload(message.content)
    if payload is not None:
        public_status = _find_key(payload, "status")
        observation_id = _find_key(payload, "observation_id")
        outcome = _find_key(payload, "outcome")
        reason = _find_key(payload, "reason")
        if isinstance(public_status, str):
            summary.append(f"public_status={public_status}")
        if type(observation_id) is int:
            summary.append(f"observation_id={observation_id}")
        if outcome in {"success", "failure"}:
            summary.append(f"game_over={outcome}")
            if isinstance(reason, str):
                summary.append(f"reason={reason}")
    output.write(" ".join(summary) + "\n")


def render_event(event: Any, *, output: TextIO = sys.stdout) -> None:
    """Render a bounded public summary without raw payloads or image bytes."""
    if not isinstance(event, dict):
        return
    for update in event.values():
        if not isinstance(update, dict):
            continue
        messages = update.get("messages", [])
        if not isinstance(messages, list):
            continue
        for message in messages:
            _render_message(message, output)
    output.flush()
