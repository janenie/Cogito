# Remove CUBICLE AREA from find_key Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the CUBICLE AREA desktop-desk answer from `find_key` while preserving that area and all `find_contract` behavior.

**Architecture:** Keep `AIPlayFindKeyMonitor` as the sole owner of the random candidate allowlist. Remove the desktop candidate from that allowlist and its scene-only wiring, then lock the four-candidate contract with a Godot integration test. Documentation changes describe only the public four-location behavior; no bridge protocol or Python session behavior changes.

**Tech Stack:** Godot 4.7, GDScript, Godot `.tscn` resources, Markdown, pytest/static shell checks

---

### Task 1: Lock the four-candidate find_key contract

**Files:**
- Modify: `tests/ai_play/test_ai_play_find_key_monitor.gd:30-86`

- [ ] **Step 1: Write the failing assertions**

Add exact candidate and scene-wiring assertions immediately after resolving the monitor:

```gdscript
	_assert(
		monitor.LOCATION_IDS == [
			"laptop_desk",
			"archive_sofa",
			"meeting_table",
			"tv_coffee_table",
		],
		"find_key exposes exactly the four non-cubicle locations",
	)
	_assert(
		lobby.get_node_or_null("FindKeyMarkers/DesktopDeskAnchor") == null,
		"Lobby does not retain the removed desktop key anchor",
	)
```

Change the coverage assertion label to:

```gdscript
	_assert(
		seen_locations.size() == monitor.LOCATION_IDS.size(),
		"fixed seed sample reaches all four key locations",
	)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd
```

Expected: exit 1 with failures for the five-element allowlist and retained `DesktopDeskAnchor`.

### Task 2: Remove the desktop candidate and its Lobby wiring

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_find_key_monitor.gd:6-31,81-89,201-215`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn:3323-3334,8032-8038`
- Test: `tests/ai_play/test_ai_play_find_key_monitor.gd`

- [ ] **Step 1: Remove the desktop candidate from the monitor**

Make the candidate definitions begin with the four retained locations:

```gdscript
const LOCATION_IDS: Array[String] = [
	"laptop_desk",
	"archive_sofa",
	"meeting_table",
	"tv_coffee_table",
]
const LOCATION_TASK_TEXT := {
	"laptop_desk": "钥匙在有笔记本电脑的办公桌上。",
	"archive_sofa": "钥匙在档案室旁边的沙发上。",
	"meeting_table": "钥匙在会议室的长桌上。",
	"tv_coffee_table": "钥匙在有大电视的茶几上。",
}
```

Delete the `desktop_desk_anchor` export. Make `_key_anchors()` return only the four retained mappings:

```gdscript
func _key_anchors() -> Dictionary:
	return {
		"laptop_desk": laptop_desk_anchor,
		"archive_sofa": archive_sofa_anchor,
		"meeting_table": meeting_table_anchor,
		"tv_coffee_table": tv_coffee_table_anchor,
	}
```

Remove `desktop_desk_anchor` from `_has_required_nodes()`. Do not modify `ACT_REQUEST_LIMIT`, spawn selection, task-card generation, or terminal behavior.

- [ ] **Step 2: Remove only the find_key scene wiring**

In `FindKeyMonitor`, remove `desktop_desk_anchor` from `node_paths` and delete:

```text
desktop_desk_anchor = NodePath("../../FindKeyMarkers/DesktopDeskAnchor")
```

Delete only this marker resource:

```text
[node name="DesktopDeskAnchor" type="Marker3D" parent="FindKeyMarkers" ...]
transform = ...
```

Keep the `CUBICLE_AREA` subtree, `TerminalMonitor.cubicle_anchor`, and `FindContract_ComputerRecord` unchanged.

- [ ] **Step 3: Run the focused test to verify it passes**

Run:

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd
```

Expected: exit 0 and `AIPlay find-key monitor test passed`.

- [ ] **Step 4: Inspect the scene boundary**

Run:

```bash
rg -n "desktop_desk|DesktopDeskAnchor|cubicle_anchor|FindContract_ComputerRecord" \
  addons/cogito/AIPlay/ai_play_find_key_monitor.gd \
  addons/cogito/DemoScenes/COGITO_3_Lobby.tscn
```

Expected: no `desktop_desk` or `DesktopDeskAnchor`; the `find_contract` cubicle anchor and record remain.

- [ ] **Step 5: Commit the verified runtime change and its test**

```bash
git add tests/ai_play/test_ai_play_find_key_monitor.gd \
  addons/cogito/AIPlay/ai_play_find_key_monitor.gd \
  addons/cogito/DemoScenes/COGITO_3_Lobby.tscn
