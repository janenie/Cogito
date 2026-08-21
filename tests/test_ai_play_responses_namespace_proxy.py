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


def _observation_image_output(observation_id, image_count=2):
    content = [
        {
            "type": "input_text",
            "text": json.dumps(
                {
                    "status": "ready",
                    "observation": {
                        "observation_id": observation_id,
                        "player": {
                            "position": [1.0, 2.0, 3.0],
                            "yaw_degrees": 45.0,
                            "pitch_degrees": -5.0,
                        },
                        "interface": {
                            "is_open": True,
                            "visible_object_text": f"Contract {observation_id}",
                            "available_interactions": ["Read"],
                        },
                        "depth_image": {
                            "near_meters": 0.05,
                            "far_meters": 20.0,
                        },
                    },
                }
            ),
        }
    ]
    mime_types = ("image/jpeg", "image/png", "image/webp")
    for index in range(image_count):
        encoded = base64.b64encode(
            f"observation-{observation_id}-image-{index}".encode()
        ).decode()
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:{mime_types[index % len(mime_types)]};base64,{encoded}",
                "detail": "high",
            }
        )
    return content


def _caption_store(proxy, tmp_path):
    return proxy.ImageCaptionStore(
        jsonl_path=tmp_path / "provider_image_captions.jsonl",
        image_dir=tmp_path / "provider_caption_images",
    )


def test_caption_store_indexes_binary_image_and_reloads_caption(tmp_path):
    proxy = load_proxy()
    store = _caption_store(proxy, tmp_path)
    image_bytes = b"fixture-jpeg-image"
    encoded = base64.b64encode(image_bytes).decode()

    record = store.register_image(
        f"data:image/jpeg;base64,{encoded}",
    )
    store.record_captions(
        model="gemini-fixture",
        captions={record.image_id: "桌面中央有一份合同，右侧是关闭的门。"},
    )

    image_path = tmp_path / record.relative_path
    assert image_path.read_bytes() == image_bytes
    assert os.stat(image_path).st_mode & 0o777 == 0o600
    assert os.stat(image_path.parent).st_mode & 0o777 == 0o700
    records = [
        json.loads(line)
        for line in (tmp_path / "provider_image_captions.jsonl")
        .read_text()
        .splitlines()
    ]
    assert records == [
        {
            "event": "provider_image_caption",
            "model": "gemini-fixture",
            "image_id": record.image_id,
            "mime_type": "image/jpeg",
            "byte_count": len(image_bytes),
            "image_path": record.relative_path,
            "caption": "桌面中央有一份合同，右侧是关闭的门。",
        }
    ]
    assert encoded not in json.dumps(records)

    reloaded = _caption_store(proxy, tmp_path)
    assert reloaded.caption_for(record.image_id) == (
        "桌面中央有一份合同，右侧是关闭的门。"
    )


def test_prepare_image_context_requests_real_captions_then_reuses_them(
    tmp_path,
):
    proxy = load_proxy()
    store = _caption_store(proxy, tmp_path)
    request = {
        "model": "gemini-fixture",
        "instructions": "Play the game.",
        "input": [
            {
                "type": "function_call_output",
                "call_id": f"call-{observation_id}",
                "output": _observation_image_output(observation_id),
            }
            for observation_id in range(1, 8)
        ]
    }

    metadata, pending = proxy.prepare_request_image_context(
        request,
        caption_store=store,
        max_historical_images=10,
    )

    assert len(pending) == 14
    assert metadata["pending_caption_count"] == 14
    assert "最多 200 个中文字符" in request["instructions"]
    assert all(image_id in request["instructions"] for image_id in pending)
    labels = [
        value["text"]
        for value in proxy._walk_values(request)
        if value.get("type") == "input_text"
        and value.get("text", "").startswith("[Trusted image_id=")
    ]
    assert len(labels) == 14

    store.record_captions(
        model="gemini-fixture",
        captions={
            image_id: f"真实视觉说明 {index}"
            for index, image_id in enumerate(pending, start=1)
        },
    )
    replay = {
        "model": "gemini-fixture",
        "instructions": "Play the game.",
        "input": [
            {
                "type": "function_call_output",
                "call_id": f"call-{observation_id}",
                "output": _observation_image_output(observation_id),
            }
            for observation_id in range(1, 8)
        ],
    }
    metadata, pending = proxy.prepare_request_image_context(
        replay,
        caption_store=store,
        max_historical_images=10,
    )
    images = [
        value
        for value in proxy._walk_values(replay)
        if value.get("type") == "input_image"
    ]
    captions = [
        value["text"]
        for value in proxy._walk_values(replay)
        if value.get("type") == "input_text"
        and value.get("text", "").startswith("[Historical image caption:")
    ]
    assert len(images) == 12
    assert len(captions) == 2
    assert pending == ()
    assert metadata["captioned_image_count"] == 2
    assert metadata["pending_caption_count"] == 0
    assert "真实视觉说明 1" in captions[0]
    assert "真实视觉说明 2" in captions[1]
    assert "Contract 1" not in "".join(captions)
    assert "observation-1-image-0" not in json.dumps(replay)
    assert all(
        item["type"] == "input_image"
        for item in replay["input"][-1]["output"][1:]
    )


