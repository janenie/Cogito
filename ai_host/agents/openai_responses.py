from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ai_host.attempt_state import AttemptContext, AttemptResult
from ai_host.config import HostConfig
from ai_host.reflection import build_attempt_instructions


def is_terminal_payload(payload: dict[str, Any]) -> tuple[str, str] | None:
    status = payload.get("status")
    if status == "game_over":
        return str(payload.get("outcome", "unknown")), str(payload.get("reason", "unknown"))
    if status in {"stopped", "disconnected"}:
        return str(status), str(payload.get("reason", status))
    return None


@dataclass
class ToolInteractionBudget:
    max_interactions: int
    used: int = 0

    def consume(self) -> bool:
        if self.used >= self.max_interactions:
            return False
        self.used += 1
        return True


class OpenAIResponsesAgent:
    def __init__(self, config: HostConfig) -> None:
        self.config = config

    async def run_attempt(
        self,
        context: AttemptContext,
        mcp_client: object | None,
    ) -> AttemptResult:
        if mcp_client is None:
            return AttemptResult(
                attempt_id=context.attempt_id,
                outcome="unknown",
                reason="missing_mcp_client",
            )
        try:
            from openai import AsyncOpenAI
        except Exception as error:
            return AttemptResult(
                attempt_id=context.attempt_id,
                outcome="unknown",
                reason="openai_import_failed",
                summary=f"{type(error).__name__}: {error}",
            )

        tools = await mcp_client.openai_tools()
        client = AsyncOpenAI()
        if self.config.api_mode == "chat":
            return await _run_chat_attempt(
                client=client,
                config=self.config,
                context=context,
                mcp_client=mcp_client,
            )
        instructions = _agent_instructions(context)
        response_input: list[dict[str, Any]] = [{
            "role": "user",
            "content": [{
                "type": "input_text",
                "text": build_attempt_instructions(
                    scenario_id=context.scenario_id,
                    attempt_id=context.attempt_id,
                    max_attempts=context.max_attempts,
                    memory=context.reflection,
                ),
            }],
        }]
        previous_response_id: str | None = None
        budget = ToolInteractionBudget(self.config.max_mcp_interactions)

        for turn in range(1, self.config.max_agent_turns + 1):
            response = await client.responses.create(
                model=self.config.model,
                instructions=instructions,
                input=response_input,
                previous_response_id=previous_response_id,
                tools=tools,
                parallel_tool_calls=False,
                store=True,
            )
            previous_response_id = response.id
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return AttemptResult(
                    attempt_id=context.attempt_id,
                    outcome="unknown",
                    reason="agent_finished_without_terminal",
                    summary=response.output_text or "",
                    steps_used=turn,
                )
            response_input = []
            for call in calls:
                if not budget.consume():
                    return AttemptResult(
                        attempt_id=context.attempt_id,
                        outcome="failure",
                        reason="max_mcp_interactions",
                        steps_used=budget.used,
                    )
                result = await mcp_client.call_openai_tool(call.name, call.arguments)
                terminal = is_terminal_payload(result.payload)
                response_input.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result.payload, ensure_ascii=False),
                })
                response_input.extend(result.image_messages)
                if terminal is not None:
                    outcome, reason = terminal
                    reflection = {}
                    if outcome != "success":
                        reflection = await _request_reflection(
                            client=client,
                            model=self.config.model,
                            previous_response_id=previous_response_id,
                            outcome=outcome,
                            reason=reason,
                        )
                    return AttemptResult(
                        attempt_id=context.attempt_id,
                        outcome=outcome,
                        reason=reason,
                        summary=reflection.get("summary") or response.output_text or "",
                        mistakes=reflection.get("mistakes", []),
                        next_strategy=reflection.get("next_strategy", []),
                        steps_used=turn,
                    )
        return AttemptResult(
            attempt_id=context.attempt_id,
            outcome="unknown",
            reason="max_agent_turns",
            steps_used=self.config.max_agent_turns,
        )


def _agent_instructions(context: AttemptContext) -> str:
    return (
        "You are playing Cogito through MCP tools. Call briefing once, then observe, "
        "then act using the latest observation_id. Do not use hidden source code, "
        "node paths, previous exact coordinates, or puzzle answers. After a failure, "
        "summaries must be process-level strategies only. "
        f"This is attempt {context.attempt_id} of {context.max_attempts}."
    )


