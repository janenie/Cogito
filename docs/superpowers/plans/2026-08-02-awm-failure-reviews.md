# AWM Failure Reviews Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded failure reviews to session-scoped AWM so a later play can reflect on a failed attempt, validate reusable optimizations against fresh evidence, and adjust its plan without retaining randomized answers or failed routes.

**Architecture:** Extend `SessionWorkflowMemory` with an optional validated failure-review candidate and a three-entry in-memory review queue. The MCP layer keeps the new field optional for old clients and injects the trusted terminal reason through the memory lifecycle; the orchestrator prompt teaches the producer/consumer reflection loop. Existing privacy validation, attempt eligibility, confidence calculation, and trajectory isolation remain authoritative.

**Tech Stack:** Python 3.12, FastMCP, pytest, existing Cogito AI Play supervisor/orchestrator, Markdown documentation.

---

## File Structure and Boundaries

- Modify `ai_play/src/ai_play/workflow_memory.py`: own review validation, trusted outcome compatibility, bounded retention, deduplication, and snapshot output.
- Modify `ai_play/tests/test_workflow_memory.py`: unit-test the memory contract independently from MCP and Godot.
- Modify `ai_play/src/ai_play/mcp_server.py`: expose the optional public argument and pass a complete candidate to the memory component.
- Modify `ai_play/tests/test_mcp_server.py`: test schema compatibility, trusted reason injection, result shape, and trajectory isolation.
- Modify `tools/ai_play_codex_orchestrator.py`: teach AWM-enabled players to produce and consume reviews; leave disabled-AWM behavior unchanged.
- Modify `tests/test_ai_play_codex_orchestrator.py`: pin the reflection prompt contract.
- Modify `ai_play/README.md` and `docs/wiki/ai-play/system-guide.md`: document the public shape, lifecycle, privacy, and multi-run reflection behavior.
- Do not modify `GameSession`, `TrajectoryLogger`, Godot scripts/scenes, request limits, or supervisor retry policy.

The worktree already contains unrelated user changes, including separate hunks in both documentation files. Never stage those hunks. Before every commit, inspect `git diff --cached`; use `git add -p` for the two documentation files and confirm the staged patch contains only AWM failure-review text.

### Task 1: Validate the Optional Failure-Review Candidate

**Files:**
- Modify: `ai_play/tests/test_workflow_memory.py:1-252`
- Modify: `ai_play/src/ai_play/workflow_memory.py:10-15,197-270`

- [ ] **Step 1: Add test helpers and failing validation tests**

Import `validate_workflow_candidate`, add `"failure_review": None` to the existing `valid_candidate()`, and add:

```python
def valid_failure_review(label="目标交互阶段"):
    return {
        "stage": label,
        "bottlenecks": ["在相似交互物之间反复判断"],
        "optimizations": ["先组合验证环境名称与目标物特征"],
    }


def test_validates_and_normalizes_failure_review():
    candidate = valid_candidate()
    candidate["failure_review"] = {
        "stage": "  接近 Cafe\u0301 目标  ",
        "bottlenecks": ["  重复检查相同候选  "],
        "optimizations": ["先确认环境特征", "为最终交互保留请求"],
    }

    safe = validate_workflow_candidate(candidate)

    assert safe["failure_review"] == {
        "stage": "接近 Café 目标",
        "bottlenecks": ["重复检查相同候选"],
        "optimizations": ["先确认环境特征", "为最终交互保留请求"],
    }


@pytest.mark.parametrize(
    "review",
    [
        {},
        {"stage": "阶段", "bottlenecks": ["瓶颈"], "optimizations": ["优化"], "extra": "x"},
        {"stage": "阶段", "bottlenecks": [], "optimizations": ["优化"]},
        {"stage": "阶段", "bottlenecks": ["瓶颈"] * 4, "optimizations": ["优化"]},
        {"stage": "阶段", "bottlenecks": ["瓶颈"], "optimizations": []},
        {"stage": "阶段", "bottlenecks": ["瓶颈"], "optimizations": ["优化"] * 5},
    ],
)
def test_rejects_invalid_failure_review_shapes(review):
    candidate = valid_candidate()
    candidate["failure_review"] = review

    with pytest.raises(WorkflowMemoryError, match="invalid_workflow_memory"):
        validate_workflow_candidate(candidate)
```