def test_prepare_image_context_always_keeps_latest_group_until_captioned(
    tmp_path,
):
    proxy = load_proxy()
    store = _caption_store(proxy, tmp_path)
    request = {
        "model": "gemini-fixture",
        "input": [
            {"output": _observation_image_output(1)},
            {"output": _observation_image_output(2, image_count=3)},
        ]
    }

    metadata, pending = proxy.prepare_request_image_context(
        request,
        caption_store=store,
        max_historical_images=0,
    )

    assert len(pending) == 5
    assert metadata["input_image_count"] == 5
    assert metadata["captioned_image_count"] == 0
    assert metadata["latest_image_count"] == 3
    assert sum(
        item.get("type") == "input_image"
        for item in request["input"][-1]["output"]
        if isinstance(item, dict)
    ) == 3


def _caption_envelope(proxy, captions):
    return (
        proxy.CAPTION_ENVELOPE_START
        + json.dumps({"captions": captions}, ensure_ascii=False)
        + proxy.CAPTION_ENVELOPE_END
    )


def test_finalize_caption_response_stores_and_removes_internal_envelope(
    tmp_path,
):
    proxy = load_proxy()
    store = _caption_store(proxy, tmp_path)
    first = store.register_image(
        "data:image/jpeg;base64,"
        + base64.b64encode(b"first").decode()
    )
    second = store.register_image(
        "data:image/png;base64,"
        + base64.b64encode(b"second").decode()
    )
    envelope = _caption_envelope(
        proxy,
        [
            {"image_id": first.image_id, "caption": "左侧有一扇门。"},
            {"image_id": second.image_id, "caption": "前方通路较空旷。"},
        ],
    )
    response = {
        "output": [
            {
                "id": "msg_1",
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": f"继续执行。\n{envelope}",
                    }
                ],
            },
            {
                "type": "function_call",
                "name": "mcp__cogito_ai_play__act",
                "arguments": "{}",
            },
        ]
    }

    proxy.finalize_caption_response_payload(
        response,
        pending_image_ids=(first.image_id, second.image_id),
        caption_store=store,
        model="gemini-fixture",
    )

    serialized = json.dumps(response, ensure_ascii=False)
    assert "继续执行。" in serialized
    assert proxy.CAPTION_ENVELOPE_START not in serialized
    assert first.image_id not in serialized
    assert "左侧有一扇门" not in serialized
    assert store.caption_for(first.image_id) == "左侧有一扇门。"
    assert store.caption_for(second.image_id) == "前方通路较空旷。"


