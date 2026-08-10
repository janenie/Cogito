import importlib.util
import http.client
import json
import sys
import threading
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROXY_PATH = REPO_ROOT / "tools" / "ai_play_responses_namespace_proxy.py"


def load_proxy():
    spec = importlib.util.spec_from_file_location(
        "tools.ai_play_responses_namespace_proxy",
        PROXY_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_rewrite_adds_namespace_to_allowed_plain_function_call():
    proxy = load_proxy()
    event = {
        "type": "response.output_item.done",
        "item": {
            "type": "function_call",
            "name": "briefing",
            "arguments": "{}",
        },
    }

    rewritten = proxy.rewrite_response_event(
        event,
        namespace="mcp__cogito_ai_play",
        allowed_tools={"briefing"},
    )

    assert rewritten["item"]["namespace"] == "mcp__cogito_ai_play"


def test_rewrite_preserves_builtin_and_existing_namespace_calls():
    proxy = load_proxy()
    event = {
        "output": [
            {"type": "function_call", "name": "update_plan"},
            {
                "type": "function_call",
                "name": "briefing",
                "namespace": "already_namespaced",
            },
        ]
    }

    rewritten = proxy.rewrite_response_event(
        event,
        namespace="mcp__cogito_ai_play",
        allowed_tools={"briefing"},
    )

    assert "namespace" not in rewritten["output"][0]
    assert rewritten["output"][1]["namespace"] == "already_namespaced"


def test_rewrite_sse_line_preserves_framing_and_done_marker():
    proxy = load_proxy()
    event = {
        "type": "response.output_item.added",
        "item": {"type": "function_call", "name": "observe"},
    }

    rewritten = proxy.rewrite_sse_line(
        b"data: " + json.dumps(event).encode("utf-8"),
        namespace="mcp__cogito_ai_play",
        allowed_tools={"observe"},
    )

    payload = json.loads(rewritten.removeprefix(b"data: "))
    assert payload["item"]["namespace"] == "mcp__cogito_ai_play"
    assert proxy.rewrite_sse_line(
        b"data: [DONE]",
        namespace="mcp__cogito_ai_play",
        allowed_tools={"observe"},
    ) == b"data: [DONE]"


def test_proxy_accepts_only_post_v1_responses():
    proxy = load_proxy()

    assert proxy.is_allowed_request("POST", "/v1/responses")
    assert not proxy.is_allowed_request("GET", "/v1/responses")
    assert not proxy.is_allowed_request("POST", "/v1/models")
    assert not proxy.is_allowed_request("POST", "/v1/responses?debug=1")


def test_forward_headers_keep_auth_without_hop_by_hop_headers():
    proxy = load_proxy()

    headers = proxy.forward_request_headers(
        {
            "Authorization": "Bearer secret",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Connection": "keep-alive",
            "Host": "127.0.0.1:8767",
            "Content-Length": "123",
        }
    )

    assert headers["Authorization"] == "Bearer secret"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "text/event-stream"
    assert "Connection" not in headers
    assert "Host" not in headers
    assert "Content-Length" not in headers


def test_upstream_url_requires_https_v1_and_appends_responses():
    proxy = load_proxy()

    assert proxy.build_upstream_responses_url("https://yibuapi.com/v1") == (
        "https://yibuapi.com/v1/responses"
    )

    for value in (
        "http://yibuapi.com/v1",
        "https://user@yibuapi.com/v1",
        "https://yibuapi.com/v2",
        "https://yibuapi.com/v1?debug=1",
    ):
        try:
            proxy.build_upstream_responses_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected unsafe upstream rejection: {value}")


def test_parse_args_requires_loopback_and_nonempty_tool_whitelist():
    proxy = load_proxy()

    args = proxy.parse_args(
        [
            "--host",
            "127.0.0.1",
            "--port",
            "8767",
            "--upstream-base-url",
            "https://yibuapi.com/v1",
            "--namespace",
            "mcp__cogito_ai_play",
            "--allowed-tool",
            "briefing",
        ]
    )
    assert args.host == "127.0.0.1"
    assert args.allowed_tool == ["briefing"]

    for argv in (
        ["--host", "0.0.0.0", "--allowed-tool", "briefing"],
        ["--host", "127.0.0.1"],
    ):
        try:
            proxy.parse_args(argv)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"expected argument rejection: {argv}")


def test_proxy_returns_generic_502_when_upstream_connection_fails(monkeypatch):
    proxy = load_proxy()

    class FailingClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            raise proxy.httpx.ConnectError("sensitive upstream detail")

    monkeypatch.setattr(proxy.httpx, "Client", FailingClient)
    handler = proxy._handler_type(
        "https://yibuapi.com/v1/responses",
        "mcp__cogito_ai_play",
        frozenset({"briefing"}),
    )
    server = proxy.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=2,
        )
        connection.request(
            "POST",
            "/v1/responses",
            body=b"{}",
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert response.status == 502
    assert body == b'{"error": "upstream request failed"}'
    assert b"sensitive" not in body