Extend the existing unsafe-text parameterization so each unsafe string is also rejected when placed in `stage`, one `bottlenecks` item, and one `optimizations` item. Keep a `failure_review: None` case to prove the internal candidate accepts old behavior.

- [ ] **Step 2: Run the new validation tests and verify they fail**

Run:

```bash
.venv/bin/python3 -m pytest ai_play/tests/test_workflow_memory.py \
  -k 'failure_review and (validates or shapes or unsafe)' -q
```

Expected: FAIL because the exact candidate keys and review validator do not exist yet.

- [ ] **Step 3: Implement the minimal review validator**

In `workflow_memory.py`, extend the exact candidate schema and add exact review keys:

```python
_CANDIDATE_KEYS = {
    "goal_pattern",
    "workflow",
    "landmarks",
    "avoid",
    "failure_review",
}
_FAILURE_REVIEW_KEYS = {"stage", "bottlenecks", "optimizations"}
```

Add a focused validator that reuses `_normalize_text` and `_validate_text_list`:

```python
def _validate_failure_review(value: object) -> dict | None:
    if value is None:
        return None
    _require_exact_dict(value, _FAILURE_REVIEW_KEYS)
    return {
        "stage": _normalize_text(value["stage"], max_length=240),
        "bottlenecks": _validate_text_list(
            value["bottlenecks"],
            max_items=3,
            require_items=True,
        ),
        "optimizations": _validate_text_list(
            value["optimizations"],
            max_items=4,
            require_items=True,
        ),
    }
```

Call it from `validate_workflow_candidate()` and include the normalized value in the returned candidate. Do not add a second privacy filter: all model-authored review strings must pass the existing `_normalize_text` boundary.

- [ ] **Step 4: Run the focused and complete memory tests**

```bash
.venv/bin/python3 -m pytest ai_play/tests/test_workflow_memory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit only the validation changes**

```bash
git add ai_play/src/ai_play/workflow_memory.py \
  ai_play/tests/test_workflow_memory.py
git diff --cached --check
git diff --cached
git commit -m "feat(ai-play): validate AWM failure reviews"
```

### Task 2: Promote Trusted Failure Reviews and Retain the Latest Three

**Files:**
- Modify: `ai_play/tests/test_workflow_memory.py`
- Modify: `ai_play/src/ai_play/workflow_memory.py:73-82,127-194,302-308`

- [ ] **Step 1: Write failing outcome and snapshot tests**

Update all exact `accepted` assertions to include `"failure_reviews": 0`, then add:

```python
def finish_failure(memory, review, reason="max_requests"):
    memory.start_attempt("find_contract")
    memory.finish_attempt("failure", reason)
    candidate = valid_candidate()
    candidate["failure_review"] = review
    return memory.update(candidate)


def test_failure_promotes_review_with_trusted_terminal_reason():
    memory = SessionWorkflowMemory()

    result = finish_failure(memory, valid_failure_review())

    assert result["accepted"]["failure_reviews"] == 1
    snapshot = memory.read("find_contract")["memory"]
    assert snapshot["failure_reviews"] == [{
        "terminal_reason": "max_requests",
        **valid_failure_review(),
    }]
    assert snapshot["workflow"] == []
    assert snapshot["landmarks"] == []
    assert snapshot["confidence"] == 0.0


def test_old_failure_candidate_without_review_remains_valid():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("failure", "max_requests")

    result = memory.update(valid_candidate())

    assert result["accepted"]["failure_reviews"] == 0
    assert memory.read("find_contract")["memory"]["failure_reviews"] == []


def test_success_rejects_failure_review_atomically():
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("success", "correct_password")
    candidate = valid_candidate()
    candidate["failure_review"] = valid_failure_review()

    with pytest.raises(WorkflowMemoryError, match="invalid_workflow_memory"):
        memory.update(candidate)

    assert memory.read("find_contract")["version"] == 0
    candidate["failure_review"] = None
    assert memory.update(candidate)["version"] == 1
```

- [ ] **Step 2: Add failing retention, deduplication, and copy tests**

```python
def test_keeps_three_latest_unique_failure_reviews_without_refreshing_duplicates():
    memory = SessionWorkflowMemory()
    reviews = {
        label: valid_failure_review(f"{label}阶段")
        for label in ("甲", "乙", "丙", "丁")
    }
    finish_failure(memory, reviews["甲"])
    finish_failure(memory, reviews["乙"])
    finish_failure(memory, reviews["丙"])
    assert finish_failure(memory, reviews["甲"])["accepted"]["failure_reviews"] == 0
    finish_failure(memory, reviews["丁"])

    stored = memory.read("find_contract")["memory"]["failure_reviews"]
    assert [item["stage"] for item in stored] == ["乙阶段", "丙阶段", "丁阶段"]