def test_finalize_caption_response_rejects_missing_or_unknown_caption(
    tmp_path,
):
    proxy = load_proxy()
    store = _caption_store(proxy, tmp_path)
    record = store.register_image(
        "data:image/jpeg;base64,"
        + base64.b64encode(b"fixture").decode()
    )

    for captions in (
        [],
        [{"image_id": "f" * 64, "caption": "未知图片"}],
        [
            {"image_id": record.image_id, "caption": "有效"},
            {"image_id": record.image_id, "caption": "重复"},
        ],
        [{"image_id": record.image_id, "caption": "字" * 201}],
    ):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": _caption_envelope(proxy, captions),
                        }
                    ],
                }
            ]
        }
        try:
            proxy.finalize_caption_response_payload(
                response,
                pending_image_ids=(record.image_id,),
                caption_store=store,
                model="gemini-fixture",
            )
        except proxy.CaptionProtocolError:
            pass
        else:
            raise AssertionError("expected invalid caption response rejection")


def _sse_lines(events):
    lines = []
    for event in events:
        lines.extend(
            [
                f"event: {event['type']}".encode(),
                b"data: "
                + json.dumps(
                    event,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode(),
                b"",
            ]
        )
    return lines


def test_finalize_caption_sse_handles_split_text_and_restores_tools(tmp_path):
    proxy = load_proxy()
    store = _caption_store(proxy, tmp_path)
    record = store.register_image(
        "data:image/jpeg;base64,"
        + base64.b64encode(b"stream-image").decode()
    )
    envelope = _caption_envelope(
        proxy,
        [{"image_id": record.image_id, "caption": "前方桌面有一份文件。"}],
    )
    full_text = f"继续操作。\n{envelope}"
    message = {
        "id": "msg_1",
        "type": "message",
        "status": "completed",
        "content": [
            {"type": "output_text", "text": full_text, "annotations": []}
        ],
    }
    function_call = {
        "id": "fc_1",
        "type": "function_call",
        "status": "completed",
        "name": "mcp__cogito_ai_play__act",
        "arguments": "{}",
    }
    response = {
        "id": "resp_1",
        "status": "completed",
        "output": [message, function_call],
    }
    split_at = len(full_text) // 2
    lines = _sse_lines(
        [
            {
                "type": "response.output_text.delta",
                "item_id": "msg_1",
                "output_index": 0,
                "content_index": 0,
                "delta": full_text[:split_at],
            },
            {
                "type": "response.output_text.delta",
                "item_id": "msg_1",
                "output_index": 0,
                "content_index": 0,
                "delta": full_text[split_at:],
            },
            {
                "type": "response.output_text.done",
                "item_id": "msg_1",
                "output_index": 0,
                "content_index": 0,
                "text": full_text,
            },
            {
                "type": "response.content_part.done",
                "item_id": "msg_1",
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": full_text},
            },
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": message,
            },
            {
                "type": "response.output_item.done",
                "output_index": 1,
                "item": function_call,
            },
            {"type": "response.completed", "response": response},
        ]
    )
    reverse_map = {
        "mcp__cogito_ai_play__act": proxy.NamespacedToolName(
            "mcp__cogito_ai_play",
            "act",
        )
    }

    rewritten = proxy.finalize_caption_sse_lines(
        lines,
        pending_image_ids=(record.image_id,),
        caption_store=store,
        model="gemini-fixture",
        namespace="mcp__cogito_ai_play",
        allowed_tools=frozenset({"act"}),
        restore_map=reverse_map,
    )

    serialized = b"\n".join(rewritten).decode()
    assert "继续操作。" in serialized
    assert proxy.CAPTION_ENVELOPE_START not in serialized
    assert record.image_id not in serialized
    assert "前方桌面有一份文件" not in serialized
    assert '"name":"act"' in serialized
    assert '"namespace":"mcp__cogito_ai_play"' in serialized
    assert store.caption_for(record.image_id) == "前方桌面有一份文件。"


def test_finalize_caption_sse_fails_before_forwarding_missing_caption(tmp_path):
    proxy = load_proxy()
    store = _caption_store(proxy, tmp_path)
    record = store.register_image(
        "data:image/png;base64,"
        + base64.b64encode(b"depth-image").decode()
    )
    lines = _sse_lines(
        [
            {
                "type": "response.completed",
                "response": {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "没有图片说明",
                                }
                            ],
                        }
                    ],
                },
            }
        ]
    )

    try:
        proxy.finalize_caption_sse_lines(
            lines,
            pending_image_ids=(record.image_id,),
            caption_store=store,
            model="gemini-fixture",
            namespace="mcp__cogito_ai_play",
            allowed_tools=frozenset(),
            restore_map={},
        )
    except proxy.CaptionProtocolError:
        pass
    else:
        raise AssertionError("expected missing caption to fail closed")
    assert store.caption_for(record.image_id) is None


