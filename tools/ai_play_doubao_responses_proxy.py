#!/usr/bin/env python3
"""Translate Codex Responses requests for the Yibu/Doubao compatibility API."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


AI_PLAY_NAMESPACE = "mcp__cogito_ai_play"
MAX_PROVIDER_OUTPUT_TOKENS = 32768


class RequestTransformError(ValueError):
    """The Codex request cannot be translated without widening permissions."""


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
