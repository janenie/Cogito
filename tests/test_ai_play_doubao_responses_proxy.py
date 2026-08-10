import copy

import pytest

from tools.ai_play_doubao_responses_proxy import (
    ProxySettings,
    RequestTransformError,
    SseTransformError,
    transform_sse_chunks,
    transform_request,
)


def _namespace_tool(*names):
    return {
        "type": "namespace",
        "name": "mcp__cogito_ai_play",
        "description": "AI Play tools",
        "tools": [
            {
                "type": "function",
                "name": name,
                "description": f"{name} description",
                "parameters": {"type": "object", "properties": {}},
                "strict": False,
            }
            for name in names
        ],
    }


def _request():
    return {
        "model": "doubao-seed-2-1-pro-260628",
        "input": [{"role": "user", "content": "play"}],
        "reasoning": {"summary": "auto"},
        "include": ["reasoning.encrypted_content"],
        "client_metadata": {"origin": "codex"},
        "parallel_tool_calls": True,
        "tools": [
            {
                "type": "function",
                "name": "update_plan",
                "parameters": {"type": "object"},
            },
            _namespace_tool("briefing", "observe", "act"),
        ],
        "stream": True,
        "store": False,
        "prompt_cache_key": "cache-key",
    }


def test_transform_request_removes_codex_extensions_and_filters_tools():
    original = _request()
    settings = ProxySettings(
        model="doubao-seed-2-1-pro-260628",
        enabled_tools=("briefing", "observe", "act"),
    )

    transformed = transform_request(original, settings)

    assert original == _request()
    assert "reasoning" not in transformed.payload
    assert "include" not in transformed.payload
    assert "client_metadata" not in transformed.payload
    assert transformed.payload["parallel_tool_calls"] is False
    assert transformed.payload["max_output_tokens"] == 8192
    assert transformed.payload["prompt_cache_key"] == "cache-key"
    assert [tool["name"] for tool in transformed.payload["tools"]] == [
        "mcp__cogito_ai_play__briefing",
        "mcp__cogito_ai_play__observe",
        "mcp__cogito_ai_play__act",
    ]
    assert all(tool["type"] == "function" for tool in transformed.payload["tools"])
    assert transformed.aliases == {
        "mcp__cogito_ai_play__briefing": "mcp__cogito_ai_play__briefing",
        "mcp__cogito_ai_play__observe": "mcp__cogito_ai_play__observe",
        "mcp__cogito_ai_play__act": "mcp__cogito_ai_play__act",
    }


def test_transform_request_preserves_other_include_values():
    payload = _request()
    payload["include"] = ["reasoning.encrypted_content", "safe.value"]

    transformed = transform_request(
        payload,
        ProxySettings(
            model="doubao-seed-2-1-pro-260628",
            enabled_tools=("briefing", "observe", "act"),
        ),
    )

    assert transformed.payload["include"] == ["safe.value"]


def test_transform_request_uses_explicit_output_limit():
    transformed = transform_request(
        _request(),
        ProxySettings(
            model="doubao-seed-2-1-pro-260628",
            enabled_tools=("briefing", "observe", "act"),
            max_output_tokens=12000,
        ),
    )

    assert transformed.payload["max_output_tokens"] == 12000


@pytest.mark.parametrize("value", [0, 32769, True, 1.5])
def test_proxy_settings_rejects_invalid_output_limit(value):
    with pytest.raises(ValueError, match="max_output_tokens"):
        ProxySettings(
            model="doubao-seed-2-1-pro-260628",
            enabled_tools=("briefing",),
            max_output_tokens=value,
        )


def test_transform_request_rejects_wrong_model():
    payload = _request()
    payload["model"] = "different-model"

    with pytest.raises(RequestTransformError, match="model"):
        transform_request(
            payload,
            ProxySettings(
                model="doubao-seed-2-1-pro-260628",
                enabled_tools=("briefing",),
            ),
        )


@pytest.mark.parametrize(
    "tools",
    [
        [],
        [_namespace_tool("briefing") | {"name": "other_namespace"}],
        [_namespace_tool("briefing") | {"tools": "invalid"}],
        [_namespace_tool("briefing") | {"tools": [{"type": "namespace"}]}],
    ],
)
def test_transform_request_rejects_missing_or_malformed_ai_play_namespace(tools):
    payload = _request()
    payload["tools"] = tools

    with pytest.raises(RequestTransformError, match="namespace"):
        transform_request(
            payload,
            ProxySettings(
                model="doubao-seed-2-1-pro-260628",
                enabled_tools=("briefing",),
            ),
        )