async def _run_chat_attempt(
    *,
    client: Any,
    config: HostConfig,
    context: AttemptContext,
    mcp_client: Any,
) -> AttemptResult:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _agent_instructions(context)},
        {
            "role": "user",
            "content": build_attempt_instructions(
                scenario_id=context.scenario_id,
                attempt_id=context.attempt_id,
                max_attempts=context.max_attempts,
                memory=context.reflection,
            ),
        },
    ]
    tools = _chat_tools(await mcp_client.openai_tools())
    budget = ToolInteractionBudget(config.max_mcp_interactions)
    for turn in range(1, config.max_agent_turns + 1):
        response = await client.chat.completions.create(
            model=config.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        tool_calls = list(message.tool_calls or [])
        if not tool_calls:
            return AttemptResult(
                attempt_id=context.attempt_id,
                outcome="unknown",
                reason="agent_finished_without_terminal",
                summary=message.content or "",
                steps_used=turn,
            )
        messages.append(_assistant_tool_call_message(message))
        for tool_call in tool_calls:
            if not budget.consume():
                return AttemptResult(
                    attempt_id=context.attempt_id,
                    outcome="failure",
                    reason="max_mcp_interactions",
                    steps_used=budget.used,
                )
            result = await mcp_client.call_openai_tool(
                tool_call.function.name,
                tool_call.function.arguments,
            )
            terminal = is_terminal_payload(result.payload)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result.payload, ensure_ascii=False),
            })
            messages.extend(_chat_image_messages(result.image_messages))
            if terminal is not None:
                outcome, reason = terminal
                reflection = {}
                if outcome != "success":
                    reflection = await _request_chat_reflection(
                        client=client,
                        model=config.model,
                        outcome=outcome,
                        reason=reason,
                    )
                return AttemptResult(
                    attempt_id=context.attempt_id,
                    outcome=outcome,
                    reason=reason,
                    summary=reflection.get("summary") or message.content or "",
                    mistakes=reflection.get("mistakes", []),
                    next_strategy=reflection.get("next_strategy", []),
                    steps_used=turn,
                )
    return AttemptResult(
        attempt_id=context.attempt_id,
        outcome="unknown",
        reason="max_agent_turns",
        steps_used=config.max_agent_turns,
    )


def _chat_tools(responses_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {"type": "object"}),
            },
        }
        for tool in responses_tools
    ]


def _assistant_tool_call_message(message: Any) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in (message.tool_calls or [])
        ],
    }


def _chat_image_messages(image_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for message in image_messages:
        content = []
        for item in message.get("content", []):
            if item.get("type") == "input_text":
                content.append({"type": "text", "text": item.get("text", "")})
            elif item.get("type") == "input_image":
                content.append({
                    "type": "image_url",
                    "image_url": {"url": item.get("image_url", "")},
                })
        if content:
            messages.append({"role": "user", "content": content})
    return messages


def parse_reflection_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return _fallback_reflection(text)
    if not isinstance(value, dict):
        return _fallback_reflection(text)
    return {
        "summary": str(value.get("summary", "")),
        "mistakes": [str(item) for item in value.get("mistakes", []) if str(item).strip()],
        "next_strategy": [
            str(item) for item in value.get("next_strategy", []) if str(item).strip()
        ],
    }


async def _request_reflection(
    *,
    client: Any,
    model: str,
    previous_response_id: str | None,
    outcome: str,
    reason: str,
) -> dict[str, Any]:
    prompt = (
        "The game attempt ended without success. Produce only JSON with keys "
        '"summary", "mistakes", and "next_strategy". Keep it process-level. '
        "Do not include coordinates, node paths, source code facts, hidden seeds, "
        "or exact previous object positions. "
        f"Outcome={outcome}; reason={reason}."
    )
    response = await client.responses.create(
        model=model,
        instructions="Return strict JSON only. No tools.",
        input=[{
            "role": "user",
            "content": [{"type": "input_text", "text": prompt}],
        }],
        previous_response_id=previous_response_id,
        tools=[],
        store=True,
    )
    return parse_reflection_json(response.output_text or "")


async def _request_chat_reflection(
    *,
    client: Any,
    model: str,
    outcome: str,
    reason: str,
) -> dict[str, Any]:
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Return strict JSON only."},
            {
                "role": "user",
                "content": (
                    "The game attempt ended without success. Produce only JSON with keys "
                    '"summary", "mistakes", and "next_strategy". Keep it process-level. '
                    "Do not include coordinates, node paths, source code facts, hidden seeds, "
                    "or exact previous object positions. "
                    f"Outcome={outcome}; reason={reason}."
                ),
            },
        ],
    )
    return parse_reflection_json(response.choices[0].message.content or "")


def _fallback_reflection(text: str) -> dict[str, Any]:
    summary = text.strip()[:500]
    return {
        "summary": summary,
        "mistakes": ["attempt ended without a structured reflection"],
        "next_strategy": [
            "check HUD progress before finishing",
            "search rooms systematically",
            "open fridge before assuming cleanup is complete",
        ],
    }
