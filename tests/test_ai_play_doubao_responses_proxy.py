import copy
from contextlib import contextmanager
import http.client
import json

import httpx
import pytest

from tools.ai_play_doubao_responses_proxy import (
    MAX_ERROR_BODY_BYTES,
    MAX_REQUEST_BODY_BYTES,
    DoubaoProxyServer,
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
        "mcp__cogito_ai_play__briefing": "briefing",
        "mcp__cogito_ai_play__observe": "observe",
        "mcp__cogito_ai_play__act": "act",
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
        transform_sse_chunks(chunks, {alias: "briefing"})
    )

    assert b": keepalive\n\n" in output
    assert output.count(b'"name":"briefing"') == 2
    assert output.count(b'"namespace":"mcp__cogito_ai_play"') == 2
    assert alias.encode() not in output
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


class _FakeResponse:
    def __init__(self, status_code=200, chunks=(), headers=None):
        self.status_code = status_code
        self._chunks = list(chunks)
        self.headers = headers or {"content-type": "text/event-stream"}
        self.closed = False

    def iter_bytes(self):
        yield from self._chunks

    def close(self):
        self.closed = True


class _FakeUpstream:
    def __init__(self, response):
        self.response = response
        self.calls = []

    @contextmanager
    def __call__(self, url, headers, content, timeout):
        self.calls.append(
            {"url": url, "headers": dict(headers), "content": content, "timeout": timeout}
        )
        try:
            yield self.response
        finally:
            self.response.close()


def _proxy(fake_upstream, logs=None):
    return DoubaoProxyServer(
        settings=ProxySettings(
            model="doubao-seed-2-1-pro-260628",
            enabled_tools=("briefing", "observe", "act"),
        ),
        upstream_base_url="https://yibuapi.com/v1",
        upstream_token="real-yibu-secret",
        proxy_token="local-proxy-secret",
        upstream_factory=fake_upstream,
        event_logger=(logs.append if logs is not None else None),
    )


def _completed_sse():
    return _sse(
        "response.completed",
        {"type": "response.completed", "response": {"output": []}},
    )


def test_http_proxy_health_and_fail_closed_routes():
    upstream = _FakeUpstream(_FakeResponse(chunks=[_completed_sse()]))
    with _proxy(upstream) as server:
        assert server.host == "127.0.0.1"
        health = httpx.get(server.base_url.removesuffix("/v1") + "/healthz")
        wrong_path = httpx.post(server.base_url + "/other")
        wrong_method = httpx.get(server.base_url + "/responses")
        unauthenticated = httpx.post(server.base_url + "/responses", json=_request())

    assert health.status_code == 200
    assert wrong_path.status_code == 404
    assert wrong_method.status_code == 405
    assert unauthenticated.status_code == 401
    assert upstream.calls == []


def test_http_proxy_replaces_auth_transforms_and_streams_without_secret_logs():
    logs = []
    upstream = _FakeUpstream(
        _FakeResponse(
            chunks=[_completed_sse()],
            headers={
                "content-type": "text/event-stream",
                "x-request-id": "upstream-request",
                "set-cookie": "must-not-forward",
            },
        )
    )
    request = _request()
    request["input"][0]["content"] = "private prompt text"

    with _proxy(upstream, logs) as server:
        response = httpx.post(
            server.base_url + "/responses",
            headers={"authorization": "Bearer local-proxy-secret"},
            json=request,
        )

    assert response.status_code == 200
    assert "response.completed" in response.text
    assert response.headers["x-request-id"] == "upstream-request"
    assert "set-cookie" not in response.headers
    assert len(upstream.calls) == 1
    call = upstream.calls[0]
    assert call["url"] == "https://yibuapi.com/v1/responses"
    assert call["headers"]["authorization"] == "Bearer real-yibu-secret"
    assert "local-proxy-secret" not in repr(call)
    sent = json.loads(call["content"])
    assert "reasoning" not in sent
    assert sent["max_output_tokens"] == 8192
    assert [tool["name"] for tool in sent["tools"]] == [
        "mcp__cogito_ai_play__briefing",
        "mcp__cogito_ai_play__observe",
        "mcp__cogito_ai_play__act",
    ]
    logged = repr(logs)
    assert "private prompt text" not in logged
    assert "real-yibu-secret" not in logged
    assert "local-proxy-secret" not in logged
    assert upstream.response.closed


def test_http_proxy_rejects_oversized_body_without_upstream_call():
    upstream = _FakeUpstream(_FakeResponse(chunks=[_completed_sse()]))
    with _proxy(upstream) as server:
        connection = http.client.HTTPConnection(server.host, server.port, timeout=5)
        connection.putrequest("POST", "/v1/responses")
        connection.putheader("Authorization", "Bearer local-proxy-secret")
        connection.putheader("Content-Length", str(MAX_REQUEST_BODY_BYTES + 1))
        connection.endheaders()
        response = connection.getresponse()
        response.read()
        connection.close()

    assert response.status == 413
    assert upstream.calls == []


def test_http_proxy_bounds_and_forwards_upstream_error_without_retry():
    body = b"x" * (MAX_ERROR_BODY_BYTES + 100)
    logs = []
    upstream = _FakeUpstream(
        _FakeResponse(
            status_code=429,
            chunks=[body],
            headers={"content-type": "application/json", "x-request-id": "rate-id"},
        )
    )

    with _proxy(upstream, logs) as server:
        response = httpx.post(
            server.base_url + "/responses",
            headers={"authorization": "Bearer local-proxy-secret"},
            json=_request(),
        )

    assert response.status_code == 429
    assert len(response.content) == MAX_ERROR_BODY_BYTES
    assert response.headers["x-request-id"] == "rate-id"
    assert len(upstream.calls) == 1
    assert len(logs) == 1
    assert logs[0]["event"] == "request_completed"
    assert logs[0]["status"] == 429
    assert logs[0]["request_bytes"] > 0
    assert logs[0]["response_bytes"] == MAX_ERROR_BODY_BYTES
    assert logs[0]["request_id"] == "rate-id"


def test_http_proxy_does_not_turn_interrupted_sse_into_successful_completion():
    upstream = _FakeUpstream(
        _FakeResponse(
            chunks=[
                _sse(
                    "response.output_text.delta",
                    {"type": "response.output_text.delta", "delta": "partial"},
                )
            ]
        )
    )

    with _proxy(upstream) as server:
        with pytest.raises(httpx.RemoteProtocolError):
            httpx.post(
                server.base_url + "/responses",
                headers={"authorization": "Bearer local-proxy-secret"},
                json=_request(),
            )


def test_http_proxy_reports_upstream_timeout_without_retry():
    calls = []

    @contextmanager
    def timeout_upstream(url, headers, content, timeout):
        calls.append((url, headers, content, timeout))
        raise httpx.ReadTimeout("slow upstream")
        yield

    logs = []
    with _proxy(timeout_upstream, logs) as server:
        response = httpx.post(
            server.base_url + "/responses",
            headers={"authorization": "Bearer local-proxy-secret"},
            json=_request(),
        )

    assert response.status_code == 502
    assert len(calls) == 1
    assert any(event["error_type"] == "ReadTimeout" for event in logs)
