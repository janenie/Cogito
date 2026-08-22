import asyncio
import importlib.util
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage


def _summary_response(observation_ids: list[int]) -> AIMessage:
    first, last = observation_ids[0], observation_ids[-1]
    return AIMessage(
        content=json.dumps(
            {
                "summary": {
                    "progress": f"Reviewed observations {first}-{last}.",
                    "key_facts": [f"Key fact from {first}-{last}."],
                    "unresolved": "Confirm the next required task object.",
                }
            }
        )
    )


def _observation(number: int) -> ToolMessage:
    return ToolMessage(
        content=[
            {
                "type": "image",
                "base64": f"rgb-{number}",
                "mime_type": "image/jpeg",
            },
            {
                "type": "image",
                "base64": f"depth-{number}",
                "mime_type": "image/png",
            },
        ],
        name="act",
        tool_call_id=f"call-{number}",
        id=f"message-{number}",
        artifact={
            "structured_content": {
                "status": "ready",
                "observation": {"observation_id": number},
            }
        },
    )


def _terminal(number: int) -> ToolMessage:
    return ToolMessage(
        content=[{"type": "text", "text": "game over"}],
        name="act",
        tool_call_id=f"terminal-call-{number}",
        id=f"terminal-message-{number}",
        artifact={
            "structured_content": {
                "status": "game_over",
                "observation": {"observation_id": number},
                "game_over": {"outcome": "failure", "reason": "max_requests"},
            }
        },
    )


class BlockingCaptionModel:
    def __init__(self) -> None:
        self.calls = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def ainvoke(self, messages):
        self.calls.append(messages)
        self.started.set()
        await self.release.wait()
        observation_ids = [
            int(block["text"].removeprefix("Observation "))
            for block in messages[-1].content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and block.get("text", "").startswith("Observation ")
        ]
        return _summary_response(observation_ids)


class ImmediateCaptionModel:
    def __init__(self) -> None:
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        observation_ids = [
            int(block["text"].removeprefix("Observation "))
            for block in messages[-1].content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and block.get("text", "").startswith("Observation ")
        ]
        return _summary_response(observation_ids)


class VerboseSummaryModel:
    async def ainvoke(self, _messages):
        return AIMessage(
            content=json.dumps(
                {
                    "summary": {
                        "progress": "p" * 1_000,
                        "key_facts": ["f" * 1_000 for _ in range(20)],
                        "unresolved": "u" * 1_000,
                    }
                }
            )
        )


class FailingCaptionModel:
    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, _messages):
        self.calls += 1
        raise TimeoutError("SECRET_PROVIDER_BODY")


class PayloadTooLargeError(RuntimeError):
    status_code = 413


class UnauthorizedError(RuntimeError):
    status_code = 401


class UnauthorizedCaptionModel:
    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, _messages):
        self.calls += 1
        raise UnauthorizedError("SECRET_AUTH_BODY")


class SplitCaptionModel(ImmediateCaptionModel):
    async def ainvoke(self, messages):
        observation_ids = [
            int(block["text"].removeprefix("Observation "))
            for block in messages[-1].content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and block.get("text", "").startswith("Observation ")
        ]
        self.calls.append(observation_ids)
        if len(observation_ids) > 5:
            raise PayloadTooLargeError("do not persist this body")
        return _summary_response(observation_ids)


@pytest.mark.asyncio
async def test_tenth_observation_starts_caption_without_blocking(
    tmp_path: Path,
):
    spec = importlib.util.find_spec("tools_langgraph_deepagents.captioning")
    assert spec is not None, "batch caption pipeline is not implemented"
    from tools_langgraph_deepagents.captioning import CaptionPipeline

    model = BlockingCaptionModel()
    pipeline = CaptionPipeline(
        model=model,
        store_path=tmp_path / "image_captions.json",
        retry_delays=(0, 0, 0),
    )

    await pipeline.prepare([_observation(number) for number in range(1, 10)])
    assert model.calls == []

    prepare = asyncio.create_task(
        pipeline.prepare(
            [_observation(number) for number in range(1, 11)]
        )
    )
    await asyncio.wait_for(model.started.wait(), timeout=1)
    await asyncio.wait_for(prepare, timeout=1)

    assert len(model.calls) == 1
    caption_prompt = model.calls[0][0].content
    assert '"progress"' in caption_prompt
    assert '"key_facts"' in caption_prompt
    assert '"unresolved"' in caption_prompt
    assert "one" in caption_prompt.lower()
    assert "summary" in caption_prompt.lower()
    assert "visible" in caption_prompt.lower()
    assert "guess" in caption_prompt.lower()
    assert "repeated" in caption_prompt.lower()
    model.release.set()
    await pipeline.aclose()