def test_read_returns_a_copy_of_failure_reviews():
    memory = SessionWorkflowMemory()
    finish_failure(memory, valid_failure_review())

    first = memory.read("find_contract")
    first["memory"]["failure_reviews"][0]["optimizations"][0] = "被修改"

    assert memory.read("find_contract")["memory"]["failure_reviews"][0][
        "optimizations"
    ][0] == "先组合验证环境名称与目标物特征"
```

- [ ] **Step 3: Run the new promotion tests and verify they fail**

```bash
.venv/bin/python3 -m pytest ai_play/tests/test_workflow_memory.py \
  -k 'promotes_review or old_failure or success_rejects or latest_unique or copy_of_failure' -q
```

Expected: FAIL because storage, outcome compatibility, retention, and snapshot output are absent.

- [ ] **Step 4: Implement atomic promotion and bounded retention**

Add `self._failure_reviews: list[dict] = []`. Include an empty or populated deep copy as `failure_reviews` in every non-null snapshot.

Before mutating success memory, reject a non-null review for a trusted success. For a trusted failure, merge `avoid` as today and, when a review exists, build the stored value from the trusted attempt:

```python
accepted = {
    "workflow": 0,
    "landmarks": 0,
    "avoid": 0,
    "failure_reviews": 0,
}
if attempt.status == "success":
    if safe["failure_review"] is not None:
        raise WorkflowMemoryError("invalid_workflow_memory")
    self._goal_pattern = safe["goal_pattern"]
    accepted["workflow"] = _merge_unique(self._workflow, safe["workflow"])
    accepted["landmarks"] = _merge_unique(self._landmarks, safe["landmarks"])
elif safe["failure_review"] is not None:
    trusted_review = {
        "terminal_reason": attempt.terminal_reason,
        **safe["failure_review"],
    }
    accepted["failure_reviews"] = _append_bounded_unique(
        self._failure_reviews,
        trusted_review,
        max_items=3,
    )
accepted["avoid"] = _merge_unique(self._avoid, safe["avoid"])
```

Add:

```python
def _append_bounded_unique(target: list, item: object, *, max_items: int) -> int:
    if item in target:
        return 0
    target.append(deepcopy(item))
    del target[:-max_items]
    return 1
```

Do not refresh a duplicate's position. Do not change `completed_runs`, eligible statuses, or confidence calculation.

- [ ] **Step 5: Run memory tests and commit**

```bash
.venv/bin/python3 -m pytest ai_play/tests/test_workflow_memory.py -q
git add ai_play/src/ai_play/workflow_memory.py \
  ai_play/tests/test_workflow_memory.py
git diff --cached --check
git diff --cached
git commit -m "feat(ai-play): retain trusted failure reviews"
```

Expected: all memory tests PASS; the commit contains no unrelated files.

### Task 3: Expose the Optional MCP Field Without Logging It

**Files:**
- Modify: `ai_play/tests/test_mcp_server.py:145-193,347-427`
- Modify: `ai_play/src/ai_play/mcp_server.py:235-272`

- [ ] **Step 1: Update the MCP helper and write failing compatibility tests**

Add `"failure_review": None` to `valid_workflow_candidate()`. Extend the tool-list test:

```python
update_tool = next(tool for tool in tools.tools if tool.name == "workflow_memory_update")
assert "failure_review" in update_tool.inputSchema["properties"]
assert "failure_review" not in update_tool.inputSchema.get("required", [])
```

Add a call that omits the optional field entirely:

```python
def test_workflow_memory_update_accepts_old_call_without_failure_review(monkeypatch):
    memory = SessionWorkflowMemory()
    memory.start_attempt("find_contract")
    memory.finish_attempt("failure", "max_requests")
    configure_server(monkeypatch, memory=memory)
    candidate = valid_workflow_candidate()
    candidate.pop("failure_review")

    result = call_tool("workflow_memory_update", candidate)

    assert result.structuredContent["accepted"]["failure_reviews"] == 0
