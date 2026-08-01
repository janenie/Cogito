# Nearby Task Card System Instruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the isolated Codex player, through high-priority developer/system instructions, to recognize the visible task-card marker and scan the nearby spawn area before exploring.

**Architecture:** Extend only `build_player_developer_instructions()` with a conditional task-card acquisition protocol based on public briefing rules and visible appearance. Keep scenario answers, coordinates, source facts, and runtime logs out of the instruction. Lock the contract through orchestrator unit tests and synchronize the existing AI Play documentation.

**Tech Stack:** Python 3, pytest, Codex CLI configuration, Markdown

---

### Task 1: Lock the developer/system instruction contract

**Files:**
- Modify: `tests/test_ai_play_codex_orchestrator.py:356-370`

- [ ] **Step 1: Add failing assertions to the developer-instruction test**

Append these assertions to `test_player_developer_instructions_authorize_visual_comparison_only`:

```python
    assert "青绿色或蓝绿色的独立标志" in instructions
    assert "同心圆、靶心或旋涡状发光圆环" in instructions
    assert "每次水平旋转 45 度" in instructions
    assert "最多覆盖 360 度" in instructions
    assert "截图没有随公开朝向变化" in instructions
    assert "用短步靠近" in instructions
    assert "远距离的 not_found 不能作为排除依据" in instructions
    assert "读取任务卡前不得离开出生区域" in instructions
```

- [ ] **Step 2: Run the focused test and verify RED**

```bash
/tmp/cogito-ai-play-test-venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py::test_player_developer_instructions_authorize_visual_comparison_only -q
```

Expected: FAIL because the visible marker description and 360-degree protocol are absent.

### Task 2: Add the task-card acquisition protocol

**Files:**
- Modify: `tools/ai_play_codex_orchestrator.py:71-94`
- Test: `tests/test_ai_play_codex_orchestrator.py`

- [ ] **Step 1: Extend `build_player_developer_instructions()` minimally**

Insert the following paragraph after the semantic `look` rules and before filesystem restrictions:

```text
如果 briefing 明确要求先读取出生点附近的任务卡，任务卡不是普通纸张：它在画面中表现为
青绿色或蓝绿色的独立标志，细杆底座上方带同心圆、靶心或旋涡状发光圆环，中间有白色小牌；
即使看起来像装饰标记，也要把它作为最高优先级任务卡候选。首次 observe 后保持原地，
每次水平旋转 45 度并获取新 observation，找到候选即停止，最多覆盖 360 度。截图没有随公开
朝向变化时不得把旧截图算作新扇区，必须等待全新 observation。找到候选后用短步靠近、将准星
对准标志中央，再单独调用 probe_interaction；远距离的 not_found 不能作为排除依据。出现读取
交互后执行 interact 并读完任务卡。读取任务卡前不得离开出生区域；水平一圈仍没找到时，才在
原地补充向上和向下扫描。
```

Do not add scenario names, node paths, coordinates, candidate answers, or trace paths.

- [ ] **Step 2: Run the focused test and verify GREEN**

```bash
/tmp/cogito-ai-play-test-venv/bin/python -m pytest \
  tests/test_ai_play_codex_orchestrator.py::test_player_developer_instructions_authorize_visual_comparison_only -q
```

Expected: `1 passed`.

- [ ] **Step 3: Run the complete orchestrator test module**

```bash
/tmp/cogito-ai-play-test-venv/bin/python -m pytest tests/test_ai_play_codex_orchestrator.py -q
```

Expected: all tests pass.

### Task 3: Synchronize operator documentation

**Files:**
- Modify: `ai_play/README.md:107-116`
- Modify: `docs/wiki/ai-play/system-guide.md:103-110`

- [ ] **Step 1: Document the high-priority task-card protocol**

State in both documents that the shared developer/system instruction describes the public visual marker, requires 45-degree sectors up to 360 degrees, waits for a genuinely fresh screenshot, approaches before probing, and forbids leaving spawn before reading.

- [ ] **Step 2: Check safety wording**

```bash
rg -n "节点路径|绝对坐标|DesktopDeskAnchor|desktop_desk|trajectory.json" \
  tools/ai_play_codex_orchestrator.py ai_play/README.md docs/wiki/ai-play/system-guide.md
```

Expected: existing safety prohibitions may match; the new instruction paragraph contains none of the internal identifiers or trace names.

### Task 4: Verify, commit, and push

**Files:**
- Verify all changed files

- [ ] **Step 1: Run affected Python suites**

```bash
/tmp/cogito-ai-play-test-venv/bin/python -m pytest tests/test_ai_play_codex_orchestrator.py -q
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-test-venv/bin/python -m pytest ai_play/tests -q
```

Expected: both suites pass.

- [ ] **Step 2: Run static safety and integrity checks**

```bash
bash tests/test_ai_play_secret_scan.sh
git diff --check
git status --short --branch
```

Expected: checks exit 0; only instruction, tests, docs, design and plan are in scope, with pre-existing cache directories unstaged.

- [ ] **Step 3: Commit and push**

```bash
git add tools/ai_play_codex_orchestrator.py \
  tests/test_ai_play_codex_orchestrator.py \
  ai_play/README.md docs/wiki/ai-play/system-guide.md \
  docs/superpowers/specs/plan-nearby-task-card-system-instruction.md
git commit -m "feat(ai-play): teach nearby task-card scan"
git push origin feature/session-awm
```

Expected: `origin/feature/session-awm` points to the verified implementation commit. Do not switch branches, merge, open a PR, or clean the worktree.

### Task 5: Repeat the authorized real AI acceptance session

**Files:**
- Runtime output only: a new timestamped directory under `/private/tmp/cogito_ai_player_runs/`

- [ ] **Step 1: Verify ports are free**

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
lsof -nP -iTCP:8766 -sTCP:LISTEN
```

Expected: no listeners.

- [ ] **Step 2: Run three unattended AWM rounds**

```bash
/tmp/cogito-ai-play-test-venv/bin/python tools/ai_play_codex_orchestrator.py \
  --runs 3 --scenario find_key --model gpt-5.6-sol \
  --reasoning-effort high --workflow-memory enabled \
  --codex-auth-home /Users/jan/.codex-cogito-player
```

Expected: the player describes and executes the nearby 360-degree scan, reads the task card before cross-room exploration, and attempts all three 50-step rounds without manual gameplay input. Previously authorized screenshot transmission, token cost, and local trace persistence remain in effect.

- [ ] **Step 3: Report evidence**

Report each completed round's task-card acquisition, outcome, terminal reason, step count, AWM update, and timestamped log directory. Keep the known supervisor max-request parsing issue out of scope unless separately approved.