@pytest.mark.asyncio
async def test_twentieth_observation_waits_for_previous_caption(
    tmp_path: Path,
):
    from tools_langgraph_deepagents.captioning import CaptionPipeline

    model = BlockingCaptionModel()
    pipeline = CaptionPipeline(
        model=model,
        store_path=tmp_path / "image_captions.json",
        retry_delays=(0, 0, 0),
    )
    await pipeline.prepare(
        [_observation(number) for number in range(1, 11)]
    )
    await asyncio.wait_for(model.started.wait(), timeout=1)

    await asyncio.wait_for(
        pipeline.prepare(
            [_observation(number) for number in range(1, 20)]
        ),
        timeout=1,
    )
    boundary = asyncio.create_task(
        pipeline.prepare(
            [_observation(number) for number in range(1, 21)]
        )
    )
    await asyncio.sleep(0)
    assert not boundary.done()

    model.release.set()
    await asyncio.wait_for(boundary, timeout=1)
    await pipeline.aclose()


@pytest.mark.asyncio
async def test_completed_batch_summary_is_persisted_and_injected_once(
    tmp_path: Path,
):
    from tools_langgraph_deepagents.captioning import CaptionPipeline

    store_path = tmp_path / "image_captions.json"
    model = BlockingCaptionModel()
    pipeline = CaptionPipeline(
        model=model,
        store_path=store_path,
        retry_delays=(0, 0, 0),
    )
    await pipeline.prepare(
        [_observation(number) for number in range(1, 11)]
    )
    await asyncio.wait_for(model.started.wait(), timeout=1)
    boundary = asyncio.create_task(
        pipeline.prepare(
            [_observation(number) for number in range(1, 21)]
        )
    )
    model.release.set()
    prepared = await asyncio.wait_for(boundary, timeout=1)

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert stored["schema_version"] == 2
    assert stored["batches"][0]["status"] == "complete"
    assert stored["batches"][0]["summary"] == {
        "progress": "Reviewed observations 1-10.",
        "key_facts": ["Key fact from 1-10."],
        "unresolved": "Confirm the next required task object.",
    }
    injected = [
        block["text"]
        for message in prepared
        for block in message.content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and "visual_history_summary" in block.get("text", "")
    ]
    assert len(injected) == 1
    assert "Reviewed observations 1-10" in injected[0]
    assert "Key fact from 1-10" in injected[0]
    assert "visual_history_summary" not in json.dumps(
        prepared[0].content
    )
    assert "visual_history_summary" in json.dumps(
        prepared[9].content
    )
    await pipeline.aclose()


