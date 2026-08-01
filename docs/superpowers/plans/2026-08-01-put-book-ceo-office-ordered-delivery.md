# Put Book CEO Office Ordered Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `put_book` into a seeded, ordered task where six books are distributed evenly over multiple archive shelves and three marked targets must be carried one at a time, low-to-middle-to-high, to one CEO-office placement point.

**Architecture:** Add nine authored slot markers over three open archive bookcases and select a balanced six-slot layout with a small deterministic helper. Keep round ownership in `AIPlayPutBookMonitor`: it creates six runtime books, marks one target per height tier, validates pickup order, and accepts delivery through one dedicated CEO destination prefab with three internal display anchors. Synchronize the new success/failure reasons and 150-request cap across Godot, Python, public briefing, tests, README, and the stable AI-play wiki.

**Tech Stack:** Godot 4.7, typed GDScript, `.tscn` scenes, COGITO carry interactions, Python 3, pytest, shell-based Godot headless checks.

## Global Constraints

- Exactly six books are visible in the archive: two `low`, two `middle`, and two `high`.
- Exactly one book per height tier is visibly marked as a target; required order is `low`, `middle`, `high`.
- A nonzero `round_seed` reproduces occupied slots and target selection; seed `0` randomizes normally.
- Occupied slots are selected only from authored standing-reachable markers; no unconstrained coordinates are generated.
- Three logical shelf groups receive exactly two books each; no slot is occupied twice.
- All six books can be picked up before a correct carry starts. Picking an ordinary or out-of-order book immediately emits `failure/wrong_book_pickup`.
- While the current correct book is carried, every other unfinished book is pickup-disabled. Dropping that book outside the CEO destination is recoverable.
- Jumping and crouching are neither required nor checked.
- The CEO office exposes one visible placement point with three internal display anchors.
- Success is exactly `success/books_in_ceo_office` after three ordered deliveries.
- The Python scenario hard cap is 150 act requests; a lower global cap may still tighten it.
- Generated slot IDs, shelf IDs, target identities, seed state, node paths, and exact coordinates remain internal and never enter MCP observations or the public briefing.
- Keep protocol version 4, the `127.0.0.1` bridge boundary, Escape emergency stop, and existing simulated-input cleanup behavior unchanged.

## File Structure

- Create `addons/cogito/AIPlay/ai_play_put_book_layout.gd`: validate authored slot metadata and choose the deterministic balanced layout.
- Create `addons/cogito/AIPlay/ai_play_put_book_destination_interactable.gd`: COGITO interactable root contract for the CEO placement prefab.
- Create `addons/cogito/AIPlay/ai_play_put_book_destination_drop_interaction.gd`: assisted-drop interaction that delegates validation and placement to the monitor.
- Create `addons/cogito/DemoScenes/DemoPrefabs/ai_play_put_book_destination.tscn`: visible tray/sign, acceptance area, and three display anchors.
- Modify `addons/cogito/AIPlay/ai_play_put_book_monitor.gd`: replace box/posture behavior with six-book setup, target order, pickup scoring, and CEO delivery state.
- Modify `addons/cogito/DemoScenes/DemoPrefabs/carryable_books.tscn`: add a hidden target label reused by every runtime duplicate.
- Modify `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`: add shelf slots and CEO destination, group the old decorative books, and update monitor exports.
- Delete `addons/cogito/AIPlay/ai_play_put_book_box_interactable.gd`: the archive-box interactable is obsolete.
- Delete `addons/cogito/AIPlay/ai_play_put_book_box_drop_interaction.gd`: the nearest-box drop interaction is obsolete.
- Modify `tests/ai_play/test_ai_play_put_book_monitor.gd`: cover seeded layout, target selection, order failure, one-book gating, recovery, and delivery.
- Modify `addons/cogito/AIPlay/ai_play_controller.gd` and `addons/cogito/AIPlay/ai_play_game_over_screen.gd`: allow and present the new terminal reasons.
- Modify `tests/ai_play/test_ai_play_controller.gd`: lock the Godot terminal allowlist.
- Modify `tests/ai_play/test_ai_play_game_over_screen.gd`: lock the Chinese success and failure copy.
- Modify `ai_play/src/ai_play/scenarios.py`, `ai_play/tests/test_scenarios.py`, and `ai_play/tests/test_game_session.py`: register the new outcomes and 150-request cap.
- Modify `ai_play/src/ai_play/put_book_briefing.py` and `ai_play/tests/test_briefing.py`: publish only the approved player-visible rules.
- Modify `ai_play/README.md` and `docs/wiki/ai-play/system-guide.md`: replace the obsolete box/posture description with the stable ordered-delivery contract.

---

### Task 1: Add authored shelf slots and deterministic balanced selection

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_put_book_layout.gd`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn:6729-6747`
- Modify: `tests/ai_play/test_ai_play_put_book_monitor.gd:25-124`
- Test: `tests/check_ai_play_put_book_monitor.sh`

**Interfaces:**
- Consumes: `Marker3D` children with string metadata `slot_id`, `shelf_id`, and `height_tier`.
- Produces: `AIPlayPutBookLayout.select_slots(slots: Array[Marker3D], rng: RandomNumberGenerator) -> Array[Marker3D]`, ordered by `low`, then `middle`, then `high`, with two slots per tier and two slots per shelf.
- Produces: `AIPlayPutBookLayout.slot_id(slot: Marker3D) -> String`, `shelf_id(slot: Marker3D) -> String`, and `height_tier(slot: Marker3D) -> String`.

- [ ] **Step 1: Write the failing layout test**

At the start of the existing Lobby-backed test, load `ARCHIVE/PutBookShelfSlots`, collect its `Marker3D` children, and add these literal assertions:

