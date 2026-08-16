#!/usr/bin/env python3
"""Translate Codex Responses requests for the Yibu/Doubao compatibility API."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from contextlib import contextmanager
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
import time
from typing import Any, Callable, ContextManager, Iterable, Iterator, Mapping

import httpx


AI_PLAY_NAMESPACE = "mcp__cogito_ai_play"
MAX_PROVIDER_OUTPUT_TOKENS = 32768
MAX_REQUEST_BODY_BYTES = 16 * 1024 * 1024
MAX_ERROR_BODY_BYTES = 64 * 1024
UPSTREAM_CONNECT_TIMEOUT_SECONDS = 30.0
UPSTREAM_READ_TIMEOUT_SECONDS = 660.0


class RequestTransformError(ValueError):
    """The Codex request cannot be translated without widening permissions."""


class SseTransformError(ValueError):
    """The upstream event stream cannot be safely forwarded to Codex."""


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
        # Codex registers namespaced MCP tools under their original short name.
        # Yibu needs the flattened alias in the provider request, so translate
        # that alias back before Codex routes the returned function call.
        aliases[alias] = name
        found.add(name)

    missing = [name for name in settings.enabled_tools if name not in found]
    if missing:
        raise RequestTransformError(
            "AI Play namespace is missing enabled tools: %s"
            % ", ".join(missing)
        )
    return flattened, aliases


def _flatten_input_function_calls(value: Any, settings: ProxySettings) -> None:
    if isinstance(value, list):
        for item in value:
            _flatten_input_function_calls(item, settings)
        return
    if not isinstance(value, dict):
        return
    if (
        value.get("type") == "message"
        and value.get("role") == "assistant"
        and "status" not in value
    ):
        value["status"] = "completed"
    if value.get("type") == "function_call" and "namespace" in value:
        namespace = value.get("namespace")
        name = value.get("name")
        if (
            namespace != settings.namespace
            or not isinstance(name, str)
            or name not in settings.enabled_tools
        ):
            raise RequestTransformError(
                "request input function call is outside the AI Play allowlist"
            )
        value["name"] = _flat_tool_alias(settings.namespace, name)
        value["status"] = "completed"
        value.pop("namespace")
    for item in value.values():
        _flatten_input_function_calls(item, settings)


def _count_input_images(value: Any) -> int:
    if isinstance(value, list):
        return sum(_count_input_images(item) for item in value)
    if not isinstance(value, dict):
        return 0
    return int(value.get("type") == "input_image") + sum(
        _count_input_images(item) for item in value.values()
    )


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
    _flatten_input_function_calls(transformed.get("input"), settings)
    transformed["parallel_tool_calls"] = False
    transformed["max_output_tokens"] = settings.max_output_tokens
    return TransformedRequest(payload=transformed, aliases=aliases)


_SSE_FRAME_END = re.compile(br"\r?\n\r?\n")
_SSE_DONE_EVENT = "__provider_done__"
_SSE_TERMINAL_EVENTS = frozenset(
    {"response.completed", "response.failed", "response.incomplete"}
)


def _rewrite_function_calls(value: Any, aliases: Mapping[str, str]) -> None:
    if isinstance(value, list):
        for item in value:
            _rewrite_function_calls(item, aliases)
        return
    if not isinstance(value, dict):
        return
    if value.get("type") == "function_call":
        name = value.get("name")
        if not isinstance(name, str) or name not in aliases:
            raise SseTransformError(f"unknown function alias: {name!r}")
        short_name = aliases[name]
        suffix = f"__{short_name}"
        if not name.endswith(suffix):
            raise SseTransformError(f"invalid function alias mapping: {name!r}")
        value["name"] = short_name
        value["namespace"] = name[: -len(suffix)]
    for item in value.values():
        _rewrite_function_calls(item, aliases)


def _transform_sse_frame(
    raw_frame: bytes,
    aliases: Mapping[str, str],
) -> tuple[bytes, str | None]:
    try:
        text = raw_frame.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise SseTransformError("SSE frame is not valid UTF-8") from error
    lines = text.splitlines()
    data_lines: list[str] = []
    prefix_lines: list[str] = []
    for line in lines:
        if line.startswith("data:"):
            data = line[5:]
            if data.startswith(" "):
                data = data[1:]
            data_lines.append(data)
        else:
            prefix_lines.append(line)
    if not data_lines:
        return (text + "\n\n").encode("utf-8"), None
    joined_data = "\n".join(data_lines)
    if joined_data == "[DONE]":
        return b"", _SSE_DONE_EVENT
    try:
        payload = json.loads(joined_data)
    except json.JSONDecodeError as error:
        raise SseTransformError("SSE data is not valid JSON") from error
    _rewrite_function_calls(payload, aliases)
    event_type = payload.get("type") if isinstance(payload, dict) else None
    output_lines = prefix_lines + [
        "data: " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    ]
    return ("\n".join(output_lines) + "\n\n").encode("utf-8"), event_type


def transform_sse_chunks(
    chunks: Iterable[bytes],
    aliases: Mapping[str, str],
) -> Iterator[bytes]:
    """Frame, validate, and translate one streaming Responses SSE body."""
    buffer = b""
    terminal = False
    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise SseTransformError("SSE chunks must be bytes")
        buffer += chunk
        while True:
            match = _SSE_FRAME_END.search(buffer)
            if match is None:
                break
            raw_frame = buffer[: match.start()]
            buffer = buffer[match.end() :]
            if not raw_frame:
                continue
            output, event_type = _transform_sse_frame(raw_frame, aliases)
            if terminal:
                if event_type in (None, _SSE_DONE_EVENT):
                    continue
                raise SseTransformError("SSE data followed a terminal event")
            if event_type == _SSE_DONE_EVENT:
                raise SseTransformError(
                    "SSE [DONE] arrived before a terminal response event"
                )
            if event_type in _SSE_TERMINAL_EVENTS:
                terminal = True
            yield output
    if buffer:
        output, event_type = _transform_sse_frame(buffer, aliases)
        if terminal:
            if event_type not in (None, _SSE_DONE_EVENT):
                raise SseTransformError("SSE data followed a terminal event")
        elif event_type in _SSE_TERMINAL_EVENTS:
            terminal = True
            yield output
        elif event_type == _SSE_DONE_EVENT:
            raise SseTransformError(
                "SSE [DONE] arrived before a terminal response event"
            )
        else:
            raise SseTransformError(
                "incomplete SSE frame at upstream disconnect"
            )
    if not terminal:
        raise SseTransformError("SSE stream ended without a terminal event")


UpstreamFactory = Callable[
    [str, Mapping[str, str], bytes, httpx.Timeout],
    ContextManager[Any],
]


@contextmanager
def _default_upstream_factory(
    url: str,
    headers: Mapping[str, str],
    content: bytes,
    timeout: httpx.Timeout,
) -> Iterator[httpx.Response]:
    with httpx.stream(
        "POST",
        url,
        headers=dict(headers),
        content=content,
        timeout=timeout,
    ) as response:
        yield response


class _LoopbackHttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


class DoubaoProxyServer:
    """Authenticated loopback-only streaming proxy for one Codex player."""

    def __init__(
        self,
        *,
        settings: ProxySettings,
        upstream_base_url: str,
        upstream_token: str,
        proxy_token: str,
        upstream_factory: UpstreamFactory | None = None,
        event_logger: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> None:
        self.settings = settings
        self.upstream_base_url = upstream_base_url.rstrip("/")
        self._upstream_token = upstream_token
        self._proxy_token = proxy_token
        self._upstream_factory = upstream_factory or _default_upstream_factory
        self._event_logger = event_logger or self._print_event
        self._server: _LoopbackHttpServer | None = None
        self._thread: threading.Thread | None = None
        self._active_lock = threading.Lock()
        self._active_responses: set[Any] = set()
        self._stopping_event = threading.Event()
        self._failure_event = threading.Event()
        self._thread_error: BaseException | None = None

    @staticmethod
    def _print_event(event: Mapping[str, Any]) -> None:
        print(
            "[doubao-proxy] "
            + json.dumps(event, ensure_ascii=False, separators=(",", ":")),
            flush=True,
        )

    @property
    def host(self) -> str:
        return "127.0.0.1"

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("proxy server is not running")
        return int(self._server.server_address[1])

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    @property
    def failure_event(self) -> threading.Event:
        return self._failure_event

    @property
    def thread_error(self) -> BaseException | None:
        return self._thread_error

    def __enter__(self) -> "DoubaoProxyServer":
        if self._server is not None:
            raise RuntimeError("proxy server is already running")
        self._stopping_event.clear()
        self._failure_event.clear()
        self._thread_error = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:
                if self.path == "/healthz":
                    self._send_json(200, {"status": "ready"})
                elif self.path == "/v1/responses":
                    self._send_json(405, {"error": {"message": "method not allowed"}})
                else:
                    self._send_json(404, {"error": {"message": "not found"}})

            def do_POST(self) -> None:
                if self.path != "/v1/responses":
                    self._send_json(404, {"error": {"message": "not found"}})
                    return
                authorization = self.headers.get("authorization", "")
                expected = "Bearer " + owner._proxy_token
                if not hmac.compare_digest(authorization, expected):
                    self.close_connection = True
                    self._send_json(401, {"error": {"message": "unauthorized"}})
                    return
                raw_length = self.headers.get("content-length")
                try:
                    length = int(raw_length) if raw_length is not None else -1
                except ValueError:
                    length = -1
                if length < 0:
                    self.close_connection = True
                    self._send_json(411, {"error": {"message": "content length required"}})
                    return
                if length > MAX_REQUEST_BODY_BYTES:
                    self.close_connection = True
                    self._send_json(413, {"error": {"message": "request body too large"}})
                    return
                body = self.rfile.read(length)
                started = time.monotonic()
                try:
                    payload = json.loads(body)
                    transformed = transform_request(payload, owner.settings)
                except (json.JSONDecodeError, RequestTransformError) as error:
                    self._send_json(400, {"error": {"message": str(error)}})
                    return
                upstream_body = json.dumps(
                    transformed.payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                input_image_count = _count_input_images(
                    transformed.payload.get("input")
                )
                upstream_headers = {
                    "authorization": "Bearer " + owner._upstream_token,
                    "content-type": "application/json",
                    "accept": "text/event-stream",
                }
                timeout = httpx.Timeout(
                    connect=UPSTREAM_CONNECT_TIMEOUT_SECONDS,
                    read=UPSTREAM_READ_TIMEOUT_SECONDS,
                    write=UPSTREAM_CONNECT_TIMEOUT_SECONDS,
                    pool=UPSTREAM_CONNECT_TIMEOUT_SECONDS,
                )
                response = None
                response_bytes = 0
                try:
                    with owner._upstream_factory(
                        owner.upstream_base_url + "/responses",
                        upstream_headers,
                        upstream_body,
                        timeout,
                    ) as response:
                        owner._register_response(response)
                        status = int(response.status_code)
                        if status != 200:
                            error_body = bytearray()
                            for chunk in response.iter_bytes():
                                remaining = MAX_ERROR_BODY_BYTES - len(error_body)
                                if remaining <= 0:
                                    break
                                error_body.extend(chunk[:remaining])
                            response_bytes = len(error_body)
                            self._send_bytes(
                                status,
                                bytes(error_body),
                                owner._safe_headers(response.headers),
                            )
                            owner._event_logger(
                                {
                                    "event": "request_completed",
                                    "status": status,
                                    "request_bytes": len(body),
                                    "input_image_count": input_image_count,
                                    "response_bytes": response_bytes,
                                    "duration_ms": int(
                                        (time.monotonic() - started) * 1000
                                    ),
                                    "request_id": response.headers.get(
                                        "x-request-id"
                                    ),
                                }
                            )
                            return
                        self.send_response(200)
                        for name, value in owner._safe_headers(response.headers).items():
                            self.send_header(name, value)
                        self.send_header("transfer-encoding", "chunked")
                        self.end_headers()
                        try:
                            for chunk in transform_sse_chunks(
                                response.iter_bytes(),
                                transformed.aliases,
                            ):
                                response_bytes += len(chunk)
                                self.wfile.write((f"{len(chunk):X}\r\n").encode("ascii"))
                                self.wfile.write(chunk)
                                self.wfile.write(b"\r\n")
                                self.wfile.flush()
                            self.wfile.write(b"0\r\n\r\n")
                            self.wfile.flush()
                        except (OSError, SseTransformError):
                            self.close_connection = True
                            raise
                except (httpx.HTTPError, OSError, SseTransformError) as error:
                    failure_event = {
                        "event": "request_failed",
                        "error_type": type(error).__name__,
                        "request_bytes": len(body),
                        "input_image_count": input_image_count,
                        "response_bytes": response_bytes,
                        "duration_ms": int((time.monotonic() - started) * 1000),
                    }
                    if isinstance(error, SseTransformError):
                        failure_event["error_reason"] = str(error)
                    owner._event_logger(failure_event)
                    if not self.wfile.closed and not self.close_connection:
                        self._send_json(502, {"error": {"message": "upstream failure"}})
                    return
                finally:
                    if response is not None:
                        owner._unregister_response(response)
                owner._event_logger(
                    {
                        "event": "request_completed",
                        "status": 200,
                        "request_bytes": len(body),
                        "input_image_count": input_image_count,
                        "response_bytes": response_bytes,
                        "duration_ms": int((time.monotonic() - started) * 1000),
                        "request_id": (
                            response.headers.get("x-request-id")
                            if response is not None
                            else None
                        ),
                    }
                )

            def _send_json(self, status: int, payload: Mapping[str, Any]) -> None:
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self._send_bytes(status, body, {"content-type": "application/json"})

            def _send_bytes(
                self,
                status: int,
                body: bytes,
                headers: Mapping[str, str],
            ) -> None:
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        self._server = _LoopbackHttpServer((self.host, 0), Handler)
        def serve() -> None:
            try:
                assert owner._server is not None
                owner._server.serve_forever()
            except BaseException as error:
                owner._thread_error = error
            finally:
                if not owner._stopping_event.is_set():
                    if owner._thread_error is None:
                        owner._thread_error = RuntimeError(
                            "Doubao proxy server thread exited unexpectedly"
                        )
                    owner._failure_event.set()

        self._thread = threading.Thread(
            target=serve,
            name="doubao-responses-proxy",
            daemon=True,
        )
        self._thread.start()
        return self

    @staticmethod
    def _safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
        safe = {}
        for name in ("content-type", "x-request-id"):
            value = headers.get(name)
            if value:
                safe[name] = value
        return safe

    def _register_response(self, response: Any) -> None:
        with self._active_lock:
            self._active_responses.add(response)

    def _unregister_response(self, response: Any) -> None:
        with self._active_lock:
            self._active_responses.discard(response)

    def close(self) -> None:
        self._stopping_event.set()
        with self._active_lock:
            responses = list(self._active_responses)
        for response in responses:
            try:
                response.close()
            except Exception:
                pass
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._server = None
        self._thread = None

    def __exit__(self, *_exc: object) -> None:
        self.close()
