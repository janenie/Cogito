from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from tools_langgraph_deepagents.credentials import YibuCredentials


def build_yibu_chat_model(
    credentials: YibuCredentials,
    *,
    model: str,
    timeout_seconds: float,
    max_retries: int,
    max_output_tokens: int,
    http_async_client: Any | None = None,
) -> ChatOpenAI:
    """Build a Yibu-compatible model using Chat Completions only."""
    return ChatOpenAI(
        model=model,
        api_key=credentials.api_key,
        base_url=credentials.base_url,
        use_responses_api=False,
        disable_streaming=True,
        timeout=timeout_seconds,
        max_retries=max_retries,
        max_completion_tokens=max_output_tokens,
        model_kwargs={"parallel_tool_calls": False},
        http_async_client=http_async_client,
    )