```

- [ ] **Step 2: Write failing trusted-reason and no-logging tests**

Create a failed attempt with terminal reason `max_requests`, submit a review that has no reason field, and assert `workflow_memory_read` returns the trusted reason. Update `test_workflow_memory_tools_are_not_logged` to submit a model-authored review and assert both logger collections remain empty. Do not assert that terminal reasons disappear from ordinary attempt result logging; only AWM calls and model-authored review fields are excluded.

- [ ] **Step 3: Run the focused MCP tests and verify they fail**

```bash
.venv/bin/python3 -m pytest ai_play/tests/test_mcp_server.py \
  -k 'workflow_memory or exposes_only_game_tools' -q
```

Expected: FAIL because the public tool has no optional field and cannot pass reviews.

- [ ] **Step 4: Add the optional MCP argument**

```python
async def workflow_memory_update(
    goal_pattern: str,
    workflow: list[dict],
    landmarks: list[dict],
    avoid: list[str],
    failure_review: dict | None = None,
) -> CallToolResult:
    ...
    candidate = {
        "goal_pattern": goal_pattern,
        "workflow": workflow,
        "landmarks": landmarks,
        "avoid": avoid,
        "failure_review": failure_review,
    }
```

Do not add trajectory logger calls or expose the active attempt to the MCP caller. `SessionWorkflowMemory.update()` remains responsible for binding the review to the next eligible trusted attempt.

- [ ] **Step 5: Run MCP tests and commit**

```bash
.venv/bin/python3 -m pytest ai_play/tests/test_mcp_server.py -q
git add ai_play/src/ai_play/mcp_server.py ai_play/tests/test_mcp_server.py
git diff --cached --check
git diff --cached
git commit -m "feat(ai-play): expose optional failure reviews"
```

Expected: all MCP server tests PASS.

### Task 4: Teach the Player the Multi-Run Reflection Loop

**Files:**
- Modify: `tests/test_ai_play_codex_orchestrator.py:330-435`
- Modify: `tools/ai_play_codex_orchestrator.py:415-454`

- [ ] **Step 1: Write failing prompt-contract tests**

```python
def test_player_prompt_requires_failure_reflection_loop():
    orchestrator = load_orchestrator()

    prompt = orchestrator.build_player_prompt(runs=2)

    assert "failure_review" in prompt
    assert "stage、bottlenecks 和 optimizations" in prompt
    assert "失败局的 workflow 和 landmarks 必须为空" in prompt
    assert "最新 briefing 和 observe" in prompt
    assert "说明哪些优化适用" in prompt
    assert "如何改变当前计划" in prompt
    assert "随机答案" in prompt
```

Extend the disabled-AWM test to assert `failure_review` and `failure_reviews` are absent when memory is disabled.

- [ ] **Step 2: Run the prompt tests and verify they fail**

```bash
.venv/bin/python3 -m pytest tests/test_ai_play_codex_orchestrator.py \
  -k 'failure_reflection or awm_lifecycle or without_awm' -q
```

Expected: FAIL because the prompt only teaches `avoid` today.

- [ ] **Step 3: Update only AWM-enabled prompt rules**

Replace the failure rule with requirements equivalent to:

```text
失败局的 workflow 和 landmarks 必须为空；提交 avoid 和 failure_review。
failure_review 只包含 stage、bottlenecks 和 optimizations，概括可跨局复用的优化。
下一局读取 failure_reviews 后，用最新 briefing 和 observe 判断哪些优化适用，公开说明证据以及它如何改变当前计划；不适用的建议必须忽略。
```

Keep the existing prohibitions on images, passwords, randomized answers, absolute coordinates, frame-by-frame actions, paths, URLs, and internal facts. Update the public decision-record section so it records review applicability rather than merely saying memory exists. Leave `workflow_memory_enabled=False` wording and tool allowlist unchanged.

- [ ] **Step 4: Run orchestrator tests and commit**

```bash
.venv/bin/python3 -m pytest tests/test_ai_play_codex_orchestrator.py -q
git add tools/ai_play_codex_orchestrator.py \
  tests/test_ai_play_codex_orchestrator.py
