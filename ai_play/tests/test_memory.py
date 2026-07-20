import json
import math
from pathlib import Path

import pytest

from ai_play.memory import MemoryStore


def _write_memory(path, **overrides):
    data = MemoryStore.empty().to_prompt_dict()
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")


def _step(observation_id):
    return {
        "observation_id": observation_id,
        "reason": "wait",
        "actions": [{"type": "wait", "duration_ms": 50}],
        "last_action_results": [{"status": "completed", "type": "wait"}],
    }


def test_memory_starts_empty():
    assert MemoryStore.empty().to_prompt_dict() == {
        "working_memory": [], "facts": [], "spatial_memory": [],
        "task_state": {"goal": "", "questions": [], "hypotheses": [], "failures": []},
    }


def test_fact_requires_runtime_source():
    store = MemoryStore.empty()
    store.apply_updates([{"kind": "fact", "text": "A visible clue", "source": "observation:4", "confidence": 0.8}], 4)
    assert store.facts[0]["text"] == "A visible clue"
    store.apply_updates([{"kind": "fact", "text": "Hidden answer", "source": "developer file", "confidence": 1}], 5)
    assert len(store.facts) == 1


def test_working_memory_is_bounded():
    store = MemoryStore.empty()
    for index in range(12):
        store.record_step(_step(index))
    assert len(store.working_memory) == 8


def test_updates_accept_only_supported_kinds():
    store = MemoryStore.empty()
    store.apply_updates(
        [
            {
                "kind": "landmark", "text": "A marked doorway",
                "source": "observation:2", "confidence": 0.8,
            },
            {"kind": "goal", "text": "Reach the doorway"},
            {"kind": "question", "text": "Is it open?", "confidence": 0.5},
            {"kind": "hypothesis", "text": "The doorway may open", "confidence": 0.5},
            {"kind": "failure", "text": "First attempt failed", "confidence": 1.0},
            {"kind": "route", "text": "Use a hidden shortcut"},
        ],
        2,
    )

    assert [entry["text"] for entry in store.spatial_memory] == ["A marked doorway"]
    assert store.task_state["goal"] == "Reach the doorway"
    assert [entry["text"] for entry in store.task_state["questions"]] == ["Is it open?"]
    assert [entry["text"] for entry in store.task_state["hypotheses"]] == ["The doorway may open"]
    assert [entry["text"] for entry in store.task_state["failures"]] == ["First attempt failed"]


def test_landmark_requires_current_runtime_source():
    store = MemoryStore.empty()
    store.apply_updates(
        [{
            "kind": "landmark", "text": "Old marker",
            "source": "observation:1", "confidence": 0.5,
        }],
        2,
    )
    assert store.spatial_memory == []


def test_update_text_over_300_characters_is_rejected():
    store = MemoryStore.empty()
    store.apply_updates(
        [{"kind": "question", "text": "x" * 301, "confidence": 0.5}],
        1,
    )
    assert store.task_state["questions"] == []


def test_memory_collections_are_bounded():
    store = MemoryStore.empty()
    store.apply_updates(
        [
            *[
                    {
                        "kind": "fact", "text": f"fact {index}",
                        "source": "observation:7", "confidence": 0.5,
                    }
                for index in range(65)
            ],
            *[
                    {
                        "kind": "landmark", "text": f"landmark {index}",
                        "source": "observation:7", "confidence": 0.5,
                    }
                for index in range(49)
            ],
            *[
                    {"kind": kind, "text": f"{kind} {index}", "confidence": 0.5}
                for kind in ("question", "hypothesis", "failure")
                for index in range(25)
            ],
        ],
        7,
    )

    assert len(store.facts) == 64
    assert len(store.spatial_memory) == 48
    assert len(store.task_state["questions"]) == 24
    assert len(store.task_state["hypotheses"]) == 24
    assert len(store.task_state["failures"]) == 24


def test_duplicate_keeps_the_higher_confidence_entry():
    store = MemoryStore.empty()
    store.apply_updates(
        [{"kind": "fact", "text": "  Visible   Clue ", "source": "observation:3", "confidence": 0.2}],
        3,
    )
    store.apply_updates(
        [{"kind": "fact", "text": "visible clue", "source": "observation:4", "confidence": 0.9}],
        4,
    )

    assert len(store.facts) == 1
    assert store.facts[0]["text"] == "visible clue"
    assert store.facts[0]["confidence"] == 0.9


