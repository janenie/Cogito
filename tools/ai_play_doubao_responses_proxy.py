#!/usr/bin/env python3
"""Translate Codex Responses requests for the Yibu/Doubao compatibility API."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import re
from typing import Any, Iterable, Iterator, Mapping


AI_PLAY_NAMESPACE = "mcp__cogito_ai_play"
MAX_PROVIDER_OUTPUT_TOKENS = 32768


class RequestTransformError(ValueError):
    """The Codex request cannot be translated without widening permissions."""


class SseTransformError(ValueError):
    """The upstream event stream cannot be safely forwarded to Codex."""


@dataclass(frozen=True)
class ProxySettings:
    model: str
    enabled_tools: tuple[str, ...]
    max_output_tokens: int = 8192
    namespace: str = AI_PLAY_NAMESPACE

    def __post_init__(self) -> None:
        if not isinstance(self.max_output_tokens, int) or isinstance(
            self.max_output_tokens, bool
        ):
            raise ValueError("max_output_tokens must be an integer")
        if not 1 <= self.max_output_tokens <= MAX_PROVIDER_OUTPUT_TOKENS:
            raise ValueError(
                "max_output_tokens must be between 1 and %d"
                % MAX_PROVIDER_OUTPUT_TOKENS
            )


@dataclass(frozen=True)
class TransformedRequest:
    payload: dict[str, Any]
    aliases: dict[str, str]


def _flat_tool_alias(namespace: str, tool_name: str) -> str:
    return f"{namespace}__{tool_name}"


def _find_namespace_tool(
    tools: object,
    namespace: str,
) -> Mapping[str, Any]:
    if not isinstance(tools, list):
        raise RequestTransformError("tools must contain the AI Play namespace")
    matches = [
        tool
        for tool in tools
        if isinstance(tool, dict)
        and tool.get("type") == "namespace"
        and tool.get("name") == namespace
    ]
    if len(matches) != 1:
        raise RequestTransformError(
            "request must contain exactly one AI Play namespace"
        )
    return matches[0]


def _flatten_enabled_tools(
    namespace_tool: Mapping[str, Any],
    settings: ProxySettings,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    nested = namespace_tool.get("tools")
    if not isinstance(nested, list):
        raise RequestTransformError("AI Play namespace tools must be a list")

    enabled = set(settings.enabled_tools)
    found: set[str] = set()
    flattened: list[dict[str, Any]] = []
    aliases: dict[str, str] = {}
    for raw_tool in nested:
        if not isinstance(raw_tool, dict) or raw_tool.get("type") != "function":
            raise RequestTransformError(
                "AI Play namespace may contain only function tools"
            )
        name = raw_tool.get("name")
        if not isinstance(name, str) or not name:
            raise RequestTransformError(
                "AI Play namespace function names must be non-empty strings"
            )
        if name not in enabled:
            continue
        alias = _flat_tool_alias(settings.namespace, name)
        if alias in aliases:
            raise RequestTransformError(f"duplicate tool alias: {alias}")
        tool = deepcopy(raw_tool)
        tool["name"] = alias
        flattened.append(tool)
        aliases[alias] = alias
        found.add(name)

    missing = [name for name in settings.enabled_tools if name not in found]
    if missing:
        raise RequestTransformError(
            "AI Play namespace is missing enabled tools: %s"
            % ", ".join(missing)
        )
    return flattened, aliases


def transform_request(
    payload: Mapping[str, Any],
    settings: ProxySettings,
) -> TransformedRequest:
    """Return a provider-compatible copy of one Codex Responses request."""
    if not isinstance(payload, Mapping):
        raise RequestTransformError("request body must be a JSON object")
    if payload.get("model") != settings.model:
        raise RequestTransformError("request model does not match proxy model")

    transformed = deepcopy(dict(payload))
    transformed.pop("reasoning", None)
    transformed.pop("client_metadata", None)

    include = transformed.get("include")
    if include is not None:
        if not isinstance(include, list):
            raise RequestTransformError("include must be a list")
        include = [
            item for item in include if item != "reasoning.encrypted_content"
        ]
        if include:
            transformed["include"] = include
        else:
            transformed.pop("include", None)

    namespace_tool = _find_namespace_tool(
        transformed.get("tools"),
        settings.namespace,
    )
    tools, aliases = _flatten_enabled_tools(namespace_tool, settings)
    transformed["tools"] = tools
    transformed["parallel_tool_calls"] = False
    transformed["max_output_tokens"] = settings.max_output_tokens
    return TransformedRequest(payload=transformed, aliases=aliases)


_SSE_FRAME_END = re.compile(br"\r?\n\r?\n")


def _rewrite_function_calls(value: Any, aliases: Mapping[str, str]) -> None:
    if isinstance(value, list):
        for item in value:
            _rewrite_function_calls(item, aliases)
        return
    if not isinstance(value, dict):
        return
    if value.get("type") == "function_call":
        name = value.get("name")
        if not isinstance(name, str) or name not in aliases:
            raise SseTransformError(f"unknown function alias: {name!r}")
        value["name"] = aliases[name]
    for item in value.values():
        _rewrite_function_calls(item, aliases)


def _transform_sse_frame(
    raw_frame: bytes,
    aliases: Mapping[str, str],
) -> tuple[bytes, str | None]:
    try:
        text = raw_frame.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SseTransformError("SSE frame is not valid UTF-8") from error
    lines = text.splitlines()
    data_lines: list[str] = []
    prefix_lines: list[str] = []
    for line in lines:
        if line.startswith("data:"):
            data = line[5:]
            if data.startswith(" "):
                data = data[1:]
            data_lines.append(data)
        else:
            prefix_lines.append(line)
    if not data_lines:
        return (text + "\n\n").encode("utf-8"), None
    try:
        payload = json.loads("\n".join(data_lines))
    except json.JSONDecodeError as error:
        raise SseTransformError("SSE data is not valid JSON") from error
    _rewrite_function_calls(payload, aliases)
    event_type = payload.get("type") if isinstance(payload, dict) else None
    output_lines = prefix_lines + [
        "data: " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    ]
    return ("\n".join(output_lines) + "\n\n").encode("utf-8"), event_type


def transform_sse_chunks(
    chunks: Iterable[bytes],
    aliases: Mapping[str, str],
) -> Iterator[bytes]:
    """Frame, validate, and translate one streaming Responses SSE body."""
    buffer = b""
    terminal = False
    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise SseTransformError("SSE chunks must be bytes")
        buffer += chunk
        while True:
            match = _SSE_FRAME_END.search(buffer)
            if match is None:
                break
            raw_frame = buffer[: match.start()]
            buffer = buffer[match.end() :]
            if not raw_frame:
                continue
            output, event_type = _transform_sse_frame(raw_frame, aliases)
            if terminal:
                raise SseTransformError("SSE data followed a terminal event")
            if event_type in ("response.completed", "response.failed"):
                terminal = True
            yield output
    if buffer:
        raise SseTransformError("incomplete SSE frame at upstream disconnect")
    if not terminal:
        raise SseTransformError("SSE stream ended without a terminal event")