git diff --cached --check
git diff --cached
git commit -m "feat(ai-play): teach multi-run failure reflection"
```

Expected: all orchestrator tests PASS.

### Task 5: Document Failure Reviews and Reflection Semantics

**Files:**
- Modify: `ai_play/README.md:180-193,248-254`
- Modify: `docs/wiki/ai-play/system-guide.md:158-174`

- [ ] **Step 1: Update operator and MCP documentation**

Document:

- optional `failure_review(stage, bottlenecks, optimizations)` input;
- trusted `terminal_reason` injection;
- failure-only eligibility and old-client omission compatibility;
- at most three unique reviews, duplicate no-op without recency refresh;
- later-run applicability checks against fresh briefing/observation evidence;
- no persistence and no model-authored review fields in trajectory logs;
- two runs in one orchestrator are required to observe the producer/consumer reflection branch.

Do not alter or revert the existing unrelated `daily_routine_cleanup` edits already present in both files.

- [ ] **Step 2: Inspect only the intended documentation hunks**

```bash
git diff -- ai_play/README.md docs/wiki/ai-play/system-guide.md
git diff --check -- ai_play/README.md docs/wiki/ai-play/system-guide.md
```

Expected: existing daily-routine hunks remain present and untouched; new AWM hunks appear only in the sections listed above.

- [ ] **Step 3: Stage only AWM hunks and commit**

```bash
git add -p ai_play/README.md docs/wiki/ai-play/system-guide.md
git diff --cached --check
git diff --cached
git commit -m "docs(ai-play): explain AWM failure reflection"
```

During `git add -p`, reject the unrelated daily-routine hunks. Expected staged diff: only AWM documentation.

### Task 6: Run Automated Verification

**Files:**
- Verify only; modify implementation files only if a failing test exposes a defect.

- [ ] **Step 1: Run focused AWM tests**

```bash
.venv/bin/python3 -m pytest \
  ai_play/tests/test_workflow_memory.py \
  ai_play/tests/test_mcp_server.py \
  tests/test_ai_play_codex_orchestrator.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the affected Python AI Play suite**

```bash
.venv/bin/python3 -m pytest \
  ai_play/tests \
  tests/test_ai_play_codex_orchestrator.py \
  tests/test_ai_play_supervisor.py -q
```

Expected: PASS. This suite must not require real credentials or network access.

- [ ] **Step 3: Check diffs and repository hygiene**

```bash
git diff --check
git status --short
git log -8 --oneline
```

Expected: `git diff --check` prints nothing. Status still shows the user's pre-existing unrelated work and any intentionally unstaged documentation hunks; no cache, generated, or unrelated files are staged by this feature.

### Task 7: Run One Approved Two-Play Reflection Session

**Files:**
- Runtime output: `/private/tmp/cogito_ai_player_runs/<timestamp>/`
- No source modification expected.

- [ ] **Step 1: Verify ports and authentication without exposing credentials**

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN || true
lsof -nP -iTCP:8766 -sTCP:LISTEN || true
test -f /Users/niefeng_jannie/.codex/auth.json
```

Expected: ports are free and the final command exits zero. If a Cogito process owns a port, identify the exact process before requesting permission to terminate it.

- [ ] **Step 2: Start the explicitly approved two-run session**

```bash
.venv/bin/python3 tools/ai_play_codex_orchestrator.py \
  --runs 2 \
  --scenario find_key \
  --model gpt-5.6-sol \
  --reasoning-effort high \
  --workflow-memory enabled \
  --codex-auth-home /Users/niefeng_jannie/.codex
```

Expected: MCP, Codex, and Godot connect; run 1 starts with `version: 0` and empty memory. This is a real model/Godot run with the user-approved screenshot, token/cost, and local-trajectory effects.

- [ ] **Step 3: Capture reflection evidence if run 1 fails eligibly**

Record from console output:

- run 1 update returns `accepted.failure_reviews: 1` (or `0` only for a normalized duplicate);
- run 2 `workflow_memory_read` returns the trusted-reason review;
- the player's public decision record identifies which optimization fresh briefing/observation evidence supports and how it changes the plan;
- neither the update call nor model-authored review fields appear in `trajectory.json`.

If run 1 succeeds, report that the failure-reflection branch was not exercised; do not induce or fabricate failure. If Godot, GPU, model transport, or bridge failures occur, report them as ineligible infrastructure outcomes and do not mislabel them as reflection results.

- [ ] **Step 4: Report final results**

Report both run outcomes, step counts, terminal reasons, elapsed time, AWM update/read evidence, trajectory directory, automated verification commands, feature commits, and remaining unrelated worktree changes. Do not attribute performance changes solely to AWM because scene randomness and model sampling remain uncontrolled.
