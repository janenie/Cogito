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
    protected_message_ids: frozenset[str] = frozenset(),
) -> list[AnyMessage]:
    """Keep the newest image-bearing messages and every text block."""
    if limit < 0:
        raise ValueError("image limit must be nonnegative")
    remaining = limit
    reversed_messages: list[AnyMessage] = []
    for message in reversed(messages):
        protected = getattr(message, "id", None) in protected_message_ids
        if not isinstance(message.content, list):
            reversed_messages.append(message)
            continue
        has_images = any(
            isinstance(block, dict)
            and block.get("type") in IMAGE_TYPES
            for block in message.content
        )
        keep_images = protected or not has_images or remaining > 0
        if has_images and keep_images and not protected:
            remaining -= 1
        kept = [
            block
            for block in message.content
            if not (
                isinstance(block, dict)
                and block.get("type") in IMAGE_TYPES
                and not keep_images
            )
        ]
        reversed_messages.append(message.model_copy(update={"content": kept}))
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


class CaptionImageMiddleware(AgentMiddleware):
    """Generate batched captions before trimming historical images."""

    def __init__(
        self,
        pipeline: Any,
        *,
        image_limit: int,
        summarizer: Any | None = None,
    ) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.image_limit = image_limit
        self.summarizer = summarizer

    @property
    def name(self) -> str:
        return "SummarizationMiddleware"

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        prepared = await self.pipeline.prepare(request.messages)
        protected = frozenset(
            self.pipeline.protected_message_ids(prepared)
        )
        limited_request = request.override(
            messages=trim_images(
                prepared,
                limit=self.image_limit,
                protected_message_ids=protected,
            )
        )
        if self.summarizer is not None:
            return await self.summarizer.awrap_model_call(
                limited_request,
                handler,
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
