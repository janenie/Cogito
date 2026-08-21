import json

import httpx2
import pytest
from deepagents.middleware.summarization import (
    compute_summarization_defaults,
)
from langchain_core.messages import AIMessage, ToolMessage

from tools_langgraph_deepagents.credentials import YibuCredentials
from tools_langgraph_deepagents.model import build_yibu_chat_model


@pytest.mark.asyncio
async def test_model_uses_chat_completions_with_serial_tools():
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": "gemini-3.6-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "ready",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(respond)
    ) as client:
        model = build_yibu_chat_model(
            YibuCredentials("secret-for-test", "https://yibu.example/v1"),
            model="gemini-3.6-flash",
            timeout_seconds=30,
            max_retries=0,
            max_output_tokens=4096,
            context_window_tokens=32768,
            http_async_client=client,
        )
        response = await model.ainvoke("hello")

    assert response.content == "ready"
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/chat/completions"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "gemini-3.6-flash"
    assert payload["parallel_tool_calls"] is False
    assert payload["max_completion_tokens"] == 4096


def test_model_explicitly_disables_responses_api():
    model = build_yibu_chat_model(
        YibuCredentials("secret-for-test", "https://yibu.example/v1"),
        model="gemini-3.6-flash",
        timeout_seconds=30,
        max_retries=0,
        max_output_tokens=4096,
        context_window_tokens=32768,
    )

    assert model.use_responses_api is False
    assert model.disable_streaming is True
    assert model.http_socket_options == ()
    assert model.profile == {"max_input_tokens": 32768}
    assert compute_summarization_defaults(model)["trigger"] == (
        "fraction",
        0.85,
    )


@pytest.mark.asyncio
async def test_model_serializes_mcp_images_in_chat_tool_messages():
    payloads: list[dict] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        payloads.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "chatcmpl-image",
                "object": "chat.completion",
                "created": 0,
                "model": "gemini-3.6-flash",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "seen",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(respond)
    ) as client:
        model = build_yibu_chat_model(
            YibuCredentials("secret-for-test", "https://yibu.example/v1"),
            model="gemini-3.6-flash",
            timeout_seconds=30,
            max_retries=0,
            max_output_tokens=4096,
            context_window_tokens=32768,
            http_async_client=client,
        )
        await model.ainvoke(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "observe",
                            "args": {},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(
                    content=[
                        {
                            "type": "image",
                            "base64": "ZmFrZQ==",
                            "mime_type": "image/jpeg",
                        },
                        {"type": "text", "text": '{"status":"ready"}'},
                    ],
                    tool_call_id="call-1",
                    name="observe",
                ),
            ]
        )

    tool_message = payloads[0]["messages"][1]
    assert tool_message["role"] == "tool"
    assert tool_message["content"][0] == {
        "type": "image_url",
        "image_url": {
            "url": "data:image/jpeg;base64,ZmFrZQ==",
        },
    }
