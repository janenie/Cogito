import importlib.util
import base64
import hashlib
import http.client
import json
import os
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


def namespace_request():
    return {
        "tools": [
            {"type": "function", "name": "plain", "parameters": {}},
            {
                "type": "namespace",
                "name": "mcp__cogito_ai_play",
                "tools": [
                    {"type": "function", "name": "briefing", "parameters": {}},
                    {"type": "function", "name": "observe", "parameters": {}},
                ],
            },
        ],
        "input": [
            {
                "type": "function_call",
                "name": "briefing",
                "namespace": "mcp__cogito_ai_play",
                "arguments": "{}",
            }
        ],
        "tool_choice": {"type": "namespace", "name": "mcp__cogito_ai_play"},
    }


def test_flatten_namespace_tools_rewrites_request_and_returns_reverse_map():
    proxy = load_proxy()
    request = namespace_request()

    reverse_map = proxy.transform_request_namespaces(
        request,
        namespace="mcp__cogito_ai_play",
        allowed_tools=frozenset({"briefing", "observe"}),
    )

    assert [tool["name"] for tool in request["tools"]] == [
        "plain",
        "mcp__cogito_ai_play__briefing",
        "mcp__cogito_ai_play__observe",
    ]
    assert request["input"][0]["name"] == "mcp__cogito_ai_play__briefing"
    assert "namespace" not in request["input"][0]
    assert request["tool_choice"] == "auto"
    assert reverse_map["mcp__cogito_ai_play__observe"] == (
        proxy.NamespacedToolName("mcp__cogito_ai_play", "observe")
    )


def test_flatten_preserves_request_without_tools_field():
    proxy = load_proxy()
    request = {"model": "fixture", "input": "hello"}

    reverse_map = proxy.transform_request_namespaces(
        request,
        namespace="mcp__cogito_ai_play",
        allowed_tools=frozenset({"briefing"}),
    )

    assert reverse_map == {}
    assert request == {"model": "fixture", "input": "hello"}


def test_flatten_overrides_provider_output_limit_when_configured():
    proxy = load_proxy()
    request = namespace_request()
    request["max_output_tokens"] = 8192

    proxy.transform_request_namespaces(
        request,
        namespace="mcp__cogito_ai_play",
        allowed_tools=frozenset({"briefing", "observe"}),
        max_output_tokens=4096,
    )

    assert request["max_output_tokens"] == 4096


def test_flatten_rejects_unapproved_namespace_child():
    proxy = load_proxy()
    request = namespace_request()
    request["tools"][1]["tools"].append(
        {"type": "function", "name": "hidden", "parameters": {}}
    )

    try:
        proxy.transform_request_namespaces(
            request,
            namespace="mcp__cogito_ai_play",
            allowed_tools=frozenset({"briefing", "observe"}),
        )
    except ValueError as error:
        assert "allowed" in str(error)
    else:
        raise AssertionError("expected unapproved namespace child rejection")


def test_flatten_rejects_existing_flat_name_collision():
    proxy = load_proxy()
    request = namespace_request()
    request["tools"].insert(
        0,
        {
            "type": "function",
            "name": "mcp__cogito_ai_play__briefing",
            "parameters": {},
        },
    )

    try:
        proxy.transform_request_namespaces(
            request,
            namespace="mcp__cogito_ai_play",
            allowed_tools=frozenset({"briefing", "observe"}),
        )
    except ValueError as error:
        assert "collision" in str(error)
    else:
        raise AssertionError("expected flat-name collision rejection")


def test_flatten_rejects_two_owners_with_same_bounded_name(monkeypatch):
    proxy = load_proxy()
    request = namespace_request()
    monkeypatch.setattr(
        proxy,
        "flatten_namespace_tool_name",
        lambda _namespace, _name: "same-bounded-name",
    )

    try:
        proxy.transform_request_namespaces(
            request,
            namespace="mcp__cogito_ai_play",
            allowed_tools=frozenset({"briefing", "observe"}),
        )
    except ValueError as error:
        assert "collision" in str(error)
    else:
        raise AssertionError("expected bounded-name owner collision rejection")


