import pytest

from ai_play.workflow_memory import SessionWorkflowMemory, WorkflowMemoryError


def valid_candidate():
    return {
        "goal_pattern": "依据公开线索逐步完成当前任务",
        "workflow": [{
            "step": "先确认任务入口物",
            "precondition": "尚未获得第一条公开任务线索",
            "success_signal": "观察中出现下一阶段目标",
        }],
        "landmarks": [{
            "relation": "先建立出生区域与主要地标的相对方向",
        }],
        "avoid": ["没有交互提示时不要重复 interact"],
    }


def test_first_attempt_reads_empty_memory():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")

    assert memory.read("find_contract") == {
        "status": "ready",
        "scope": "current_orchestrator_session",
        "scenario": "find_contract",
        "version": 0,
        "completed_runs": 0,
        "memory": None,
    }


def test_read_requires_a_started_scenario():
    memory = SessionWorkflowMemory()

    with pytest.raises(WorkflowMemoryError, match="scenario_not_ready"):
        memory.read("find_contract")


def test_session_rejects_a_different_scenario():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")

    with pytest.raises(WorkflowMemoryError, match="scenario_mismatch"):
        memory.read("garden_watering")


def test_success_promotes_all_candidate_sections():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")

    result = memory.update(valid_candidate())

    assert result == {
        "status": "updated",
        "version": 1,
        "accepted": {
            "workflow": 1,
            "landmarks": 1,
            "avoid": 1,
        },
    }
    snapshot = memory.read("find_contract")
    assert snapshot["completed_runs"] == 1
    assert snapshot["memory"]["goal_pattern"] == "依据公开线索逐步完成当前任务"
    assert snapshot["memory"]["workflow"][0]["step"] == "先确认任务入口物"
    assert snapshot["memory"]["confidence"] == 1.0


def test_failure_only_promotes_avoid():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("failure", "max_requests")

    result = memory.update(valid_candidate())

    assert result["accepted"] == {
        "workflow": 0,
        "landmarks": 0,
        "avoid": 1,
    }
    snapshot = memory.read("find_contract")["memory"]
    assert snapshot["goal_pattern"] is None
    assert snapshot["workflow"] == []
    assert snapshot["landmarks"] == []
    assert snapshot["avoid"] == ["没有交互提示时不要重复 interact"]
    assert snapshot["confidence"] == 0.0


@pytest.mark.parametrize("status", ["stopped", "disconnected", "shutdown"])
def test_ineligible_attempt_does_not_learn(status):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt(status, "bridge_disconnected")

    with pytest.raises(WorkflowMemoryError, match="attempt_not_eligible"):
        memory.update(valid_candidate())

    snapshot = memory.read("find_contract")
    assert snapshot["version"] == 0
    assert snapshot["completed_runs"] == 0


def test_ineligible_attempt_does_not_block_a_later_success():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("disconnected", "bridge_disconnected")
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")

    assert memory.update(valid_candidate())["version"] == 1
    assert memory.read("find_contract")["completed_runs"] == 1


def test_completed_attempt_can_update_after_next_attempt_starts():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    memory.start_attempt("find_contract")

    assert memory.update(valid_candidate())["version"] == 1


def test_update_while_only_attempt_is_in_progress_is_rejected():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")

    with pytest.raises(WorkflowMemoryError, match="attempt_in_progress"):
        memory.update(valid_candidate())


def test_attempt_can_only_be_consumed_once():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    memory.update(valid_candidate())

    with pytest.raises(WorkflowMemoryError, match="attempt_already_updated"):
        memory.update(valid_candidate())


def test_normalized_duplicates_are_not_appended_twice():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    memory.update(valid_candidate())
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    duplicate = valid_candidate()
    duplicate["avoid"] = ["  没有交互提示时不要重复 interact  "]

    result = memory.update(duplicate)

    assert result["accepted"] == {
        "workflow": 0,
        "landmarks": 0,
        "avoid": 0,
    }
    snapshot = memory.read("find_contract")["memory"]
    assert len(snapshot["workflow"]) == 1
    assert len(snapshot["landmarks"]) == 1
    assert len(snapshot["avoid"]) == 1
    assert snapshot["confidence"] == 1.0


def test_read_returns_a_copy():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    memory.update(valid_candidate())

    first = memory.read("find_contract")
    first["memory"]["workflow"][0]["step"] = "被调用方修改"

    assert (
        memory.read("find_contract")["memory"]["workflow"][0]["step"]
        == "先确认任务入口物"
    )


@pytest.mark.parametrize(
    "unsafe",
    [
        "密码是 123456",
        "移动到 (12.4, 0, -3.2)",
        "向前走 100ms 然后右转 15 度",
        "读取 /tmp/private/answer.txt",
        "读取 C:\\secret\\answer.txt",
        "读取 res://game_script/answer.gd",
        "查看 https://example.test/solution",
        "参考 game_script 里的答案",
        "参考 code_read 的开发者笔记",
        "参考 tests/test_answer.py",
        "读取 Node/ArchiveDoor 节点路径",
    ],
)
def test_rejects_non_reusable_or_internal_memory(unsafe):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    candidate = valid_candidate()
    candidate["avoid"] = [unsafe]

    with pytest.raises(WorkflowMemoryError, match="invalid_workflow_memory"):
        memory.update(candidate)

    assert memory.read("find_contract")["version"] == 0
    candidate["avoid"] = ["没有提示时先重新观察"]
    assert memory.update(candidate)["version"] == 1


@pytest.mark.parametrize(
    "candidate",
    [
        {},
        {**valid_candidate(), "extra": "not allowed"},
        {**valid_candidate(), "workflow": "not a list"},
        {**valid_candidate(), "workflow": [{}]},
        {**valid_candidate(), "landmarks": [{"relation": ""}]},
        {**valid_candidate(), "avoid": []},
        {**valid_candidate(), "avoid": ["含有\u0000控制字符"]},
        {**valid_candidate(), "workflow": valid_candidate()["workflow"] * 9},
        {**valid_candidate(), "landmarks": valid_candidate()["landmarks"] * 9},
        {**valid_candidate(), "avoid": valid_candidate()["avoid"] * 13},
    ],
)
def test_rejects_invalid_candidate_shapes(candidate):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")

    with pytest.raises(WorkflowMemoryError, match="invalid_workflow_memory"):
        memory.update(candidate)

    assert memory.read("find_contract")["version"] == 0


def test_candidate_text_is_unicode_normalized():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    candidate = valid_candidate()
    candidate["avoid"] = ["不要遗漏 Cafe\u0301 标牌"]

    memory.update(candidate)

    assert memory.read("find_contract")["memory"]["avoid"] == [
        "不要遗漏 Café 标牌",
    ]
