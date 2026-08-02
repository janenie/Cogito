# Find Key Godot 50-Step Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every new Godot `find_key` round report a 50-request maximum, regardless of key location.

**Architecture:** `AIPlayFindKeyMonitor` becomes the single new-round source of a constant 50. The protocol-v4 controller and Python compatibility allowlist remain unchanged, so older Godot processes that report 100 are still accepted. Public rules describe the effective limit emitted by the current Godot implementation.

**Tech Stack:** Godot 4.7/GDScript, Python briefing data, Markdown documentation.

---

### Task 1: Lock the Godot round report to 50

**Files:**
- Modify: `tests/ai_play/test_ai_play_find_key_monitor.gd`
- Modify: `addons/cogito/AIPlay/ai_play_find_key_monitor.gd`

- [ ] **Step 1: Write the failing monitor assertion**

```gdscript
_assert(
	monitor.get_act_request_limit() == 50,
	"every selected key location uses the fixed 50-request limit",
)
```

- [ ] **Step 2: Verify the test fails**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd`

Expected: FAIL for laptop-desk and meeting-table seeds because current Godot returns 100.

- [ ] **Step 3: Implement the minimal fixed report**

```gdscript
const ACT_REQUEST_LIMIT: int = 50

func get_act_request_limit() -> int:
	return ACT_REQUEST_LIMIT
```

- [ ] **Step 4: Verify the focused test passes**

Run the command from Step 2 and expect `AIPlay find-key monitor test passed` with exit 0.

### Task 2: Synchronize public and operator-facing rules

**Files:**
- Modify: `ai_play/src/ai_play/find_key_briefing.py`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`

- [ ] **Step 1: Update effective-limit text**

State that current Godot rounds use a fixed 50 `act` limit. Retain the protocol paragraph that Python accepts 50 or 100 for older Godot compatibility; do not change Python constants or validation.

- [ ] **Step 2: Verify obsolete location-dependent claims are absent**

Run:

```bash
rg -n '50/100|最大值 100|位置使用 100' ai_play/README.md docs/wiki/ai-play/system-guide.md ai_play/src/ai_play/find_key_briefing.py
```

Expected: no effective-limit claim remains; compatibility text may still explicitly mention accepted 50 or 100.

### Task 3: Full verification and publication

**Files:**
- Verify only the files changed above and existing controller/bridge behavior.

- [ ] **Step 1: Run affected verification**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-test-venv/bin/python -m pytest ai_play/tests -q
bash tests/check_ai_play_lobby.sh
bash tests/test_ai_play_secret_scan.sh
git diff --check
```

- [ ] **Step 2: Commit and push intended files**

Commit as `fix(ai-play): report fifty-step find-key rounds` and push `feature/session-awm`. Do not stage `__pycache__`, logs, screenshots, or run directories.
