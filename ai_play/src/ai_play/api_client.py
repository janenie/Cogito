"""OpenAI-compatible Chat Completions adapter."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time

from openai import OpenAI


_JSON_FENCE = re.compile(r"\A```json[ \t]*\r?\n([\s\S]*?)\r?\n```\Z")


def _reject_json_constant(value):
    raise ValueError(f"non-standard JSON constant: {value}")


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    match = _JSON_FENCE.fullmatch(stripped)
    if match is not None:
        return match.group(1)
    return stripped


def parse_model_json(content: str):
    return json.loads(
        _strip_json_fence(content),
        parse_constant=_reject_json_constant,
    )


@dataclass(frozen=True)
class ModelCompletion:
    raw_content: str
    latency_ms: int


class ApiClient:
    """Send decision messages to an OpenAI-compatible endpoint."""

    def __init__(self, config, client=None):
        self.config = config
        self.client = client or OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            max_retries=config.api_max_retries,
        )

    def complete(self, messages):
        started_ns = time.monotonic_ns()
        completion = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            timeout=self.config.request_timeout_seconds,
        )
        content = completion.choices[0].message.content
        if not isinstance(content, str):
            raise ValueError("model response content must be text JSON")
        return ModelCompletion(
            raw_content=content,
            latency_ms=(time.monotonic_ns() - started_ns) // 1_000_000,
        )

    def decide(self, messages):
        return parse_model_json(self.complete(messages).raw_content)
