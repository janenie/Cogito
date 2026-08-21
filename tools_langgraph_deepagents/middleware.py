from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import AnyMessage, ToolMessage


IMAGE_TYPES = frozenset({"image", "image_url", "input_image"})


def trim_images(
    messages: Sequence[AnyMessage],
    *,
    limit: int,
) -> list[AnyMessage]:
    """Keep only the newest image blocks while preserving every text block."""
    if limit < 0:
        raise ValueError("image limit must be nonnegative")
    remaining = limit
    reversed_messages: list[AnyMessage] = []
    for message in reversed(messages):
        if not isinstance(message.content, list):
            reversed_messages.append(message)
            continue
        kept_reversed: list[Any] = []
        for block in reversed(message.content):
            is_image = (
                isinstance(block, dict)
                and block.get("type") in IMAGE_TYPES
            )
            if not is_image or remaining > 0:
                kept_reversed.append(block)
                if is_image:
                    remaining -= 1
        reversed_messages.append(
            message.model_copy(
                update={"content": list(reversed(kept_reversed))}
            )
        )
    return list(reversed(reversed_messages))


class ImageLimitMiddleware(AgentMiddleware):
    def __init__(self, limit: int) -> None:
        super().__init__()
        self.limit = limit

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        limited_request = request.override(
            messages=trim_images(request.messages, limit=self.limit)
        )
        return await handler(limited_request)


class SerialGameTools(AgentMiddleware):
    """Fail closed on unknown tools and serialize every accepted call."""

    def __init__(self, allowed_names: set[str]) -> None:
        super().__init__()
        self.allowed_names = frozenset(allowed_names)
        self._lock = asyncio.Lock()

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        tool_call = request.tool_call
        name = tool_call["name"]
        if name not in self.allowed_names:
            return ToolMessage(
                content=(
                    "tool is not available to the game player: " + name
                ),
                tool_call_id=tool_call.get("id", "unavailable-tool"),
                status="error",
            )
        async with self._lock:
            return await handler(request)