```gdscript
var slot_root: Node3D = lobby.get_node_or_null("ARCHIVE/PutBookShelfSlots")
_assert(slot_root != null, "archive exposes put-book shelf slots")
var slots: Array[Marker3D] = []
if slot_root != null:
	for child: Node in slot_root.get_children():
		if child is Marker3D:
			slots.append(child as Marker3D)
_assert(slots.size() == 9, "three shelves expose three height slots each")

var seen_layouts: Dictionary = {}
var seen_slot_ids: Dictionary = {}
for seed_value: int in range(1, 129):
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var selected := AIPlayPutBookLayout.select_slots(slots, rng)
	_assert(selected.size() == 6, "layout selects six slots")
	_assert(_count_tier(selected, "low") == 2, "layout has two low slots")
	_assert(_count_tier(selected, "middle") == 2, "layout has two middle slots")
	_assert(_count_tier(selected, "high") == 2, "layout has two high slots")
	for shelf_name: String in ["open_a", "open_b", "open_c"]:
		_assert(_count_shelf(selected, shelf_name) == 2, "layout balances shelf books")
	var layout_ids: Array[String] = []
	for slot: Marker3D in selected:
		var id := AIPlayPutBookLayout.slot_id(slot)
		layout_ids.append(id)
		seen_slot_ids[id] = true
	layout_ids.sort()
	seen_layouts["|".join(layout_ids)] = true

_assert(seen_layouts.size() > 1, "seed sample produces multiple layouts")
_assert(seen_slot_ids.size() == slots.size(), "seed sample reaches every slot")
```

Add concrete helpers at the bottom of the test:

```gdscript
func _count_tier(slots: Array[Marker3D], tier: String) -> int:
	var count := 0
	for slot: Marker3D in slots:
		if AIPlayPutBookLayout.height_tier(slot) == tier:
			count += 1
	return count


func _count_shelf(slots: Array[Marker3D], shelf_name: String) -> int:
	var count := 0
	for slot: Marker3D in slots:
		if AIPlayPutBookLayout.shelf_id(slot) == shelf_name:
			count += 1
	return count
```

- [ ] **Step 2: Run the layout test and verify RED**

Run:

```bash
bash tests/check_ai_play_put_book_monitor.sh
```

Expected: FAIL because `AIPlayPutBookLayout` and `ARCHIVE/PutBookShelfSlots` do not exist.

- [ ] **Step 3: Add the nine authored slot markers**

Under `ARCHIVE`, add `PutBookShelfSlots` and these nine `Marker3D` children. Use the existing open-bookcase basis and the literal archive-local positions below:

| Marker | `slot_id` | `shelf_id` | `height_tier` | Position `(x, y, z)` |
| --- | --- | --- | --- | --- |
| `OpenA_Low` | `open_a_low` | `open_a` | `low` | `(2.68, 0.25, -0.18)` |
| `OpenA_Middle` | `open_a_middle` | `open_a` | `middle` | `(2.68, 0.85, -0.18)` |
| `OpenA_High` | `open_a_high` | `open_a` | `high` | `(2.68, 1.45, -0.18)` |
| `OpenB_Low` | `open_b_low` | `open_b` | `low` | `(2.68, 0.25, -0.98)` |
| `OpenB_Middle` | `open_b_middle` | `open_b` | `middle` | `(2.68, 0.85, -0.98)` |
| `OpenB_High` | `open_b_high` | `open_b` | `high` | `(2.68, 1.45, -0.98)` |
| `OpenC_Low` | `open_c_low` | `open_c` | `low` | `(2.68, 0.25, -1.78)` |
| `OpenC_Middle` | `open_c_middle` | `open_c` | `middle` | `(2.68, 0.85, -1.78)` |
| `OpenC_High` | `open_c_high` | `open_c` | `high` | `(2.68, 1.45, -1.78)` |

Each marker uses metadata keys exactly as listed and the shelf-facing basis already used by the book props:

```text
Transform3D(-4.37114e-08, 0, -1, 0, 1, 0, 1, 0, -4.37114e-08, x, y, z)
```

- [ ] **Step 4: Implement the selector**

Create the helper with exact validation and combination behavior:

```gdscript
class_name AIPlayPutBookLayout
extends RefCounted

const HEIGHT_TIERS: Array[String] = ["low", "middle", "high"]
const BOOKS_PER_TIER := 2


static func slot_id(slot: Marker3D) -> String:
	return String(slot.get_meta("slot_id", ""))


static func shelf_id(slot: Marker3D) -> String:
	return String(slot.get_meta("shelf_id", ""))


static func height_tier(slot: Marker3D) -> String:
	return String(slot.get_meta("height_tier", ""))


static func select_slots(
	slots: Array[Marker3D],
	rng: RandomNumberGenerator,
) -> Array[Marker3D]:
	var by_tier: Dictionary = {}
	for tier: String in HEIGHT_TIERS:
		by_tier[tier] = []
	var seen_ids: Dictionary = {}
	for slot: Marker3D in slots:
		var id := slot_id(slot)
		var shelf := shelf_id(slot)
		var tier := height_tier(slot)
		if id.is_empty() or shelf.is_empty() or tier not in HEIGHT_TIERS:
			continue
		if seen_ids.has(id):
			continue
		seen_ids[id] = true
		(by_tier[tier] as Array).append(slot)

	var tier_pairs: Dictionary = {}
	for tier: String in HEIGHT_TIERS:
		tier_pairs[tier] = _pairs(by_tier[tier] as Array)
		if (tier_pairs[tier] as Array).is_empty():
			return []

	var best_layouts: Array[Array] = []
	var best_score: Array[int] = []
	for low_pair: Array in tier_pairs["low"]:
		for middle_pair: Array in tier_pairs["middle"]:
			for high_pair: Array in tier_pairs["high"]:
				var layout: Array = low_pair + middle_pair + high_pair
				var score := _shelf_score(layout)
				if best_score.is_empty() or _score_less(score, best_score):
					best_score = score
					best_layouts = [layout]
				elif score == best_score:
					best_layouts.append(layout)
	if best_layouts.is_empty():
		return []
	var chosen: Array = best_layouts[rng.randi_range(0, best_layouts.size() - 1)]
	var result: Array[Marker3D] = []
	for value: Variant in chosen:
		result.append(value as Marker3D)
	return result


static func _pairs(values: Array) -> Array[Array]:
	var result: Array[Array] = []
	for first: int in range(values.size()):
		for second: int in range(first + 1, values.size()):
			result.append([values[first], values[second]])
	return result


static func _shelf_score(layout: Array) -> Array[int]:
	var counts: Dictionary = {}
	for value: Variant in layout:
		var shelf := shelf_id(value as Marker3D)
		counts[shelf] = int(counts.get(shelf, 0)) + 1
	var score: Array[int] = []
	for count: Variant in counts.values():
		score.append(int(count))
	score.sort()
	score.reverse()
	while score.size() < 3:
		score.append(0)
	return score


static func _score_less(left: Array[int], right: Array[int]) -> bool:
	for index: int in range(mini(left.size(), right.size())):
		if left[index] != right[index]:
			return left[index] < right[index]
	return left.size() < right.size()
```