def _run_proxy_request(proxy, handler, request):
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
            body=json.dumps(request).encode(),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_proxy_buffers_caption_response_and_fails_closed_before_forwarding(
    monkeypatch,
    tmp_path,
):
    proxy = load_proxy()
    store = _caption_store(proxy, tmp_path)
    image_bytes = b"handler-image"
    image_id = hashlib.sha256(image_bytes).hexdigest()
    image_url = (
        "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
    )
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "text/event-stream"}

        def __init__(self, lines):
            self._lines = lines

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def iter_lines(self):
            return [line.decode() for line in self._lines]

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream(self, *_args, **kwargs):
            captured["request"] = json.loads(kwargs["content"])
            caption_text = captured.get("caption_text", "没有说明")
            message = {
                "id": "msg_handler",
                "type": "message",
                "content": [
                    {"type": "output_text", "text": caption_text}
                ],
            }
            return FakeResponse(
                _sse_lines(
                    [
                        {
                            "type": "response.output_text.delta",
                            "item_id": "msg_handler",
                            "output_index": 0,
                            "content_index": 0,
                            "delta": caption_text,
                        },
                        {
                            "type": "response.output_item.done",
                            "output_index": 0,
                            "item": message,
                        },
                        {
                            "type": "response.completed",
                            "response": {
                                "status": "completed",
                                "output": [message],
                            },
                        },
                    ]
                )
            )

    monkeypatch.setattr(proxy.httpx, "Client", FakeClient)
    handler = proxy._handler_type(
        "https://yibuapi.com/v1/responses",
        "mcp__cogito_ai_play",
        frozenset(),
        caption_store=store,
    )
    request = {
        "model": "gemini-fixture",
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "observe"},
                    {"type": "input_image", "image_url": image_url},
                ],
            }
        ],
    }

    status, body = _run_proxy_request(proxy, handler, request)
    assert status == 502
    assert body == b'{"error": "image caption protocol failed"}'
    assert store.caption_for(image_id) is None

    captured["caption_text"] = _caption_envelope(
        proxy,
        [{"image_id": image_id, "caption": "画面中有一张桌子。"}],
    )
    status, body = _run_proxy_request(proxy, handler, request)

    assert status == 200
    assert proxy.CAPTION_ENVELOPE_START.encode() not in body
    assert store.caption_for(image_id) == "画面中有一张桌子。"
    assert image_id in captured["request"]["instructions"]
    assert any(
        value.get("type") == "input_text"
        and image_id in value.get("text", "")
        for value in proxy._walk_values(captured["request"])
    )


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


def test_caption_store_uses_private_siblings_of_provider_diagnostics(tmp_path):
    proxy = load_proxy()
    diagnostics_path = tmp_path / "trusted_mcplogs" / "provider_requests.jsonl"
    diagnostics_path.parent.mkdir()

    store = proxy.caption_store_for_diagnostics(diagnostics_path)

    assert store._jsonl_path == (
        diagnostics_path.parent / "provider_image_captions.jsonl"
    )
    assert store._image_dir == (
        diagnostics_path.parent / "provider_caption_images"
    )
    assert os.stat(store._image_dir).st_mode & 0o777 == 0o700


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
        ]
    )
    assert args.host == "127.0.0.1"
    assert args.allowed_tool == ["briefing"]
    assert args.diagnostics_jsonl == Path("/tmp/provider_requests.jsonl")
    assert args.max_historical_images == 10

    for argv in (
        ["--host", "0.0.0.0", "--allowed-tool", "briefing"],
        ["--host", "127.0.0.1"],
        [
            "--host",
            "127.0.0.1",
            "--allowed-tool",
            "briefing",
            "--max-historical-images",
            "-1",
        ],
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
