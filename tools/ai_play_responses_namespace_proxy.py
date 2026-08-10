#!/usr/bin/env python3
"""Loopback Responses proxy for Codex custom-provider MCP namespaces."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
        if (
            value.get("type") == "function_call"
            and value.get("name") in allowed_tools
            and not value.get("namespace")
        ):
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


def _response_headers(headers: Mapping[str, str]) -> Iterable[tuple[str, str]]:
    for name, value in headers.items():
        if name.casefold() not in _HOP_BY_HOP_HEADERS:
            yield name, value


def _handler_type(
    upstream_url: str,
    namespace: str,
    allowed_tools: frozenset[str],
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
    args = parser.parse_args(argv)
    if args.host != LOOPBACK_HOST:
        parser.error("--host must be 127.0.0.1")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if any(not value or value.strip() != value for value in args.allowed_tool):
        parser.error("--allowed-tool values must be non-empty")
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
