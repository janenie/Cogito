import asyncio
from types import SimpleNamespace

from ai_host.attempt_state import AttemptContext, ReflectionMemory
from ai_host.agents.openai_responses import (
    ToolInteractionBudget,
    _chat_image_messages,
    _chat_tools,
    _run_chat_attempt,
    is_terminal_payload,
    parse_reflection_json,
)
from ai_host.config import HostConfig


def test_terminal_detection_for_game_over_payload():
    payload = {
        "status": "game_over",
        "outcome": "success",
        "reason": "cleanup_complete",
    }

    terminal = is_terminal_payload(payload)

    assert terminal == ("success", "cleanup_complete")


def test_terminal_detection_ignores_ready_observation():
    payload = {
        "status": "ready",
        "observation": {"observation_id": 1},
    }

    assert is_terminal_payload(payload) is None


def test_tool_interaction_budget_allows_calls_until_limit():
    budget = ToolInteractionBudget(max_interactions=2)

    assert budget.consume() is True
    assert budget.consume() is True
    assert budget.consume() is False
    assert budget.used == 2


def test_chat_attempt_fails_when_mcp_interaction_budget_is_exhausted(tmp_path):
    class FakeCompletions:
        async def create(self, **kwargs):
            tool_call = SimpleNamespace(
                id="call-1",
                function=SimpleNamespace(name="observe", arguments="{}"),
            )
            message = SimpleNamespace(content="", tool_calls=[tool_call])
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeClient:
        chat = SimpleNamespace(completions=FakeCompletions())

    class FakeMcpClient:
        def __init__(self):
            self.calls = 0

        async def openai_tools(self):
            return [{
                "name": "observe",
                "description": "Observe",
                "parameters": {"type": "object", "properties": {}},
            }]

        async def call_openai_tool(self, name, arguments):
            self.calls += 1
            return SimpleNamespace(
                payload={"status": "ready", "observation": {"observation_id": self.calls}},
                image_messages=[],
            )

    mcp_client = FakeMcpClient()

    result = asyncio.run(_run_chat_attempt(
        client=FakeClient(),
        config=HostConfig(
            run_dir=tmp_path,
            api_mode="chat",
            max_agent_turns=5,
            max_mcp_interactions=1,
        ),
        context=AttemptContext(
            attempt_id=1,
            max_attempts=3,
            scenario_id="daily_routine_cleanup",
            run_dir=tmp_path,
            reflection=ReflectionMemory(),
        ),
        mcp_client=mcp_client,
    ))

    assert result.outcome == "failure"
    assert result.reason == "max_mcp_interactions"
    assert result.steps_used == 1
    assert mcp_client.calls == 1


def test_parse_reflection_json_extracts_strategy():
    parsed = parse_reflection_json(
        '{"summary":"submitted too early",'
        '"mistakes":["did not check HUD"],'
        '"next_strategy":["check HUD before finishing"]}'
    )

    assert parsed == {
        "summary": "submitted too early",
        "mistakes": ["did not check HUD"],
        "next_strategy": ["check HUD before finishing"],
    }


def test_parse_reflection_json_falls_back_for_unstructured_text():
    parsed = parse_reflection_json("I failed.")

    assert parsed["summary"] == "I failed."
    assert "check HUD progress before finishing" in parsed["next_strategy"]


def test_chat_tools_convert_responses_tools():
    tools = _chat_tools([{
        "type": "function",
        "name": "observe",
        "description": "Observe",
        "parameters": {"type": "object", "properties": {}},
    }])

    assert tools == [{
        "type": "function",
        "function": {
            "name": "observe",
            "description": "Observe",
            "parameters": {"type": "object", "properties": {}},
        },
    }]


def test_chat_image_messages_convert_responses_images():
    messages = _chat_image_messages([{
        "role": "user",
        "content": [
            {"type": "input_text", "text": "image:"},
            {"type": "input_image", "image_url": "data:image/jpeg;base64,abc"},
        ],
    }])

    assert messages == [{
        "role": "user",
        "content": [
            {"type": "text", "text": "image:"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64,abc"},
            },
        ],
    }]
