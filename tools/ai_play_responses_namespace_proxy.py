#!/usr/bin/env python3
"""Loopback Responses proxy for Codex custom-provider MCP namespaces."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

import httpx


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 18767
MAX_REQUEST_BYTES = 64 * 1024 * 1024
_HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def rewrite_response_event(
    value: Any,
    *,
    namespace: str,
    allowed_tools: set[str] | frozenset[str],
) -> Any:
    if isinstance(value, dict):
        if value.get("type") == "function_call" and not value.get("namespace"):
            tool_name = value.get("name")
            provider_prefix = namespace.removeprefix("mcp__") + ":"
            if (
                isinstance(tool_name, str)
                and tool_name.startswith(provider_prefix)
                and tool_name.removeprefix(provider_prefix) in allowed_tools
            ):
                tool_name = tool_name.removeprefix(provider_prefix)
                value["name"] = tool_name
            if tool_name in allowed_tools:
                value["namespace"] = namespace
        for child in value.values():
            rewrite_response_event(
                child,
                namespace=namespace,
                allowed_tools=allowed_tools,
            )
    elif isinstance(value, list):
        for child in value:
            rewrite_response_event(
                child,
                namespace=namespace,
                allowed_tools=allowed_tools,
            )
    return value


def rewrite_sse_line(
    line: bytes,
    *,
    namespace: str,
    allowed_tools: set[str] | frozenset[str],
) -> bytes:
    if not line.startswith(b"data: ") or line == b"data: [DONE]":
        return line
    try:
        event = json.loads(line[6:])
    except (json.JSONDecodeError, UnicodeDecodeError):
        return line
    rewrite_response_event(
        event,
        namespace=namespace,
        allowed_tools=allowed_tools,
    )
    return b"data: " + json.dumps(
        event,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def is_allowed_request(method: str, path: str) -> bool:
    return method == "POST" and path == "/v1/responses"


def forward_request_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        name: value
        for name, value in headers.items()
        if name.casefold() not in _HOP_BY_HOP_HEADERS
    }


def build_upstream_responses_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("upstream base URL must use https and include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("upstream base URL must not contain credentials")
    if parsed.query or parsed.fragment or parsed.path.rstrip("/") != "/v1":
        raise ValueError("upstream base URL path must be /v1 without query")
    return normalized + "/responses"


def _walk_values(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child)


def _image_metadata(value: Any, ordinal: int) -> dict[str, Any]:
    metadata: dict[str, Any] = {"ordinal": ordinal}
    if not isinstance(value, str) or not value.startswith("data:"):
        metadata["source"] = "non_data_url"
        return metadata
    header, separator, encoded = value.partition(",")
    mime_type = header[5:].removesuffix(";base64").casefold()
    if (
        not separator
        or not header.endswith(";base64")
        or not mime_type.startswith("image/")
        or len(mime_type) > 64
        or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789/-.+"
            for character in mime_type
        )
    ):
        metadata["source"] = "invalid_data_url"
        return metadata
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        metadata["source"] = "invalid_data_url"
        return metadata
    metadata.update(
        {
            "mime_type": mime_type,
            "byte_count": len(decoded),
            "sha256": hashlib.sha256(decoded).hexdigest(),
        }
    )
    return metadata


def inspect_request_images(body: bytes) -> dict[str, Any]:
    """Return content-free image metadata for one Responses request."""
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("Responses request must be a JSON object")
    images = [
        _image_metadata(item.get("image_url"), ordinal)
        for ordinal, item in enumerate(
            (
                candidate
                for candidate in _walk_values(payload)
                if candidate.get("type") == "input_image"
            ),
            start=1,
        )
    ]
    return {
        "request_bytes": len(body),
        "input_image_count": len(images),
        "images": images,
        "has_previous_response_id": bool(payload.get("previous_response_id")),
        "store": (
            payload.get("store")
            if isinstance(payload.get("store"), bool)
            else None
        ),
    }


class RequestDiagnosticsWriter:
    """Append metadata-only request records to a private JSONL file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._request_index = 0

    def write(self, metadata: Mapping[str, Any]) -> None:
        with self._lock:
            self._request_index += 1
            record = {
                "event": "provider_request_images",
                "request_index": self._request_index,
                **metadata,
            }
            flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self._path, flags, 0o600)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "ab", closefd=False) as output:
                    output.write(
                        (
                            json.dumps(record, separators=(",", ":")) + "\n"
                        ).encode("utf-8")
                    )
                    output.flush()
            finally:
                os.close(descriptor)