def test_save_atomically_round_trips_memory(tmp_path, monkeypatch):
    store = MemoryStore.empty()
    store.apply_updates(
        [{"kind": "fact", "text": "Observed clue", "source": "observation:9", "confidence": 0.7}],
        9,
    )
    store.record_step(_step(9))
    path = tmp_path / "memory.json"
    replace_calls = []
    original_replace = Path.replace

    def record_replace(source, target):
        replace_calls.append((source, Path(target)))
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", record_replace)
    store.save(path)

    assert MemoryStore.load(path).to_prompt_dict() == store.to_prompt_dict()
    assert len(replace_calls) == 1
    assert replace_calls[0][0].parent == path.parent
    assert replace_calls[0][0] != path
    assert replace_calls[0][1] == path
    assert list(tmp_path.iterdir()) == [path]


def test_load_missing_file_returns_empty_memory(tmp_path):
    assert MemoryStore.load(tmp_path / "missing.json").to_prompt_dict() == MemoryStore.empty().to_prompt_dict()


@pytest.mark.parametrize("contents", ["not json", "[]", '{"working_memory": []}'])
def test_load_rejects_malformed_data(tmp_path, contents):
    path = tmp_path / "memory.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        MemoryStore.load(path)


@pytest.mark.parametrize(
    ("collection", "kind", "source"),
    [
        ("facts", "fact", None),
        ("facts", "fact", "developer file"),
        ("spatial_memory", "landmark", "observation:-1"),
    ],
)
def test_load_rejects_non_runtime_sources(tmp_path, collection, kind, source):
    path = tmp_path / "memory.json"
    entry = {"kind": kind, "text": "Observed at runtime", "confidence": 0.5}
    if source is not None:
        entry["source"] = source
    _write_memory(path, **{collection: [entry]})

    with pytest.raises(ValueError):
        MemoryStore.load(path)


@pytest.mark.parametrize(
    ("collection", "entries"),
    [
        (
            "facts",
            [
                {
                    "kind": "fact", "text": "Visible  Clue",
                    "source": "observation:1", "confidence": 0.5,
                },
                {
                    "kind": "fact", "text": " visible clue ",
                    "source": "observation:2", "confidence": 0.5,
                },
            ],
        ),
        (
            "questions",
            [
                {"kind": "question", "text": "Is it open?", "confidence": 0.5},
                {"kind": "question", "text": " is it OPEN? ", "confidence": 0.5},
            ],
        ),
    ],
)
def test_load_rejects_normalized_duplicates(tmp_path, collection, entries):
    path = tmp_path / "memory.json"
    if collection == "facts":
        _write_memory(path, facts=entries)
    else:
        data = MemoryStore.empty().to_prompt_dict()
        data["task_state"][collection] = entries
        path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError):
        MemoryStore.load(path)


@pytest.mark.parametrize("text", ["   ", "x" * 301])
def test_load_rejects_invalid_entry_text(tmp_path, text):
    path = tmp_path / "memory.json"
    _write_memory(
        path,
        facts=[{
            "kind": "fact", "text": text,
            "source": "observation:1", "confidence": 0.5,
        }],
    )

    with pytest.raises(ValueError):
        MemoryStore.load(path)


def test_load_rejects_oversized_optional_working_memory_text(tmp_path):
    path = tmp_path / "memory.json"
    _write_memory(path, working_memory=[{"observation_id": 1, "text": "x" * 301}])

    with pytest.raises(ValueError):
        MemoryStore.load(path)


def test_load_allows_exact_recorded_step(tmp_path):
    path = tmp_path / "memory.json"
    step = {
        "observation_id": 1,
        "reason": "move",
        "actions": [{"type": "wait", "duration_ms": 50}],
        "last_action_results": [{"status": "completed", "type": "wait"}],
    }
    _write_memory(path, working_memory=[step])

    assert MemoryStore.load(path).working_memory == [step]


def test_record_step_rejects_arbitrary_observation_payload():
    store = MemoryStore.empty()

    with pytest.raises(ValueError):
        store.record_step({
            "observation_id": 1,
            "reason": "move",
            "actions": [{"type": "wait", "duration_ms": 50}],
            "last_action_results": [],
            "image": {"base64": "must-not-persist"},
        })

    assert store.working_memory == []