def test_transform_request_requires_complete_enabled_tool_surface():
    payload = _request()
    payload["tools"] = [_namespace_tool("briefing", "observe")]

    with pytest.raises(RequestTransformError, match="act"):
        transform_request(
            payload,
            ProxySettings(
                model="doubao-seed-2-1-pro-260628",
                enabled_tools=("briefing", "observe", "act"),
            ),
        )


def test_transform_request_rejects_duplicate_aliases():
    payload = _request()
    namespace = _namespace_tool("briefing", "briefing")
    payload["tools"] = [copy.deepcopy(namespace)]

    with pytest.raises(RequestTransformError, match="duplicate"):
        transform_request(
            payload,
            ProxySettings(
                model="doubao-seed-2-1-pro-260628",
                enabled_tools=("briefing",),
            ),
        )


def _sse(event_type, payload):
    import json

    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
    ).encode()


def test_sse_transform_handles_split_frames_and_nested_function_calls():
    alias = "mcp__cogito_ai_play__briefing"
    added = _sse(
        "response.output_item.added",
        {
            "type": "response.output_item.added",
            "item": {"type": "function_call", "name": alias, "arguments": "{}"},
        },
    )
    completed = _sse(
        "response.completed",
        {
            "type": "response.completed",
            "response": {
                "output": [
                    {"type": "reasoning", "summary": []},
                    {"type": "function_call", "name": alias, "arguments": "{}"},
                ]
            },
        },
    )
    payload = b": keepalive\n\n" + added + completed
    chunks = [payload[:7], payload[7:31], payload[31:93], payload[93:]]

    output = b"".join(
        transform_sse_chunks(chunks, {alias: alias})
    )

    assert b": keepalive\n\n" in output
    assert output.count(alias.encode()) == 2
    assert b"event: response.completed" in output


def test_sse_transform_parses_multiline_data():
    frame = (
        b"event: response.completed\n"
        b'data: {"type":"response.completed",\n'
        b'data: "response":{"output":[]}}\n\n'
    )

    output = b"".join(transform_sse_chunks([frame], {}))

    assert b'"type":"response.completed"' in output


def test_sse_transform_passes_reasoning_and_text_frames():
    reasoning = _sse(
        "response.reasoning_summary_text.delta",
        {"type": "response.reasoning_summary_text.delta", "delta": "plan"},
    )
    text = _sse(
        "response.output_text.delta",
        {"type": "response.output_text.delta", "delta": "hello"},
    )
    completed = _sse(
        "response.completed",
        {"type": "response.completed", "response": {"output": []}},
    )

    output = b"".join(transform_sse_chunks([reasoning, text, completed], {}))

    assert b"plan" in output
    assert b"hello" in output


def test_sse_transform_accepts_response_failed_as_terminal():
    failed = _sse(
        "response.failed",
        {"type": "response.failed", "response": {"error": {"code": "bad"}}},
    )

    output = b"".join(transform_sse_chunks([failed], {}))

    assert b"response.failed" in output


@pytest.mark.parametrize(
    ("chunks", "message"),
    [
        ([b"data: not-json\n\n"], "JSON"),
        ([b"data: \xff\n\n"], "UTF-8"),
        ([b'data: {"type":"response.completed"}'], "incomplete"),
        (
            [_sse("response.output_text.delta", {"type": "response.output_text.delta"})],
            "terminal",
        ),
    ],
)
def test_sse_transform_rejects_malformed_or_interrupted_streams(chunks, message):
    with pytest.raises(SseTransformError, match=message):
        list(transform_sse_chunks(chunks, {}))


def test_sse_transform_rejects_unknown_function_alias_before_forwarding_frame():
    unknown = _sse(
        "response.output_item.added",
        {
            "type": "response.output_item.added",
            "item": {
                "type": "function_call",
                "name": "mcp__cogito_ai_play__unknown",
                "arguments": "{}",
            },
        },
    )
    completed = _sse(
        "response.completed",
        {"type": "response.completed", "response": {"output": []}},
    )
    iterator = transform_sse_chunks([unknown, completed], {})

    with pytest.raises(SseTransformError, match="unknown function alias"):
        next(iterator)