def _response_headers(headers: Mapping[str, str]) -> Iterable[tuple[str, str]]:
    for name, value in headers.items():
        if name.casefold() not in _HOP_BY_HOP_HEADERS:
            yield name, value


def _handler_type(
    upstream_url: str,
    namespace: str,
    allowed_tools: frozenset[str],
    diagnostics_writer: RequestDiagnosticsWriter | None = None,
) -> type[BaseHTTPRequestHandler]:
    class ResponsesProxyHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format: str, *_args: object) -> None:
            return

        def _send_error(self, status: int, message: str) -> None:
            body = json.dumps({"error": message}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def do_GET(self) -> None:
            self._send_error(404, "not found")

        def do_POST(self) -> None:
            if not is_allowed_request("POST", self.path):
                self._send_error(404, "not found")
                return
            if self.headers.get("Transfer-Encoding"):
                self._send_error(400, "content length required")
                return
            try:
                content_length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._send_error(400, "invalid content length")
                return
            if content_length < 1:
                self._send_error(400, "request body required")
                return
            if content_length > MAX_REQUEST_BYTES:
                self._send_error(413, "request body too large")
                return
            body = self.rfile.read(content_length)
            if diagnostics_writer is not None:
                try:
                    diagnostics_writer.write(inspect_request_images(body))
                except (OSError, ValueError, json.JSONDecodeError):
                    self._send_error(500, "request diagnostics failed")
                    return
            response_started = False
            try:
                with httpx.Client(timeout=300.0, trust_env=False) as client:
                    with client.stream(
                        "POST",
                        upstream_url,
                        headers=forward_request_headers(dict(self.headers.items())),
                        content=body,
                    ) as response:
                        response_started = True
                        self.send_response(response.status_code)
                        for name, value in _response_headers(response.headers):
                            self.send_header(name, value)
                        self.send_header("Connection", "close")
                        self.end_headers()
                        content_type = response.headers.get("content-type", "")
                        if content_type.startswith("text/event-stream"):
                            for line in response.iter_lines():
                                rewritten = rewrite_sse_line(
                                    line.encode("utf-8"),
                                    namespace=namespace,
                                    allowed_tools=allowed_tools,
                                )
                                self.wfile.write(rewritten + b"\n")
                                self.wfile.flush()
                        else:
                            response_body = response.read()
                            if "application/json" in content_type:
                                payload = json.loads(response_body)
                                rewrite_response_event(
                                    payload,
                                    namespace=namespace,
                                    allowed_tools=allowed_tools,
                                )
                                response_body = json.dumps(
                                    payload,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                ).encode("utf-8")
                            self.wfile.write(response_body)
                        self.close_connection = True
            except (httpx.HTTPError, json.JSONDecodeError):
                if not response_started:
                    self._send_error(502, "upstream request failed")
                else:
                    self.close_connection = True
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

    return ResponsesProxyHandler


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add Codex MCP namespaces to trusted Responses tool calls.",
    )
    parser.add_argument("--host", default=LOOPBACK_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--upstream-base-url", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--allowed-tool", action="append", required=True)
    parser.add_argument("--diagnostics-jsonl", type=Path)
    args = parser.parse_args(argv)
    if args.host != LOOPBACK_HOST:
        parser.error("--host must be 127.0.0.1")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if any(not value or value.strip() != value for value in args.allowed_tool):
        parser.error("--allowed-tool values must be non-empty")
    if (
        args.diagnostics_jsonl is not None
        and not args.diagnostics_jsonl.is_absolute()
    ):
        parser.error("--diagnostics-jsonl must be an absolute path")
    try:
        build_upstream_responses_url(args.upstream_base_url)
    except ValueError as error:
        parser.error(str(error))
    return args


def main(argv: Sequence[str] | None = None) -> int:
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    upstream_url = build_upstream_responses_url(args.upstream_base_url)
    handler = _handler_type(
        upstream_url,
        args.namespace,
        frozenset(args.allowed_tool),
        RequestDiagnosticsWriter(args.diagnostics_jsonl)
        if args.diagnostics_jsonl is not None
        else None,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        "[responses-proxy] listening on %s:%s" % (args.host, args.port),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