def test_load_rejects_arbitrary_working_memory_payload(tmp_path):
    path = tmp_path / "memory.json"
    _write_memory(path, working_memory=[{
        "observation_id": 1,
        "reason": "move",
        "actions": [{"type": "wait", "duration_ms": 50}],
        "last_action_results": [],
        "observation": {"image": "must-not-load"},
    }])

    with pytest.raises(ValueError):
        MemoryStore.load(path)


@pytest.mark.parametrize(
    "result",
    [
        {"status": "blocked", "type": "move"},
        {"status": "blocked", "type": "sprint"},
        {"status": "stopped", "type": "stop"},
    ],
)
def test_working_memory_accepts_exact_blocked_and_stopped_results(result):
    store = MemoryStore.empty()
    step = _step(1)
    step["last_action_results"] = [result]

    store.record_step(step)

    assert store.working_memory[0]["last_action_results"] == [result]


@pytest.mark.parametrize(
    "result",
    [
        {"status": "blocked", "type": "look"},
        {"status": "stopped", "type": "move"},
        {"status": "blocked", "type": "move", "reason": "extra"},
    ],
)
def test_working_memory_rejects_invalid_blocked_and_stopped_results(result):
    store = MemoryStore.empty()
    step = _step(1)
    step["last_action_results"] = [result]

    with pytest.raises(ValueError):
        store.record_step(step)


@pytest.mark.parametrize(
    ("collection", "kind", "limit"),
    [
        ("facts", "fact", 64),
        ("spatial_memory", "landmark", 48),
    ],
)
def test_load_rejects_over_capacity_memory_collections(
    tmp_path,
    collection,
    kind,
    limit,
):
    path = tmp_path / "memory.json"
    entries = [
        {
            "kind": kind,
            "text": f"entry {index}",
            "source": f"observation:{index}",
            "confidence": 0.5,
        }
        for index in range(limit + 1)
    ]
    _write_memory(path, **{collection: entries})

    with pytest.raises(ValueError):
        MemoryStore.load(path)


@pytest.mark.parametrize("collection", ["questions", "hypotheses", "failures"])
def test_load_rejects_over_capacity_task_collections(tmp_path, collection):
    path = tmp_path / "memory.json"
    data = MemoryStore.empty().to_prompt_dict()
    kind = collection[:-1] if collection != "hypotheses" else "hypothesis"
    data["task_state"][collection] = [
        {"kind": kind, "text": f"entry {index}", "confidence": 0.5}
        for index in range(25)
    ]
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError):
        MemoryStore.load(path)


@pytest.mark.parametrize("confidence", [math.nan, math.inf, -0.01, 1.01, True])
def test_invalid_update_confidence_is_omitted(confidence):
    store = MemoryStore.empty()

    store.apply_updates(
        [{
            "kind": "fact", "text": "Visible clue",
            "source": "observation:1", "confidence": confidence,
        }],
        1,
    )

    assert store.facts == []


@pytest.mark.parametrize("confidence", [math.nan, math.inf, -0.01, 1.01, True])
def test_load_rejects_invalid_confidence(tmp_path, confidence):
    path = tmp_path / "memory.json"
    _write_memory(
        path,
        facts=[{
            "kind": "fact", "text": "Visible clue",
            "source": "observation:1", "confidence": confidence,
        }],
    )

    with pytest.raises(ValueError):
        MemoryStore.load(path)


def test_save_disallows_nonstandard_nan(tmp_path):
    store = MemoryStore.empty()
    store.facts.append({
        "kind": "fact", "text": "Visible clue",
        "source": "observation:1", "confidence": math.nan,
    })

    with pytest.raises(ValueError):
        store.save(tmp_path / "memory.json")


@pytest.mark.parametrize(
    "entry",
    [
        {"kind": "fact", "text": "Seen", "source": "observation:1"},
        {
            "kind": "fact", "text": "Seen", "source": "observation:1",
            "confidence": 0.5, "extra": {"nested": "payload"},
        },
        {"kind": "question", "text": "Why?", "confidence": 0.5, "source": "extra"},
        {"kind": "question", "text": "bad\ntext", "confidence": 0.5},
        {
            "kind": "fact", "text": "Seen", "source": "observation:" + "1" * 65,
            "confidence": 0.5,
        },
    ],
)
def test_load_rejects_nonexact_persisted_entries(tmp_path, entry):
    path = tmp_path / "memory.json"
    if entry["kind"] == "fact":
        _write_memory(path, facts=[entry])
    else:
        data = MemoryStore.empty().to_prompt_dict()
        data["task_state"]["questions"] = [entry]
        path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError):
        MemoryStore.load(path)