def test_restore_flattened_name_in_json_response():
    proxy = load_proxy()
    event = {
        "item": {
            "type": "function_call",
            "name": "mcp__cogito_ai_play__observe",
        }
    }
    reverse_map = {
        "mcp__cogito_ai_play__observe": proxy.NamespacedToolName(
            "mcp__cogito_ai_play", "observe"
        )
    }

    proxy.rewrite_response_event(
        event,
        namespace="mcp__cogito_ai_play",
        allowed_tools={"observe"},
        restore_map=reverse_map,
    )

    assert event["item"]["name"] == "observe"
    assert event["item"]["namespace"] == "mcp__cogito_ai_play"


def test_restore_flattened_name_in_sse_but_not_unmapped_name():
    proxy = load_proxy()
    event = {
        "output": [
            {
                "type": "function_call",
                "name": "mcp__cogito_ai_play__observe",
            },
            {"type": "function_call", "name": "unmapped"},
        ]
    }
    reverse_map = {
        "mcp__cogito_ai_play__observe": proxy.NamespacedToolName(
            "mcp__cogito_ai_play", "observe"
        )
    }

    rewritten = proxy.rewrite_sse_line(
        b"data: " + json.dumps(event).encode(),
        namespace="mcp__cogito_ai_play",
        allowed_tools={"observe"},
        restore_map=reverse_map,
    )
    payload = json.loads(rewritten.removeprefix(b"data: "))

    assert payload["output"][0]["name"] == "observe"
    assert payload["output"][0]["namespace"] == "mcp__cogito_ai_play"
    assert payload["output"][1] == {"type": "function_call", "name": "unmapped"}


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


def test_rewrite_normalizes_provider_colon_qualified_mcp_tool_call():
    proxy = load_proxy()
    event = {
        "type": "response.output_item.done",
        "item": {
            "type": "function_call",
            "name": "cogito_ai_play:briefing",
            "arguments": "{}",
        },
    }

    rewritten = proxy.rewrite_response_event(
        event,
        namespace="mcp__cogito_ai_play",
        allowed_tools={"briefing"},
    )

    assert rewritten["item"]["name"] == "briefing"
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


def test_inspect_request_images_records_only_safe_metadata():
    proxy = load_proxy()
    jpeg = b"fixture-jpeg-bytes"
    png = b"fixture-png-bytes"
    jpeg_b64 = base64.b64encode(jpeg).decode("ascii")
    png_b64 = base64.b64encode(png).decode("ascii")
    request = {
        "model": "gemini-fixture",
        "previous_response_id": "response-secret",
        "store": False,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "prompt-secret"},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{jpeg_b64}",
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{png_b64}",
                    },
                ],
            }
        ],
    }

    metadata = proxy.inspect_request_images(json.dumps(request).encode("utf-8"))

    assert metadata == {
        "request_bytes": len(json.dumps(request).encode("utf-8")),
        "input_image_count": 2,
        "images": [
            {
                "ordinal": 1,
                "mime_type": "image/jpeg",
                "byte_count": len(jpeg),
                "sha256": hashlib.sha256(jpeg).hexdigest(),
            },
            {
                "ordinal": 2,
                "mime_type": "image/png",
                "byte_count": len(png),
                "sha256": hashlib.sha256(png).hexdigest(),
            },
        ],
        "has_previous_response_id": True,
        "store": False,
    }
    serialized = json.dumps(metadata)
    assert "prompt-secret" not in serialized
    assert "response-secret" not in serialized
    assert jpeg_b64 not in serialized
    assert png_b64 not in serialized


def test_request_diagnostics_writer_appends_private_numbered_jsonl(tmp_path):
    proxy = load_proxy()
    path = tmp_path / "provider_requests.jsonl"
    writer = proxy.RequestDiagnosticsWriter(path)

    writer.write({"input_image_count": 0})
    writer.write({"input_image_count": 1})

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [record["request_index"] for record in records] == [1, 2]
    assert [record["input_image_count"] for record in records] == [0, 1]
    assert os.stat(path).st_mode & 0o777 == 0o600


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
            "--diagnostics-jsonl",
            "/tmp/provider_requests.jsonl",
            "--max-output-tokens",
            "4096",
        ]
    )
    assert args.host == "127.0.0.1"
    assert args.allowed_tool == ["briefing"]
    assert args.diagnostics_jsonl == Path("/tmp/provider_requests.jsonl")
    assert args.max_output_tokens == 4096

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
