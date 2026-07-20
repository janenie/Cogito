"""OpenAI-compatible Chat Completions adapter."""

from __future__ import annotations

import json
import re

from openai import OpenAI


_JSON_FENCE = re.compile(r"\A```json[ \t]*\r?\n([\s\S]*?)\r?\n```\Z")


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    match = _JSON_FENCE.fullmatch(stripped)
    if match is not None:
        return match.group(1)
    return stripped


class ApiClient:
    """Send decision messages to an OpenAI-compatible endpoint."""

    def __init__(self, config, client=None):
        self.config = config
        self.client = client or OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            max_retries=config.api_max_retries,
        )

    def decide(self, messages):
        completion = self.client.chat.completions.create(
            model=self.config.model,
            messages=messages,
            timeout=self.config.request_timeout_seconds,
        )
        content = completion.choices[0].message.content
        if not isinstance(content, str):
            raise ValueError("model response content must be text JSON")
        return json.loads(_strip_json_fence(content))