The three-by-three authored grid makes the best score exactly `[2, 2, 2]`.

- [ ] **Step 5: Verify GREEN and commit**

Run:

```bash
godot --headless --path . --editor --quit
bash tests/check_ai_play_put_book_monitor.sh
git diff --check
```

Expected: the slot/selector assertions pass and Godot reports no parse or UID errors.

Commit:

```bash
git add addons/cogito/AIPlay/ai_play_put_book_layout.gd addons/cogito/AIPlay/ai_play_put_book_layout.gd.uid addons/cogito/DemoScenes/COGITO_3_Lobby.tscn tests/ai_play/test_ai_play_put_book_monitor.gd
git commit -m "feat(ai-play): add balanced put-book shelf layouts"
```

---

### Task 2: Populate six books and select one marked target per tier

**Files:**
- Modify: `addons/cogito/DemoScenes/DemoPrefabs/carryable_books.tscn`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn:3342-3361,6729-6749,6789-6817`
- Modify: `addons/cogito/AIPlay/ai_play_put_book_monitor.gd`
- Modify: `tests/ai_play/test_ai_play_put_book_monitor.gd`
- Test: `tests/check_ai_play_put_book_monitor.sh`

**Interfaces:**
- Consumes: `AIPlayPutBookLayout.select_slots(slots: Array[Marker3D], rng: RandomNumberGenerator) -> Array[Marker3D]` from Task 1 and `shelf_slots_root: Node3D` from the Lobby.
- Produces: `configure_round(seed_value: int = 0) -> void` with six active books and three ordered targets.
- Produces: `get_round_snapshot() -> Dictionary` with keys `seed`, `books`, `target_order`, `current_target_index`, `carried_book`, `completed`, and `task_text`.
- Produces internal state `_active_books: Array[RigidBody3D]`, `_target_books: Array[RigidBody3D]`, `_slot_by_book: Dictionary`, `_current_target_index: int`, and `_effective_seed: int`.

- [ ] **Step 1: Replace the old round-setup assertions with failing six-book assertions**

For seeds `1..128`, assert:

```gdscript
monitor.configure_round(seed_value)
var snapshot: Dictionary = monitor.get_round_snapshot()
_assert(snapshot["books"].size() == 6, "round exposes six books")
_assert(snapshot["target_order"].size() == 3, "round selects three targets")
_assert(monitor._active_books.size() == 6, "six runtime books are active")
_assert(monitor._target_books.size() == 3, "three runtime books are targets")
_assert(_snapshot_tier_count(snapshot, "low") == 2, "snapshot has two low books")
_assert(_snapshot_tier_count(snapshot, "middle") == 2, "snapshot has two middle books")
_assert(_snapshot_tier_count(snapshot, "high") == 2, "snapshot has two high books")
_assert(_target_tiers(snapshot) == ["low", "middle", "high"], "targets are ordered low to high")
_assert(String(snapshot["task_text"]).contains("CEO OFFICE"), "task card names CEO OFFICE")
_assert(not String(snapshot["task_text"]).contains("跳"), "task card removes jump rule")
_assert(not String(snapshot["task_text"]).contains("蹲"), "task card removes crouch rule")
_assert(not String(snapshot["task_text"]).contains("纸箱"), "task card removes box rule")
```

Configure the same nonzero seed twice and compare the `books` and `target_order` arrays for exact equality. Across the seed sample, record at least two distinct occupied-slot fingerprints and every active book's `TargetMarker.visible` state.

Add these snapshot helpers:

```gdscript
func _snapshot_tier_count(snapshot: Dictionary, tier: String) -> int:
	var count := 0
	for entry: Dictionary in snapshot["books"]:
		if entry["height"] == tier:
			count += 1
	return count


func _target_tiers(snapshot: Dictionary) -> Array[String]:
	var tier_by_book: Dictionary = {}
	for entry: Dictionary in snapshot["books"]:
		tier_by_book[entry["book"]] = entry["height"]
	var result: Array[String] = []
	for book_name: String in snapshot["target_order"]:
		result.append(String(tier_by_book[book_name]))
	return result