@pytest.mark.asyncio
async def test_twentieth_observation_starts_second_caption_batch(
    tmp_path: Path,
):
    from tools_langgraph_deepagents.captioning import CaptionPipeline

    model = ImmediateCaptionModel()
    pipeline = CaptionPipeline(
        model=model,
        store_path=tmp_path / "image_captions.json",
        retry_delays=(0, 0, 0),
    )
    await pipeline.prepare(
        [_observation(number) for number in range(1, 11)]
    )
    await asyncio.sleep(0)
    await pipeline.prepare(
        [_observation(number) for number in range(1, 21)]
    )
    await pipeline.aclose()

    assert len(model.calls) == 2
    second_ids = [
        block["text"]
        for block in model.calls[1][-1].content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    assert second_ids == [
        f"Observation {number}" for number in range(11, 21)
    ]


@pytest.mark.asyncio
async def test_batch_summary_is_hard_capped_before_storage_and_injection(
    tmp_path: Path,
):
    from tools_langgraph_deepagents.captioning import CaptionPipeline

    store_path = tmp_path / "image_captions.json"
    pipeline = CaptionPipeline(
        model=VerboseSummaryModel(),
        store_path=store_path,
    )

    prepared = await pipeline.prepare(
        [_observation(number) for number in range(1, 11)]
    )
    await pipeline.aclose()
    prepared = await pipeline.prepare(prepared)

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    summary = stored["batches"][0]["summary"]
    assert len(summary["progress"]) == 140
    assert len(summary["key_facts"]) == 4
    assert all(len(fact) == 80 for fact in summary["key_facts"])
    assert len(summary["unresolved"]) == 140
    injected = [
        block["text"]
        for block in prepared[-1].content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and "visual_history_summary" in block.get("text", "")
    ]
    assert len(injected) == 1
    assert len(injected[0]) < 800


@pytest.mark.asyncio
async def test_caption_retry_exhaustion_fails_closed_at_boundary(
    tmp_path: Path,
):
    from tools_langgraph_deepagents import captioning

    assert hasattr(captioning, "CaptionPipelineError")
    CaptionPipeline = captioning.CaptionPipeline
    CaptionPipelineError = captioning.CaptionPipelineError

    store_path = tmp_path / "image_captions.json"
    model = FailingCaptionModel()
    pipeline = CaptionPipeline(
        model=model,
        store_path=store_path,
        retry_delays=(0, 0, 0),
    )
    await pipeline.prepare(
        [_observation(number) for number in range(1, 11)]
    )
    await asyncio.sleep(0)

    with pytest.raises(CaptionPipelineError, match="caption_timeout"):
        await pipeline.prepare(
            [_observation(number) for number in range(1, 21)]
        )

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    failed = stored["batches"][0]
    assert model.calls == 4
    assert failed["status"] == "failed"
    assert failed["attempts"] == 4
    assert failed["last_error"] == "caption_timeout"
    assert "SECRET_PROVIDER_BODY" not in store_path.read_text(
        encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_terminal_skips_partial_batch_without_caption_call(
    tmp_path: Path,
):
    from tools_langgraph_deepagents.captioning import CaptionPipeline

    store_path = tmp_path / "image_captions.json"
    model = ImmediateCaptionModel()
    pipeline = CaptionPipeline(model=model, store_path=store_path)

    await pipeline.prepare(
        [
            *[_observation(number) for number in range(1, 10)],
            _terminal(9),
        ]
    )

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert model.calls == []
    assert stored["batches"] == [
        {
            "batch_id": "message-1",
            "status": "skipped_terminal",
            "attempts": 0,
            "observations": [
                {
                    "message_id": f"message-{number}",
                    "observation_id": number,
                }
                for number in range(1, 10)
            ],
            "last_error": None,
        }
    ]
    await pipeline.aclose()


@pytest.mark.asyncio
async def test_payload_limit_splits_caption_batch_in_half(tmp_path: Path):
    from tools_langgraph_deepagents.captioning import CaptionPipeline

    store_path = tmp_path / "image_captions.json"
    model = SplitCaptionModel()
    pipeline = CaptionPipeline(
        model=model,
        store_path=store_path,
        retry_delays=(0, 0, 0),
    )

    await pipeline.prepare(
        [_observation(number) for number in range(1, 11)]
    )
    await pipeline.aclose()

    assert model.calls == [
        list(range(1, 11)),
        list(range(1, 6)),
        list(range(6, 11)),
    ]
    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert stored["batches"][0]["status"] == "complete"
    assert len(stored["batches"][0]["observations"]) == 10
    assert stored["batches"][0]["summary"] == {
        "progress": (
            "Reviewed observations 1-5. "
            "Reviewed observations 6-10."
        ),
        "key_facts": [
            "Key fact from 1-5.",
            "Key fact from 6-10.",
        ],
        "unresolved": "Confirm the next required task object.",
    }
    assert "do not persist this body" not in store_path.read_text(
        encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_auth_failure_does_not_retry(tmp_path: Path):
    from tools_langgraph_deepagents.captioning import (
        CaptionPipeline,
        CaptionPipelineError,
    )

    store_path = tmp_path / "image_captions.json"
    model = UnauthorizedCaptionModel()
    pipeline = CaptionPipeline(
        model=model,
        store_path=store_path,
        retry_delays=(0, 0, 0),
    )
    await pipeline.prepare(
        [_observation(number) for number in range(1, 11)]
    )
    await asyncio.sleep(0)

    with pytest.raises(CaptionPipelineError, match="caption_http_401"):
        await pipeline.prepare(
            [_observation(number) for number in range(1, 21)]
        )

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert model.calls == 1
    assert stored["batches"][0]["attempts"] == 1
    assert "SECRET_AUTH_BODY" not in store_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_interrupted_batch_is_retried_after_resume(tmp_path: Path):
    from tools_langgraph_deepagents.captioning import CaptionPipeline

    store_path = tmp_path / "image_captions.json"
    store_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "batches": [
                    {
                        "batch_id": "message-1",
                        "status": "in_progress",
                        "attempts": 1,
                        "observations": [
                            {
                                "message_id": f"message-{number}",
                                "observation_id": number,
                            }
                            for number in range(1, 11)
                        ],
                        "last_error": "caption_timeout",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    model = ImmediateCaptionModel()
    pipeline = CaptionPipeline(model=model, store_path=store_path)

    await pipeline.prepare(
        [_observation(number) for number in range(1, 11)]
    )
    await pipeline.aclose()

    stored = json.loads(store_path.read_text(encoding="utf-8"))
    assert len(model.calls) == 1
    assert len(stored["batches"]) == 1
    assert stored["batches"][0]["status"] == "complete"


@pytest.mark.asyncio
async def test_legacy_per_observation_captions_resume_as_one_short_summary(
    tmp_path: Path,
):
    from tools_langgraph_deepagents.captioning import CaptionPipeline

    store_path = tmp_path / "image_captions.json"
    store_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "batches": [
                    {
                        "batch_id": "message-1",
                        "status": "complete",
                        "attempts": 1,
                        "observations": [
                            {
                                "message_id": f"message-{number}",
                                "observation_id": number,
                                "rgb": "repeated visual description",
                                "depth": "repeated depth description",
                                "task_facts": [
                                    "Archive keypad is visible.",
                                    "HUD displays unchanged stats.",
                                ],
                            }
                            for number in range(1, 11)
                        ],
                        "last_error": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    model = ImmediateCaptionModel()
    pipeline = CaptionPipeline(model=model, store_path=store_path)

    prepared = await pipeline.prepare(
        [_observation(number) for number in range(1, 11)]
    )

    assert model.calls == []
    injected = [
        block["text"]
        for message in prepared
        for block in message.content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and "visual_history_summary" in block.get("text", "")
    ]
    assert len(injected) == 1
    assert "Archive keypad is visible" in injected[0]
    assert "HUD displays" not in injected[0]
