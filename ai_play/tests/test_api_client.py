from types import SimpleNamespace

import pytest

import ai_play.api_client as api_client_module
from ai_play.api_client import ApiClient


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.arguments = None

    def create(self, **kwargs):
        self.arguments = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeOpenAI:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def config():
    test_key = "secret"
    return SimpleNamespace(
        base_url="https://example.invalid/v1",
        api_key=test_key,
        model="vision-model",
        request_timeout_seconds=12.5,
        api_max_retries=2,
    )


def test_decide_forwards_request_and_decodes_json():
    content = (
        '{"reason":"observe","memory_updates":[],"actions":'
        '[{"type":"wait","duration_ms":100}]}'
    )
    fake = FakeOpenAI(content)
    messages = [{"role": "user", "content": "state"}]

    decision = ApiClient(config(), client=fake).decide(messages)

    assert fake.chat.completions.arguments == {
        "model": "vision-model",
        "messages": messages,
        "timeout": 12.5,
    }
    assert decision == {
        "reason": "observe",
        "memory_updates": [],
        "actions": [{"type": "wait", "duration_ms": 100}],
    }


def test_decide_accepts_one_surrounding_json_fence():
    fake = FakeOpenAI('```json\n{"actions": []}\n```')

    assert ApiClient(config(), client=fake).decide([]) == {"actions": []}


def test_decide_does_not_search_prose_for_json():
    fake = FakeOpenAI('Here is the answer: {"actions": []}')

    with pytest.raises(ValueError):
        ApiClient(config(), client=fake).decide([])


def test_decide_rejects_non_text_content():
    fake = FakeOpenAI([{"type": "text", "text": "{}"}])

    with pytest.raises(ValueError, match="must be text JSON"):
        ApiClient(config(), client=fake).decide([])


def test_constructor_passes_bounded_retries_to_sdk(monkeypatch):
    arguments = {}

    def record_openai(**kwargs):
        arguments.update(kwargs)
        return FakeOpenAI("{}")

    monkeypatch.setattr(api_client_module, "OpenAI", record_openai)

    ApiClient(config())

    assert arguments["max_retries"] == 2