git commit -m "fix(ai-play): remove cubicle find-key answer"
```

### Task 3: Synchronize public and developer documentation

**Files:**
- Modify: `ai_play/README.md:206-211`
- Modify: `docs/wiki/ai-play/system-guide.md:259-269`
- Modify: `game_script/find_key.md:30-61,186,317`

- [ ] **Step 1: Update public documentation**

Change the README and Wiki from five furniture locations to four. List or describe only the retained semantic locations, retain the 50-request rule, and do not expose internal IDs or coordinates.

Use this public wording:

```markdown
`find_key` 每局把场景中唯一的钥匙放到四类办公家具位置之一：有笔记本电脑的办公桌、
档案室旁边的沙发、会议室长桌或有大电视的茶几。
```

- [ ] **Step 2: Update the developer gameplay note**

In `game_script/find_key.md`, rename the candidate section to `四个钥匙候选位置`, delete the complete desktop-computer candidate section, renumber the retained candidates 1–4, and replace remaining references to five candidates with four. Preserve the warning that this file never becomes runtime model input.

- [ ] **Step 3: Verify stale answer text is gone from find_key scope**

Run:

```bash
rg -n "五个钥匙|五类办公家具|desktop_desk|DesktopDeskAnchor|钥匙在有台式电脑" \
  addons/cogito/AIPlay/ai_play_find_key_monitor.gd \
  addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  tests/ai_play/test_ai_play_find_key_monitor.gd \
  ai_play/README.md docs/wiki/ai-play/system-guide.md game_script/find_key.md
```

Expected: no matches. References to CUBICLE AREA for `find_contract` elsewhere remain valid.

- [ ] **Step 4: Commit documentation**

```bash
git add ai_play/README.md docs/wiki/ai-play/system-guide.md game_script/find_key.md
git commit -m "docs(ai-play): document four find-key locations"
```

### Task 4: Run affected verification and publish

**Files:**
- Verify only; no planned source changes

- [ ] **Step 1: Run Godot tests**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_find_key_monitor.gd
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
```

Expected: both commands exit 0 with their respective pass messages.

- [ ] **Step 2: Run Python and static suites**

```bash
PYTHONPATH=ai_play/src /tmp/cogito-ai-play-test-venv/bin/python -m pytest ai_play/tests -q
bash tests/check_ai_play_lobby.sh
bash tests/test_ai_play_secret_scan.sh
```

Expected: pytest reports all tests passed; both shell checks exit 0.

- [ ] **Step 3: Verify diff integrity and scope**

```bash
git diff --check
git status --short --branch
git diff origin/feature/session-awm...HEAD --stat
```

Expected: no whitespace errors; only the design, plan, four-candidate implementation, scene wiring, tests, and documentation are changed. The pre-existing untracked Python cache directories remain unstaged.

- [ ] **Step 4: Commit the implementation plan**

```bash
git add docs/superpowers/specs/plan-find-key-remove-cubicle-candidate.md
git commit -m "docs(ai-play): plan cubicle key candidate removal"
```

- [ ] **Step 5: Push the current branch**

```bash
git push origin feature/session-awm
```

Expected: `origin/feature/session-awm` points to the verified final commit. Do not switch branches, merge, open a PR, or delete the worktree.

### Task 5: Run the authorized real AI acceptance session

**Files:**
- Runtime output only: a new timestamped directory under `/private/tmp/cogito_ai_player_runs/`

- [ ] **Step 1: Confirm the bridge port is available without changing unrelated processes**

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

Expected: no listener. If a listener exists, inspect its command and clients first; stop it only when it is an idle AI Play process from this repository. Do not terminate unrelated processes.

- [ ] **Step 2: Start three unattended AWM rounds**

Run from the current worktree:

```bash
/tmp/cogito-ai-play-test-venv/bin/python tools/ai_play_codex_orchestrator.py \
  --runs 3 \
  --scenario find_key \
  --model gpt-5.6-sol \
  --reasoning-effort high \
  --workflow-memory enabled \
  --codex-auth-home /Users/jan/.codex-cogito-player
```

Expected: Godot advertises a 50-request round limit, Codex receives only approved screenshots and briefing data, and the orchestrator advances through all three rounds without manual input. Screenshot transmission, token cost, and local trajectory persistence were explicitly authorized by the user.

- [ ] **Step 3: Inspect and report all three outcomes**

```bash
run_dir=$(find /private/tmp/cogito_ai_player_runs -mindepth 1 -maxdepth 1 -type d -print | sort | tail -n 1)
find "$run_dir" -maxdepth 4 \
  -type f \( -name 'summary.json' -o -name 'trajectory.json' -o -name 'run.json' \) -print
```

Read the generated summaries and report each round's outcome, terminal reason, step count, AWM update status, and the concrete log directory. Do not treat model failure as proof of a code regression, and do not modify supervisor or gameplay behavior without a separate diagnosis and user approval.