```

- [ ] **Step 2: Run the setup test and verify RED**

Run:

```bash
bash tests/check_ai_play_put_book_monitor.sh
```

Expected: FAIL because the monitor still creates three books, assigns boxes, and uses posture text.

- [ ] **Step 3: Add the reusable target marker and scene groups**

Add this child to `carryable_books.tscn`, default-hidden so non-targets never show it:

```text
[node name="TargetMarker" type="Label3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0.34, 0)
visible = false
text = "任务书"
font_size = 32
outline_size = 10
billboard = 1
no_depth_test = false
```

In the Lobby, add the six original `ARCHIVE/books*` props to group `put_book_decorative_book`. Remove `target_box`, `target_box_area`, near/far box anchors, and `book_a..book_f` from the monitor's exported NodePaths. Add `archive_root` and `shelf_slots_root`:

```gdscript
@export var archive_root: Node3D
@export var shelf_slots_root: Node3D
```

Wire them to `../../ARCHIVE` and `../../ARCHIVE/PutBookShelfSlots`.

- [ ] **Step 4: Replace round setup with six-book seeded setup**

Use these constants and fields:

```gdscript
const ROUND_BOOK_COUNT := 6
const TARGET_BOOK_COUNT := 3
const HEIGHT_TIERS: Array[String] = ["low", "middle", "high"]

var _effective_seed: int = 0
var _runtime_books: Array[RigidBody3D] = []
var _runtime_book_parent: Node3D = null
var _active_books: Array[RigidBody3D] = []
var _target_books: Array[RigidBody3D] = []
var _slot_by_book: Dictionary = {}
var _current_target_index: int = 0
var _current_carried_book: RigidBody3D = null
var _completed_books: Array[RigidBody3D] = []
var _books_carried_once: Dictionary = {}
```

In `configure_round`, randomize or assign the RNG, record `rng.seed` as `_effective_seed`, hide the old decorative book group and all archive children whose names begin `cardboardBox`, reset six runtime books, select six slots, place one runtime book at each transform, then choose one active book per tier:

```gdscript
func _select_target_books(rng: RandomNumberGenerator) -> void:
	_target_books.clear()
	for tier: String in HEIGHT_TIERS:
		var candidates: Array[RigidBody3D] = []
		for book: RigidBody3D in _active_books:
			var slot := _slot_by_book.get(book) as Marker3D
			if slot != null and AIPlayPutBookLayout.height_tier(slot) == tier:
				candidates.append(book)
		_target_books.append(candidates[rng.randi_range(0, candidates.size() - 1)])
	for book: RigidBody3D in _active_books:
		var is_target := book in _target_books
		book.set("display_name", "任务书" if is_target else "普通书")
		var marker := book.get_node_or_null("TargetMarker") as Label3D
		if marker != null:
			marker.visible = is_target
```

`_ensure_runtime_books()` must store `carried_book.get_parent_node_3d()` in `_runtime_book_parent` and duplicate until six instances exist. `_reset_runtime_books()` must reparent every previously delivered runtime book back to `_runtime_book_parent` before hiding and resetting it, so repeated `configure_round()` calls do not leave books under CEO display anchors. Remove posture constants, posture dictionaries, jump windows, nearest-box assignment, box placement, and box-area setup from round initialization. Set every unfinished carry component to `is_disabled = false` after placement.

Use this task copy:

```gdscript
const TASK_TITLE := "将任务书送到 CEO OFFICE"
const TASK_CONTENT := (
	"档案室的多个书架上共有六本可搬运的书，其中三本带有“任务书”标记。\n\n"
	+ "请根据它们所在书架的高度，严格按照低层、中层、高层的顺序，一次搬运一本。\n\n"
	+ "把三本任务书依次送到 CEO OFFICE 内标有“书籍放置点”的位置。拿起普通书或顺序错误的任务书会立即失败。"
)
```

- [ ] **Step 5: Produce the internal snapshot**

Return book entries in the selected low-to-high layout order:

```gdscript
func get_round_snapshot() -> Dictionary:
	var book_entries: Array[Dictionary] = []
	for book: RigidBody3D in _active_books:
		var slot := _slot_by_book.get(book) as Marker3D
		book_entries.append({
			"book": String(book.name),
			"slot": AIPlayPutBookLayout.slot_id(slot),
			"shelf": AIPlayPutBookLayout.shelf_id(slot),
			"height": AIPlayPutBookLayout.height_tier(slot),
			"target": book in _target_books,
		})
	return {
		"seed": _effective_seed,
		"books": book_entries,
		"target_order": _book_names(_target_books),
		"current_target_index": _current_target_index,
		"carried_book": (
			String(_current_carried_book.name)
			if _current_carried_book != null
			else ""
		),
		"completed": _book_names(_completed_books),
		"task_text": task_card.readable_content,
	}


func _book_names(books: Array[RigidBody3D]) -> Array[String]:
	var result: Array[String] = []
	for book: RigidBody3D in books:
		result.append(String(book.name))
	return result
```

The snapshot is used only by Godot tests; do not add it to controller observations.

- [ ] **Step 6: Verify GREEN and commit**

Run:

```bash
bash tests/check_ai_play_put_book_monitor.sh
git diff --check
```

Expected: all seeded setup, marker, count, copy, and snapshot assertions pass.

Commit:

```bash
git add addons/cogito/AIPlay/ai_play_put_book_monitor.gd addons/cogito/DemoScenes/DemoPrefabs/carryable_books.tscn addons/cogito/DemoScenes/COGITO_3_Lobby.tscn tests/ai_play/test_ai_play_put_book_monitor.gd
git commit -m "feat(ai-play): seed six marked shelf books"
```

---

### Task 3: Enforce immediate pickup-order failure and one-book carrying

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_put_book_monitor.gd`
- Modify: `tests/ai_play/test_ai_play_put_book_monitor.gd`
- Test: `tests/check_ai_play_put_book_monitor.sh`

**Interfaces:**
- Consumes: `_target_books` ordered `low`, `middle`, `high` and `_current_target_index` from Task 2.
- Produces: `_expected_target_book() -> RigidBody3D`, `_on_book_carry_state_changed(is_being_carried: bool, book: RigidBody3D, carry_component: Variant) -> void`, and `_update_book_pickup_gate() -> void`.
- Emits: `game_finished("failure", "wrong_book_pickup")` on the first invalid pickup.

- [ ] **Step 1: Add failing pickup-state tests**

Connect `game_finished` to `terminal_results`, configure a fixed seed, and identify `expected`, `later_target`, and `ordinary`. Assert all six components start enabled, then drive the existing carry callback directly:

```gdscript
var expected: RigidBody3D = monitor._target_books[0]
var later_target: RigidBody3D = monitor._target_books[1]
var ordinary: RigidBody3D = _first_ordinary_book(monitor)

for book: RigidBody3D in monitor._active_books:
	_assert(not monitor._carry_component_for_book(book).is_disabled, "all books start available")
_assert(terminal_results.is_empty(), "observing ordinary books does not fail")

monitor._on_book_carry_state_changed(
	true,
	ordinary,
	monitor._carry_component_for_book(ordinary),
)
_assert(terminal_results == [{"outcome": "failure", "reason": "wrong_book_pickup"}], "ordinary pickup fails immediately")

monitor.configure_round(123456)
terminal_results.clear()
later_target = monitor._target_books[1]
monitor._on_book_carry_state_changed(
	true,
	later_target,
	monitor._carry_component_for_book(later_target),
)
_assert(terminal_results == [{"outcome": "failure", "reason": "wrong_book_pickup"}], "later target pickup fails immediately")
```

Configure again, pick the expected book, assert no terminal, assert expected remains enabled and every other unfinished book is disabled. Emit the matching `false` callback and assert the index remains `0`, no terminal appears, and all unfinished books are enabled again.

Add the concrete ordinary-book helper:

```gdscript
func _first_ordinary_book(monitor: Node) -> RigidBody3D:
	for book: RigidBody3D in monitor._active_books:
		if book not in monitor._target_books:
			return book
	return null
```

- [ ] **Step 2: Run the pickup tests and verify RED**

Run:

```bash
bash tests/check_ai_play_put_book_monitor.sh
```

Expected: FAIL because current pickup handling neither validates target order nor disables the other five books.

- [ ] **Step 3: Implement the pickup state machine**

Use one finish helper so only the first terminal result is emitted:

```gdscript
func _finish_round(outcome: String, reason: String) -> void:
	if _round_finished:
		return
	_round_finished = true
	game_finished.emit(outcome, reason)


func _expected_target_book() -> RigidBody3D:
	if _current_target_index < 0 or _current_target_index >= _target_books.size():
		return null
	return _target_books[_current_target_index]


func _on_book_carry_state_changed(
	is_being_carried: bool,
	book: RigidBody3D,
	_carry_component: Variant,
) -> void:
	if _round_finished:
		return
	if is_being_carried:
		if book != _expected_target_book():
			_finish_round("failure", "wrong_book_pickup")
			return
		_current_carried_book = book
		_books_carried_once[book] = true
		_snap_book_to_carry_position(book)
		_update_book_pickup_gate()
	elif _current_carried_book == book:
		_current_carried_book = null
		_update_book_pickup_gate()


func _update_book_pickup_gate() -> void:
	for book: RigidBody3D in _active_books:
		var carry_component: Variant = _carry_component_for_book(book)
		if carry_component == null:
			continue
		if book in _completed_books:
			carry_component.is_disabled = true
		elif _current_carried_book == null:
			carry_component.is_disabled = false
		else:
			carry_component.is_disabled = book != _current_carried_book
```

Do not advance `_current_target_index` on pickup or ordinary drop. Keep the current book's long drop distance and carry-position snap behavior. Clear `_books_carried_once` in every `configure_round` reset.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
bash tests/check_ai_play_put_book_monitor.sh
git diff --check
```

Expected: ordinary and out-of-order pickup fail once, correct pickup does not fail, and the explicit one-book gate opens again after a recoverable outside drop.

Commit:

```bash
git add addons/cogito/AIPlay/ai_play_put_book_monitor.gd tests/ai_play/test_ai_play_put_book_monitor.gd
git commit -m "feat(ai-play): score ordered book pickups"
```

---

### Task 4: Add the CEO placement point and ordered delivery completion

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_put_book_destination_interactable.gd`
- Create: `addons/cogito/AIPlay/ai_play_put_book_destination_drop_interaction.gd`
- Create: `addons/cogito/DemoScenes/DemoPrefabs/ai_play_put_book_destination.tscn`
- Modify: `addons/cogito/AIPlay/ai_play_put_book_monitor.gd`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn:115-117,3342-3361,6252-6583`
- Modify: `tests/ai_play/test_ai_play_put_book_monitor.gd`
- Delete: `addons/cogito/AIPlay/ai_play_put_book_box_interactable.gd`
- Delete: `addons/cogito/AIPlay/ai_play_put_book_box_drop_interaction.gd`
- Test: `tests/check_ai_play_put_book_monitor.sh`

**Interfaces:**
- Consumes: `_expected_target_book()`, `_current_carried_book`, and `_current_target_index` from Task 3.
- Produces: `can_show_destination_interaction() -> bool`, `can_assisted_drop_to_destination() -> bool`, `assisted_drop_to_destination() -> void`, and `_complete_current_delivery(book: RigidBody3D) -> void`.
- Produces scene exports `ceo_door: CogitoDoor`, `destination: StaticBody3D`, `destination_area: Area3D`, and `destination_slots_root: Node3D`.
- Emits: `game_finished("success", "books_in_ceo_office")` after the third delivery.

- [ ] **Step 1: Add failing destination and delivery tests**

Assert the Lobby resolves the four new exports, the destination is visible and interactable for `put_book`, and it has three `Marker3D` display slots. Then exercise assisted delivery:

```gdscript
for index: int in range(3):
	var book: RigidBody3D = monitor._target_books[index]
	var carry_component: Variant = monitor._carry_component_for_book(book)
	carry_component.is_being_carried = true
	monitor._on_book_carry_state_changed(true, book, carry_component)
	monitor.player.global_position = monitor.destination_area.global_position
	_assert(monitor.can_assisted_drop_to_destination(), "current target can use CEO destination")
	monitor.assisted_drop_to_destination()
	_assert(monitor._current_target_index == index + 1, "delivery advances one tier")
	_assert(book in monitor._completed_books, "delivered book is completed")
	_assert(carry_component.is_disabled, "delivered book is locked")
	var display_slot: Marker3D = monitor.destination_slots_root.get_child(index)
	_assert(book.global_position.distance_to(display_slot.global_position) < 0.001, "book snaps to its display slot")
	if index < 2:
		_assert(terminal_results.is_empty(), "partial delivery is nonterminal")

_assert(terminal_results == [{"outcome": "success", "reason": "books_in_ceo_office"}], "three ordered deliveries succeed")
```

Also test that interacting with the destination before carrying leaves the round active, and that dropping the correct first book outside `destination_area` leaves `_current_target_index == 0` and permits the same book to be picked up again. After the successful delivery loop, call `configure_round(123456)` and assert every active book's parent is `_runtime_book_parent`, proving reset detaches completed books from the CEO display anchors.

- [ ] **Step 2: Run the delivery tests and verify RED**

Run:

```bash
bash tests/check_ai_play_put_book_monitor.sh
```

Expected: FAIL because no CEO destination nodes or delivery methods exist.

- [ ] **Step 3: Build the destination prefab**

Create a `StaticBody3D` root named `PutBookDestination` using `AIPlayPutBookDestinationInteractable`. Set `visible = false`, `process_mode = 4`, `collision_layer = 0`, and add it to group `interactable`, so it is inert outside `put_book`. Give it:

- a `0.96 × 0.08 × 0.52` cyan tray `BoxMesh` and matching collision;
- a billboarded `Label3D` at `(0, 0.42, 0)` with text `书籍放置点`, font size `28`, outline `10`;
- `DestinationArea` with collision mask `3` and a `1.10 × 0.55 × 0.70` box shape centered at `(0, 0.25, 0)`;
- `DisplaySlots/Book1`, `Book2`, and `Book3` at `(-0.30, 0.13, 0)`, `(0, 0.13, 0)`, and `(0.30, 0.13, 0)`; and
- `DestinationDropInteraction` using `AIPlayPutBookDestinationDropInteraction`.

The interactable root contract is:

```gdscript
class_name AIPlayPutBookDestinationInteractable
extends StaticBody3D

@export var display_name: String = "书籍放置点"
var interaction_nodes: Array[Node] = []
```

The interaction delegates without owning game state:

```gdscript
class_name AIPlayPutBookDestinationDropInteraction
extends InteractionComponent

var monitor: AIPlayPutBookMonitor
var prefer_while_carrying: bool = true


func _ready() -> void:
	input_map_action = "interact2"
	interaction_text = "放置任务书"
	ignore_open_gui = false


func interact(player_interaction_component: PlayerInteractionComponent) -> void:
	if is_disabled or monitor == null:
		return
	if monitor.can_assisted_drop_to_destination():
		monitor.assisted_drop_to_destination()
	elif player_interaction_component != null:
		player_interaction_component.send_hint(null, "需要先拿起当前任务书")
	was_interacted_with.emit(interaction_text, input_map_action)


func set_disabled(_player: CogitoPlayer) -> bool:
	is_disabled = monitor == null or not monitor.can_show_destination_interaction()
	return is_disabled
```

- [ ] **Step 4: Instance and wire the CEO destination**

Instance the prefab under `UPPER_OFFICE_CEO` at local position `(4.90, 0.08, -3.40)`. Add its root, area, and display-slot root to the monitor NodePath array. Wire `ceo_door` to `../../UPPER_OFFICE_CEO/WindowedDoor/FrontDoor`.

On round setup, activate the destination with this exact helper and unlock the CEO door while leaving it closed and operable:

```gdscript
func _activate_destination() -> void:
	destination.visible = true
	destination.process_mode = Node.PROCESS_MODE_INHERIT
	destination.collision_layer = 3
	destination.collision_mask = 3
	destination_area.monitoring = true
	var interaction := destination.get_node(
		"DestinationDropInteraction"
	) as AIPlayPutBookDestinationDropInteraction
	interaction.monitor = self
	destination.set("interaction_nodes", [interaction])
	var callback := Callable(self, "_on_destination_body_entered")
	if not destination_area.body_entered.is_connected(callback):
		destination_area.body_entered.connect(callback)
	ceo_door.is_locked = false
```

- [ ] **Step 5: Implement acceptance and snapping**

Keep `ASSISTED_DROP_RANGE := 2.0`, remove the box-specific debounce path, and let the destination interaction own the explicit `interact2` request. Completion accepts only `_expected_target_book()` after it has entered the carried state:

```gdscript
func can_assisted_drop_to_destination() -> bool:
	var carry_component: Variant = _carry_component_for_book(_current_carried_book)
	return (
		not _round_finished
		and _current_carried_book == _expected_target_book()
		and carry_component != null
		and carry_component.is_being_carried
		and player.global_position.distance_to(destination_area.global_position)
			<= ASSISTED_DROP_RANGE
	)


func can_show_destination_interaction() -> bool:
	return (
		not _round_finished
		and player != null
		and player.global_position.distance_to(destination_area.global_position)
			<= ASSISTED_DROP_RANGE
	)


func assisted_drop_to_destination() -> void:
	if not can_assisted_drop_to_destination():
		return
	var book := _current_carried_book
	var carry_component: Variant = _carry_component_for_book(book)
	if carry_component.has_method("leave"):
		carry_component.leave()
	_complete_current_delivery(book)


func _complete_current_delivery(book: RigidBody3D) -> void:
	if (
		_round_finished
		or book != _expected_target_book()
		or not _books_carried_once.has(book)
	):
		return
	var display_slot := destination_slots_root.get_child(_current_target_index) as Marker3D
	book.reparent(display_slot, false)
	book.transform = Transform3D.IDENTITY
	book.freeze = true
	book.linear_velocity = Vector3.ZERO
	book.angular_velocity = Vector3.ZERO
	_completed_books.append(book)
	_current_carried_book = null
	_current_target_index += 1
	var carry_component: Variant = _carry_component_for_book(book)
	if carry_component != null:
		carry_component.is_being_carried = false
		carry_component.is_disabled = true
	var marker := book.get_node_or_null("TargetMarker") as Label3D
	if marker != null:
		marker.visible = false
	_update_book_pickup_gate()
	if _current_target_index == _target_books.size():
		_finish_round("success", "books_in_ceo_office")
```

For physical drops, remember the current expected book has been carried, then complete it only when it is no longer carried and overlaps `destination_area`. Poll this condition in `_physics_process` as a fallback for an area event that occurred before release.

Use these exact hooks:

```gdscript
func _on_destination_body_entered(body: Node) -> void:
	_try_complete_destination_book(body as RigidBody3D)


func _try_complete_destination_book(book: RigidBody3D = null) -> void:
	if book == null or book != _expected_target_book():
		return
	var carry_component: Variant = _carry_component_for_book(book)
	if carry_component != null and carry_component.is_being_carried:
		return
	if not _books_carried_once.has(book):
		return
	if book in destination_area.get_overlapping_bodies():
		_complete_current_delivery(book)


func _physics_process(_delta: float) -> void:
	if _round_finished:
		return
	_try_complete_destination_book(_expected_target_book())
```

- [ ] **Step 6: Remove obsolete box code and verify GREEN**

Remove all box preloads, placement arrays, nearest-box assignment dictionaries, box interaction setup, and box completion functions from the monitor. Delete the two obsolete box scripts only after `rg` confirms no scene or code reference remains.

Run:

```bash
rg -n "ai_play_put_book_box|book_in_wrong_box|GROUND_BOX|nearest_box" addons/cogito tests/ai_play/test_ai_play_put_book_monitor.gd
bash tests/check_ai_play_put_book_monitor.sh
godot --headless --path . --editor --quit
git diff --check
```

Expected: the search returns no obsolete put-book box logic, the headless scenario test passes, and the project parses cleanly.

Commit:

```bash
git add -A addons/cogito/AIPlay addons/cogito/DemoScenes/DemoPrefabs addons/cogito/DemoScenes/COGITO_3_Lobby.tscn tests/ai_play/test_ai_play_put_book_monitor.gd
git commit -m "feat(ai-play): deliver ordered books to CEO office"
```

---

### Task 5: Synchronize terminal reasons and the 150-request cap

**Files:**
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd:14-29`
- Modify: `addons/cogito/AIPlay/ai_play_game_over_screen.gd:3-25`
- Modify: `tests/ai_play/test_ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_game_over_screen.gd`
- Modify: `ai_play/src/ai_play/scenarios.py:45-52`
- Modify: `ai_play/tests/test_scenarios.py:40-52,103-145`
- Modify: `ai_play/tests/test_game_session.py:224-242,276-390`

**Interfaces:**
- Consumes: monitor results `success/books_in_ceo_office` and `failure/wrong_book_pickup`.
- Produces: matching Godot and Python allowlists and a hard cap of 150 requests.

- [ ] **Step 1: Write failing registry and session tests**

Change the exact Python assertions to:

```python
assert scenario_act_request_limit("put_book", 500) == 150
assert scenario_act_request_limit("put_book", 120) == 120
assert is_allowed_game_over("put_book", "success", "books_in_ceo_office")
assert is_allowed_game_over("put_book", "failure", "wrong_book_pickup")
assert not is_allowed_game_over("put_book", "success", "book_in_box")
```

Rename the session cap test to `test_put_book_uses_150_request_hard_cap`, update its expectation, send `books_in_ceo_office` in the success-terminal test and logging parameter set, and add a valid failure-terminal test for `wrong_book_pickup`.

In the Godot controller test, assert:

```gdscript
_assert(
	["success", "books_in_ceo_office"] in AIPlayController.SCENARIO_TERMINAL_RESULTS["put_book"],
	"put_book allows CEO delivery success",
)
_assert(
	["failure", "wrong_book_pickup"] in AIPlayController.SCENARIO_TERMINAL_RESULTS["put_book"],
	"put_book allows wrong-pickup failure",
)
```

Add two `_test_result` calls to the game-over screen test:

```gdscript
await _test_result(
	screen_scene,
	"success",
	"books_in_ceo_office",
	"任务成功",
	"三本任务书已按顺序送达 CEO OFFICE",
)
await _test_result(
	screen_scene,
	"failure",
	"wrong_book_pickup",
	"任务失败",
	"拿取了错误的书或搬运顺序不正确",
)
```

- [ ] **Step 2: Run protocol tests and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_scenarios.py ai_play/tests/test_game_session.py -q
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
```

Expected: FAIL on the old `50`, `book_in_box`, and missing `wrong_book_pickup` registrations.

- [ ] **Step 3: Update both allowlists and result copy**

Set the Python definition to:

```python
"put_book": ScenarioDefinition(
    briefing_loader=load_put_book_briefing,
    max_act_requests=150,
    terminal_results=frozenset({
        ("success", "books_in_ceo_office"),
        ("failure", "wrong_book_pickup"),
        ("failure", "max_requests"),
    }),
),
```

Set the Godot controller entry to the same three tuples. Replace game-over labels with:

```gdscript
"books_in_ceo_office": "任务成功",
"wrong_book_pickup": "任务失败",
```

and reasons:

```gdscript
"books_in_ceo_office": "三本任务书已按顺序送达 CEO OFFICE",
"wrong_book_pickup": "拿取了错误的书或搬运顺序不正确",
```

Remove the two obsolete box reasons.

- [ ] **Step 4: Verify GREEN and commit**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_scenarios.py ai_play/tests/test_game_session.py -q
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
git diff --check
```

Expected: all selected Python and Godot protocol tests pass.

Commit:

```bash
git add addons/cogito/AIPlay/ai_play_controller.gd addons/cogito/AIPlay/ai_play_game_over_screen.gd tests/ai_play/test_ai_play_controller.gd tests/ai_play/test_ai_play_game_over_screen.gd ai_play/src/ai_play/scenarios.py ai_play/tests/test_scenarios.py ai_play/tests/test_game_session.py
git commit -m "feat(ai-play): register ordered book outcomes"
```

---

### Task 6: Update the approved briefing and stable documentation

**Files:**
- Modify: `ai_play/src/ai_play/put_book_briefing.py`
- Modify: `ai_play/tests/test_briefing.py:40-59`
- Modify: `ai_play/README.md:212-214,281-283`
- Modify: `docs/wiki/ai-play/system-guide.md:56-65,271-294`

**Interfaces:**
- Consumes: the player-visible rules and outcome contract implemented in Tasks 2–5.
- Produces: a bounded public briefing with no generated answer data and documentation that names the 150-request cap and terminal reasons.

- [ ] **Step 1: Write the failing briefing assertions**

Replace the old success/cap checks with:

```python
assert briefing["success_condition"] == (
    "按低层、中层、高层顺序，将三本带标记的任务书逐本送到 "
    "CEO OFFICE 的书籍放置点。"
)
assert "150" in briefing["failure_condition"]
serialized = repr(briefing)
for required in ["六本", "任务书", "低层", "中层", "高层", "CEO OFFICE", "一次搬运一本"]:
    assert required in serialized
for obsolete in ["目标纸箱", "最近", "jump", "crouch", "高处或低处"]:
    assert obsolete not in serialized
for forbidden in [
    "PutBookShelfSlots",
    "DestinationArea",
    "slot_id",
    "shelf_id",
    "height_tier",
    "round_seed",
]:
    assert forbidden not in serialized
```

- [ ] **Step 2: Run the briefing test and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_briefing.py -q
```

Expected: FAIL because the current briefing describes one book, an archive box, and posture controls.

- [ ] **Step 3: Rewrite only the approved player-visible briefing**

Set the objective and success/failure contract to the exact accepted rules. Add object-guide entries for `task_book_marker` and `ceo_book_placement_point`; retain `readable_document`, `carryable_book`, and `operable_door`; remove `cardboard_box`.

The task-specific rules must state:

```python
[
    "档案室会显示六本可搬运的书，其中三本带有清晰的任务书标记。",
    "先比较三本任务书所在的书架高度，再严格按照低层、中层、高层顺序搬运。",
    "一次只能搬运一本书；当前书送到 CEO OFFICE 的书籍放置点后，再返回搬下一本。",
    "拿起普通书或顺序错误的任务书会立即失败；仅观察或探测交互不会失败。",
    "本任务不要求跳跃或下蹲才能拿到书。",
]
```

Keep `COMMON_CONTROL_RULES`, the existing bounded JPEG loader, and the privacy statement that the reference image is not the current layout or route.

- [ ] **Step 4: Update README and wiki**

Replace every `put_book` statement that mentions one/three nearest boxes, `50`, `book_in_box`, `book_in_wrong_box`, jump, or crouch. Document:

- nine authored shelf slots over three shelves;
- seeded balanced selection of six occupied slots, two per shelf and tier;
- three visible task markers selected one per tier;
- immediate `failure/wrong_book_pickup` on wrong pickup;
- one CEO placement point and `success/books_in_ceo_office` after ordered delivery; and
- hard cap `150`, still tighten-able by `AI_PLAY_MAX_ACT_REQUESTS`.

Keep slot IDs, exact coordinates, selected targets, and seed out of the public briefing section; the internal wiki may describe deterministic initialization without publishing a live round's answer through MCP.

- [ ] **Step 5: Verify GREEN and commit**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_briefing.py ai_play/tests/test_scenarios.py ai_play/tests/test_game_session.py -q
rg -n "put_book.*50|success/book_in_box|book_in_wrong_box|目标纸箱|最近的.*纸箱" ai_play/README.md docs/wiki/ai-play/system-guide.md ai_play/src/ai_play/put_book_briefing.py
git diff --check
```

Expected: tests pass and the search returns no stale put-book contract.

Commit:

```bash
git add ai_play/src/ai_play/put_book_briefing.py ai_play/tests/test_briefing.py ai_play/README.md docs/wiki/ai-play/system-guide.md
git commit -m "docs(ai-play): explain ordered CEO book delivery"
```

---

### Task 7: Run integration, parsing, and visual acceptance checks

**Files:**
- Verify: all files changed by Tasks 1–6
- Modify only when a failure is caused by this feature; add the regression assertion to the nearest existing test before changing production behavior.

**Interfaces:**
- Consumes: complete seeded shelf, pickup-order, destination, protocol, and briefing implementation.
- Produces: evidence that the feature works in the real Lobby scene without breaking the AI-play bridge or other scenarios.

- [x] **Step 1: Generate engine-owned resource metadata and inspect it**

Run:

```bash
godot --headless --path . --editor --quit
git status --short
```

Expected: no parse/UID error. Track only new `.uid` files generated for the three new GDScript resources; do not add `.godot/` or import caches.

- [x] **Step 2: Run focused Godot tests**

Run:

```bash
bash tests/check_ai_play_put_book_monitor.sh
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
bash tests/check_ai_play_lobby.sh
```

Expected: all commands exit `0`; the put-book test prints `AIPlay put-book monitor test passed` and no output contains `SCRIPT ERROR` or `invalid UID`.

- [x] **Step 3: Run the full Python AI-play suite**

Run:

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q
sphinx-build -b html docs docs/_build/html
```

Expected: all Python AI-play tests pass with no real MCP client, model invocation, screenshot persistence, or credentials.

- [x] **Step 4: Run repository safety and formatting checks**

Run:

```bash
bash tests/test_ai_play_secret_scan.sh
rg -n "book_in_box|book_in_wrong_box|ai_play_put_book_box" addons/cogito ai_play tests docs/wiki --glob '!docs/superpowers/**'
git diff --check
git status --short --branch
```

Expected: secret scan and diff check pass; the obsolete-symbol search returns no put-book implementation or contract references; status contains only intentional feature files.

- [ ] **Step 5: Perform local visual acceptance without an external model**

Launch normal human play:

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn -- --ai-play-scenario=put_book
```

Verify in the rendered game:

1. six books occupy the three open archive bookcases, exactly two per bookcase and two per height tier;
2. every book is reachable while standing and none intersects a shelf board;
3. exactly three labels are visible and their heights are unambiguous;
4. ordinary and out-of-order pickups fail immediately;
5. a correct book dropped outside the CEO point can be picked up again;
6. the CEO door is operable and the cyan `书籍放置点` does not overlap the desk, chair, key, contract page, or hidden-door interaction;
7. delivered books occupy three separate tray positions; and
8. low, middle, high delivery ends with the new success message.

Do not run `tools/ai_play_codex_orchestrator.py` as part of this plan. A real 150-request Codex acceptance uses screenshots, credentials, tokens, and persisted trajectories and therefore requires separate explicit user authorization.

- [x] **Step 6: Record completion in the plan and commit final verification**

Mark completed checkboxes only for commands and acceptance checks actually performed. If the human visual check is delegated to the user, leave that checkbox open and report it explicitly.

Commit generated UIDs and the completed plan state:

```bash
git add docs/superpowers/plans/2026-08-01-put-book-ceo-office-ordered-delivery.md
git commit -m "docs(ai-play): complete ordered book delivery plan"
```
