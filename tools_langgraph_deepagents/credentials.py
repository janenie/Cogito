from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class YibuCredentials:
    api_key: str
    base_url: str


def _normalize_base_url(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("yibu credential URL must be non-empty")
    url = value.strip().rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError("yibu credential URL must use https")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("yibu credential URL must not contain credentials")
    if not parsed.hostname or parsed.query or parsed.fragment:
        raise ValueError("invalid yibu credential URL")
    if parsed.path in ("", "/"):
        return url + "/v1"
    if parsed.path.rstrip("/") != "/v1":
        raise ValueError("yibu credential URL path must be /v1 or empty")
    return url


def load_yibu_credentials(path: Path, variable: str) -> YibuCredentials:
    source = path.expanduser()
    try:
        text = source.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ValueError(
            f"missing yibu credential file: {source}"
        ) from error
    except OSError as error:
        raise ValueError("invalid yibu credential file") from error
    try:
        tree = ast.parse(text, filename=str(source))
    except SyntaxError as error:
        raise ValueError("invalid yibu credential file") from error
    for node in tree.body:
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable
            for target in node.targets
        ):
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == variable
        ):
            value = node.value
        if value is None:
            continue
        try:
            payload = ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError) as error:
            raise ValueError(
                "credential must be a literal dictionary"
            ) from error
        if not isinstance(payload, dict):
            raise ValueError("credential must be a literal dictionary")
        key = payload.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("yibu credential key must be non-empty")
        return YibuCredentials(
            key.strip(),
            _normalize_base_url(payload.get("url")),
        )
    raise ValueError(f"missing credential variable: {variable}")
