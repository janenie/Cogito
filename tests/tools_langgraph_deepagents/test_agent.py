import asyncio
from collections.abc import Sequence
from typing import Any

import pytest
from langchain.agents.middleware import ModelRequest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from pydantic import PrivateAttr

from tools_langgraph_deepagents.agent import build_game_agent
from tools_langgraph_deepagents.middleware import (
    ImageLimitMiddleware,
    SerialGameTools,
    trim_images,
)
from tools_langgraph_deepagents.prompt import build_system_prompt


def test_trim_images_keeps_latest_ten_and_all_text():
    messages = [
        ToolMessage(
            content=[
                {"type": "text", "text": f"observation-{index}"},
                {
                    "type": "image",
                    "base64": str(index),
                    "mime_type": "image/jpeg",
                },
            ],
            tool_call_id=f"call-{index}",
        )
        for index in range(12)
    ]

    trimmed = trim_images(messages, limit=10)
    images = [
        block["base64"]
        for message in trimmed
        for block in message.content
        if isinstance(block, dict) and block.get("type") == "image"
    ]

    assert images == [str(index) for index in range(2, 12)]
    assert [message.content[0]["text"] for message in trimmed] == [
        f"observation-{index}" for index in range(12)
    ]


@pytest.mark.asyncio
async def test_image_limit_applies_immediately_before_model_call():
    messages = [
        ToolMessage(
            content=[
                {"type": "text", "text": f"caption-{index}"},
                {
                    "type": "image",
                    "base64": str(index),
                    "mime_type": "image/jpeg",
                },
            ],
            tool_call_id=f"call-{index}",
        )
        for index in range(12)
    ]
    model = RecordingFakeModel(
        messages=iter([AIMessage(content="done")]),
        profile={"max_input_tokens": 100_000},
    )
    request = ModelRequest(model=model, messages=messages)
    captured: list[ModelRequest] = []

    async def handler(limited_request: ModelRequest):
        captured.append(limited_request)
        return "response"

    result = await ImageLimitMiddleware(10).awrap_model_call(
        request,
        handler,
    )

    assert result == "response"
    assert sum(
        block.get("type") == "image"
        for message in captured[0].messages
        for block in message.content
        if isinstance(block, dict)
    ) == 10


@pytest.mark.asyncio
async def test_serial_middleware_never_overlaps_game_tools():
    middleware = SerialGameTools({"act"})
    active = 0
    maximum = 0

    async def handler(_request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        active -= 1
        return "ok"

    request = type(
        "Request",
        (),
        {"tool_call": {"name": "act", "id": "call-1"}},
    )()
    await asyncio.gather(
        middleware.awrap_tool_call(request, handler),
        middleware.awrap_tool_call(request, handler),
    )

    assert maximum == 1


@pytest.mark.asyncio
async def test_serial_middleware_rejects_non_game_tools():
    middleware = SerialGameTools({"act"})
    called = False

    async def handler(_request):
        nonlocal called
        called = True

    request = type(
        "Request",
        (),
        {"tool_call": {"name": "ls", "id": "call-ls"}},
    )()
    result = await middleware.awrap_tool_call(request, handler)

    assert called is False
    assert isinstance(result, ToolMessage)
    assert result.status == "error"


class RecordingFakeModel(GenericFakeChatModel):
    _bound_names: list[str] = PrivateAttr(default_factory=list)

    def _get_ls_params(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "ls_provider": "openai",
            "ls_model_name": "fake-game-model",
            "ls_model_type": "chat",
        }

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable:
        self._bound_names = [
            item.name if hasattr(item, "name") else item["name"]
            for item in tools
        ]
        return self


@tool
def briefing() -> str:
    """Return the public game briefing."""
    return "briefing"


@tool
def observe() -> str:
    """Return the current public observation."""
    return "observation"


@tool
def act(observation_id: int) -> str:
    """Perform one public game action."""
    return str(observation_id)


@pytest.mark.asyncio
async def test_deep_agent_exposes_only_game_tools():
    model = RecordingFakeModel(
        messages=iter([AIMessage(content="done")]),
        profile={"max_input_tokens": 100_000},
    )
    game_tools = [briefing, observe, act]
    agent = build_game_agent(
        model=model,
        tools=game_tools,
        system_prompt=build_system_prompt(
            runs=3,
            workflow_memory_enabled=False,
        ),
        checkpointer=None,
    )

    await agent.ainvoke({"messages": [{"role": "user", "content": "start"}]})

    assert model._bound_names == ["briefing", "observe", "act"]


def test_prompt_contains_no_scenario_or_repository_answer():
    prompt = build_system_prompt(runs=3, workflow_memory_enabled=True)

    assert "3" in prompt
    assert "caption" in prompt.lower()
    assert "find_contract" not in prompt
    assert "game_script" in prompt
    assert "workflow_memory_update" in prompt
