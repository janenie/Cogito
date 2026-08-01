# Meeting Briefing Arrangement Implementation Plan

**Goal:** Add the `arrange_meeting_briefings` Lobby scenario with three distributed relation clues, a deterministic
minimal-unique four-folder seating puzzle, four trusted snap seats, one-shot Verify submission, a sanitized public
briefing, and a hard limit of 200 `act` requests.

**Architecture:** A scene-independent GDScript round model enumerates all 24 assignments and deterministically
selects a three-clue minimal unique puzzle. An inert task setup scene holds dedicated readable records, four copies
of the existing carryable book, four seat markers, labels, spawn anchors, and Verify. A dedicated Monitor owns all
hidden state and the logical `folder_id → seat_id` map. Seat interactions use the existing priority-carry path but
delegate validation, release, snapping, occupancy, and terminal locking to the Monitor.

**Tech Stack:** Godot 4.7, typed GDScript, Godot `.tscn` resources, Python 3, pytest, and Bash scene checks.

## Global Constraints

- Use scenario ID exactly `arrange_meeting_briefings`.
- Reuse `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`; do not duplicate the Lobby.
- Reuse existing carryable-book, readable-page, GenericButton, task-card, Label3D, and game-over assets; add no art.
- Keep the task setup invisible, non-colliding, non-interactive, and state-free unless this scenario is selected.
- Only `-- --ai-play-scenario=arrange_meeting_briefings` selects gameplay; only an additional `--ai-play` enables
  MCP control.
- Keep seed, hidden assignment, normalized clues, candidate solutions, clue-generation state, internal seat IDs,
  and scene paths out of briefing, observations, bridge packets, public terminal data, and trajectory logs.
- The three per-round clues must be learned only from the three in-world records.
- The hard limit is exactly 200 `act` requests; `AI_PLAY_MAX_ACT_REQUESTS` may only reduce it.
- Allow exactly `success/meeting_prepared`, `failure/incorrect_seating_assignment`, and
  `failure/max_requests` for this scenario.
- Verify is one-shot. No action, delayed signal, or collision event may produce a second terminal result.
- Submission uses the trusted logical placement map, never inferred physics coordinates.
- Do not extend trajectory, observation, bridge, workflow-memory, or MCP schemas for optional reasoning metrics.
- Do not run a real external model or MCP acceptance session without separate user approval for screenshots,
  tokens, cost, and trajectory persistence.
- Add tests before implementation, run the narrowest RED test first, then focused GREEN tests, affected full
  suites, secret checks, and finally `git diff --check`.

## Stable Domain Contract

Use these folder IDs in this order:

```gdscript
const FOLDER_IDS: Array[String] = ["atlas", "birch", "crown", "delta"]
```

Use these clockwise seat IDs in this order:

```gdscript
const SEAT_IDS: Array[String] = [
	"tv_side",
	"door_side",
	"opposite_tv",
	"inner_wall",
]
```

Public labels are `ATLAS`, `BIRCH`, `CROWN`, `DELTA`, and `电视侧`, `会议室门侧`, `电视对面侧`,
`内墙侧`. `clockwise_next(A, B)` means B occupies the next entry after A's seat in the cyclic `SEAT_IDS` list.

## File Structure

**Create**

- `ai_play/src/ai_play/arrange_meeting_briefings_briefing.py` — sanitized public rules and bounded Lobby image.
- `addons/cogito/AIPlay/ai_play_meeting_briefing_round.gd` — deterministic permutation, clue, and solver model.
- `addons/cogito/AIPlay/ai_play_meeting_seat_interaction.gd` — priority interaction used while carrying a folder.
- `addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_monitor.gd` — task activation, records, placement map,
  physical snapping, Verify, and terminal behavior.
- `addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_setup.tscn` — inert task-only world objects and anchors.
- `tests/ai_play/test_ai_play_meeting_briefing_round.gd` — exhaustive round-model tests.
- `tests/ai_play/test_ai_play_meeting_seat_interaction.gd` — focused carry/seat delegation tests.
- `tests/ai_play/test_ai_play_arrange_meeting_briefings_monitor.gd` — selected and unselected Lobby integration.
- `tests/check_ai_play_arrange_meeting_briefings_monitor.sh` — dual-mode integration wrapper.

Godot import also creates stable `.gd.uid` files beside the three new scripts.

**Modify**

- `ai_play/src/ai_play/scenarios.py` — scenario registry, 200-request cap, and terminal allowlist.
- `ai_play/tests/test_scenarios.py` — registry, cap, terminal isolation, and ordering coverage.
- `ai_play/tests/test_briefing.py` — public briefing, shared rules, image, and hidden-state rejection.
- `ai_play/tests/test_game_session.py` — 200-request session cap and accepted terminal packets.
- `addons/cogito/AIPlay/ai_play_controller.gd` — matching Godot scenario terminal allowlist.
- `addons/cogito/AIPlay/ai_play_game_over_screen.gd` — Chinese copy for both task results.
- `tests/ai_play/test_ai_play_controller.gd` — scenario selection, terminal validation, and idempotency.
- `tests/ai_play/test_ai_play_game_over_screen.gd` — visible result copy.
- `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn` — setup instance and direct Controller Monitor child.
- `tests/check_ai_play_lobby.sh` — stable wiring and inert-default checks.
- `README_AI_PLAY.md`, `ai_play/README.md`, `docs/wiki/ai-play/system-guide.md`, and
  `docs/wiki/development/contributor-guide.md` — launch, rules, outcomes, privacy, and verification.

---

### Task 1: Register the Sanitized Python Scenario

**Files:**

- Create: `ai_play/src/ai_play/arrange_meeting_briefings_briefing.py`
- Modify: `ai_play/src/ai_play/scenarios.py`
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/tests/test_game_session.py`

**Produces:** `load_arrange_meeting_briefings_briefing() -> tuple[dict, bytes]`, one ordered registry entry with a
hard cap of 200, and three legal terminal pairs.

- [ ] **Step 1: Add failing registry, cap, and terminal tests**

Append the new ID to the exact ordered tuple in `test_scenario_registry_exposes_only_allowlisted_scenarios()` and
assert:

```python
assert is_supported_scenario("arrange_meeting_briefings")
assert scenario_act_request_limit("arrange_meeting_briefings", 500) == 200
assert scenario_act_request_limit("arrange_meeting_briefings", 125) == 125
assert is_allowed_game_over(
    "arrange_meeting_briefings", "success", "meeting_prepared"
)
assert is_allowed_game_over(
    "arrange_meeting_briefings",
    "failure",
    "incorrect_seating_assignment",
)
assert is_allowed_game_over(
    "arrange_meeting_briefings", "failure", "max_requests"
)
assert not is_allowed_game_over(
    "find_contract", "success", "meeting_prepared"
)
```

Add a `GameSession` test using the existing `make_scenario_session()` helper and assert the 200th request triggers
the existing max-request flow while a lower configured limit remains respected.

- [ ] **Step 2: Add the failing public briefing test**

Add the scenario ID to every shared all-scenario loop and add a focused test:

```python
def test_arrange_meeting_briefings_briefing_is_public_and_bounded():
    briefing, image_bytes = load_scenario_briefing(
        "arrange_meeting_briefings"
    )

    assert briefing["game_id"] == "arrange_meeting_briefings"
    assert "CEO 办公室" in repr(briefing)
    assert "档案室" in repr(briefing)
    assert "休息室" in repr(briefing)
    assert "ATLAS" in repr(briefing)
    assert "顺时针" in repr(briefing)
    assert "200 次 act 请求" in briefing["failure_condition"]
    assert "一次" in repr(briefing)
    assert image_bytes.startswith(b"\xff\xd8\xff")
    assert image_bytes.endswith(b"\xff\xd9")
    assert len(image_bytes) <= 2 * 1024 * 1024

    serialized = repr(briefing).lower()
    for forbidden in [
        "round_seed",
        "hidden_assignment",
        "candidate_solutions",
        "clue_type",
        "tv_side",
        "door_side",
        "nodepath",
        "meeting_room/",
    ]:
        assert forbidden not in serialized
```

- [ ] **Step 3: Run the focused Python tests and confirm RED**

```bash
PYTHONPATH=ai_play/src python3 -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_game_session.py -q
```

Expected: registry, briefing, and cap assertions fail because the scenario is not registered.

- [ ] **Step 4: Implement the loader and registry entry**

Follow the existing explicit loader pattern. Reuse `COMMON_CONTROL_RULES` and the bounded Lobby reference JPEG.
The public objective must tell the player to read the entrance task card, investigate the three named areas, solve
four folder-to-seat assignments, and submit once. It may describe visible seat names and the clockwise label, but
must not contain the three generated clue strings.

Add to `_SCENARIOS`:

```python
"arrange_meeting_briefings": ScenarioDefinition(
    briefing_loader=load_arrange_meeting_briefings_briefing,
    max_act_requests=200,
    terminal_results=frozenset({
        ("success", "meeting_prepared"),
        ("failure", "incorrect_seating_assignment"),
        ("failure", "max_requests"),
    }),
),
```

- [ ] **Step 5: Re-run focused Python tests and commit**

```bash
PYTHONPATH=ai_play/src python3 -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_game_session.py -q
git add \
  ai_play/src/ai_play/arrange_meeting_briefings_briefing.py \
  ai_play/src/ai_play/scenarios.py \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_game_session.py
git commit -m "feat(ai-play): register meeting briefing task"
```

---

### Task 2: Add Matching Godot Terminal Contracts

**Files:**

- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_game_over_screen.gd`
- Modify: `tests/ai_play/test_ai_play_controller.gd`
- Modify: `tests/ai_play/test_ai_play_game_over_screen.gd`

- [ ] **Step 1: Add failing Controller tests**

Assert command-line selection accepts `arrange_meeting_briefings`, rejects duplicate/malformed scenario arguments,
and permits only these pairs for the new scenario:

```gdscript
["success", "meeting_prepared"]
["failure", "incorrect_seating_assignment"]
["failure", "max_requests"]
```

Also assert cross-scenario uses such as `find_key/success/meeting_prepared` and
`arrange_meeting_briefings/success/circuit_repaired` are rejected. Reuse the existing repeated terminal test to
prove the first accepted terminal remains authoritative.

- [ ] **Step 2: Add failing game-over copy tests**

Assert `meeting_prepared` renders “任务成功 / 会议资料已正确分发”, and
`incorrect_seating_assignment` renders “任务失败 / 会议资料席位不正确”.

- [ ] **Step 3: Run both Godot tests and confirm RED**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
```

- [ ] **Step 4: Implement matching allowlists and copy, then commit**

Add the same three pairs to `SCENARIO_TERMINAL_RESULTS`. Add both reasons to `OUTCOME_TEXT` and `REASON_TEXT`.
Do not change protocol version or public packet shape.

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
git add \
  addons/cogito/AIPlay/ai_play_controller.gd \
  addons/cogito/AIPlay/ai_play_game_over_screen.gd \
  tests/ai_play/test_ai_play_controller.gd \
  tests/ai_play/test_ai_play_game_over_screen.gd
git commit -m "feat(ai-play): allow meeting briefing outcomes"
```

---

### Task 3: Build the Deterministic Minimal-Unique Round Model

**Files:**

- Create: `addons/cogito/AIPlay/ai_play_meeting_briefing_round.gd`
- Create after import: `addons/cogito/AIPlay/ai_play_meeting_briefing_round.gd.uid`
- Create: `tests/ai_play/test_ai_play_meeting_briefing_round.gd`

**Produces:** a `RefCounted` model with `configure(seed_value)`, assignment enumeration, clue evaluation, solver,
public clue text formatting, and a trusted test snapshot.

- [ ] **Step 1: Write the failing pure-model test**

Create a `SceneTree` test. Verify same-seed determinism and exhaustive generation:

```gdscript
var first := AIPlayMeetingBriefingRound.new()
var second := AIPlayMeetingBriefingRound.new()
first.configure(87123)
second.configure(87123)
_assert(first.snapshot() == second.snapshot(), "same seed is deterministic")

for seed_value: int in range(1, 513):
	var round_state := AIPlayMeetingBriefingRound.new()
	round_state.configure(seed_value)
	var state: Dictionary = round_state.snapshot()
	_assert(_is_assignment_permutation(state.solution), "solution is one-to-one")
	_assert(state.clues.size() == 3, "round has three clues")
	_assert(state.record_clues.keys().size() == 3, "three records are assigned")
	var matches: Array = round_state.solve(state.clues)
	_assert(matches.size() == 1, "all clues have one solution")
	_assert(matches[0] == state.solution, "unique solution is hidden answer")
	for removed_index: int in range(3):
		var reduced: Array = state.clues.duplicate(true)
		reduced.remove_at(removed_index)
		_assert(round_state.solve(reduced).size() >= 2, "every clue is necessary")
```

For every generated clue, assert it matches the hidden solution, its canonical key is unique, and it reduces the
24-permutation universe. Explicitly build fixtures for all five clue kinds and assert adjacent is symmetric,
opposite is symmetric, clockwise-next is directional, and `SEAT_IDS` wraps from `inner_wall` to `tv_side`.

Assert `all_assignments().size() == 24`, every assignment is one-to-one, and all generated public clue strings use
only public folder and seat labels. Assert record keys sort to `['archive', 'break_room', 'ceo']` and their clue
indexes are a permutation of `[0, 1, 2]`.

- [ ] **Step 2: Run the pure-model test and confirm RED**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_meeting_briefing_round.gd
```

- [ ] **Step 3: Implement assignment enumeration and clue predicates**

Use the stable IDs from this plan. Generate all 24 assignments recursively or by a fixed four-level loop; always
iterate arrays in declared order. Represent clues with dictionaries containing `kind` and only the required
`folder`, `seat`, `folder_a`, `folder_b`, `from_folder`, or `to_folder` keys.

Implement:

```gdscript
func all_assignments() -> Array[Dictionary]
func clue_matches(clue: Dictionary, assignment: Dictionary) -> bool
func solve(clues: Array) -> Array[Dictionary]
func canonical_clue_key(clue: Dictionary) -> String
func clue_text(clue: Dictionary) -> String
```

Canonicalize both folder IDs for symmetric clues by declared `FOLDER_IDS` order. Do not sort directional clues.
Adjacent uses cyclic distance 1 or 3; opposite uses distance 2; clockwise-next uses `(from_index + 1) % 4`.

- [ ] **Step 4: Implement deterministic puzzle generation**

`configure()` must:

1. seed one RNG, or randomize it only when the provided value is zero;
2. Fisher–Yates shuffle a duplicate `SEAT_IDS` and zip it to `FOLDER_IDS` as the hidden solution;
3. enumerate every true exact, adjacent, opposite, clockwise-next, and not-seat clue;
4. canonicalize, sort by canonical key, and remove duplicates;
5. discard clues whose match count is 24;
6. enumerate every `i < j < k` triplet;
7. retain only triplets with exactly one combined match equal to the hidden solution and at least two matches after
   removing any one clue;
8. select one retained triplet by RNG index, shuffle only its display order, then shuffle `[ceo, archive,
   break_room]` to assign clue indexes to records.

If no valid triplet exists, use `push_error()` and return false from `configure()`; never publish a degraded puzzle.
The test snapshot may deep-copy `seed`, `solution`, `clues`, and `record_clues`, but no runtime bridge caller may
consume it.

- [ ] **Step 5: Import, run exhaustive tests, and commit**

```bash
godot --headless --path . --editor --quit
godot --headless --path . --script tests/ai_play/test_ai_play_meeting_briefing_round.gd
git add \
  addons/cogito/AIPlay/ai_play_meeting_briefing_round.gd \
  addons/cogito/AIPlay/ai_play_meeting_briefing_round.gd.uid \
  tests/ai_play/test_ai_play_meeting_briefing_round.gd
git commit -m "feat(ai-play): model meeting briefing rounds"
```

---

### Task 4: Build the Priority Seat Interaction

**Files:**

- Create: `addons/cogito/AIPlay/ai_play_meeting_seat_interaction.gd`
- Create after import: `addons/cogito/AIPlay/ai_play_meeting_seat_interaction.gd.uid`
- Create: `tests/ai_play/test_ai_play_meeting_seat_interaction.gd`

**Produces:** an `InteractionComponent` recognized by the existing
`PlayerInteractionComponent._priority_carry_interactions()` path.

- [ ] **Step 1: Write a failing focused interaction test**

Use a fake Monitor Node exposing `place_carried_folder(seat_id, player_interaction) -> Dictionary`. Assert the
interaction defaults to `input_map_action = "interact2"`, `interaction_text = "放置资料"`,
`prefer_while_carrying = true`, and delegates the stable seat ID and exact player interaction object once.

Assert disabled interactions do nothing; a rejected `occupied` result sends “该席位已有资料”; an
`invalid_folder` or `not_carrying` result sends “请先拿起会议资料”; accepted placement emits
`was_interacted_with` but never leaks whether the folder is correct.

- [ ] **Step 2: Run the test and confirm RED**

```bash
godot --headless --path . --script tests/ai_play/test_ai_play_meeting_seat_interaction.gd
```

- [ ] **Step 3: Implement and verify the interaction**

Use:

```gdscript
class_name AIPlayMeetingSeatInteraction
extends InteractionComponent

var monitor: Node
var seat_id: String = ""
var prefer_while_carrying: bool = true
```

The interaction must not inspect coordinates or decide correctness. It delegates the operation to the Monitor,
maps only neutral rejection reasons to hints, and emits the normal interaction audit signal.

```bash
godot --headless --path . --editor --quit
godot --headless --path . --script tests/ai_play/test_ai_play_meeting_seat_interaction.gd
git add \
  addons/cogito/AIPlay/ai_play_meeting_seat_interaction.gd \
  addons/cogito/AIPlay/ai_play_meeting_seat_interaction.gd.uid \
  tests/ai_play/test_ai_play_meeting_seat_interaction.gd
git commit -m "feat(ai-play): add trusted meeting seat interaction"
```

---

### Task 5: Build and Wire the Playable Lobby Task

**Files:**

- Create: `addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_monitor.gd`
- Create after import: `addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_monitor.gd.uid`
- Create: `addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_setup.tscn`
- Create: `tests/ai_play/test_ai_play_arrange_meeting_briefings_monitor.gd`
- Create: `tests/check_ai_play_arrange_meeting_briefings_monitor.sh`
- Modify: `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`
- Modify: `tests/check_ai_play_lobby.sh`

**Produces:** an inert setup and a direct Controller child Monitor exposing `scenario_id`, `configure_round()`,
`place_carried_folder()`, `get_round_snapshot()` for trusted tests, `show_result()`, and `game_finished`.

- [ ] **Step 1: Write the failing selected/unselected integration test**

Selected mode must instantiate the Lobby, await two process frames, detach the shared result screen during terminal
assertions, and verify:

```gdscript
var monitor: Node = lobby.get_node(
	"AIPlayController/ArrangeMeetingBriefingsMonitor"
)
_assert(monitor.scenario_id == "arrange_meeting_briefings", "scenario ID matches")
_assert(lobby.get_node("ArrangeMeetingBriefingsSetup").visible, "setup is visible")
_assert(monitor.folder_nodes.size() == 4, "four folders are active")
_assert(monitor.seat_interactions.size() == 4, "four seats are active")
_assert(monitor.record_readables.size() == 3, "three records are active")
_assert(monitor.task_card.readable_content.contains("CEO 办公室"), "task card names CEO")
_assert(monitor.task_card.readable_content.contains("档案室"), "task card names archive")
_assert(monitor.task_card.readable_content.contains("休息室"), "task card names break room")
```

For a fixed seed, compare the trusted model snapshot across reconfiguration and assert each record contains exactly
the clue assigned to that area. Assert the task card contains no generated clue text or hidden IDs.

Use real task folder nodes and the Lobby player's actual `PlayerInteractionComponent`; add a test helper that makes
the component carry the selected folder through its normal `CogitoCarryableComponent.carry()` path. Then test:

- placing each folder into a different seat produces a four-entry logical map and snaps to the exact marker;
- an occupied seat rejects a second folder without calling `leave()`;
- a non-task carried body is rejected;
- `carry_state_changed(true)` on an occupied folder immediately clears both folder and seat entries;
- the removed folder can be placed into another seat;
- repeated false/true carry signals do not corrupt the map.

Use fresh rounds for terminal checks. Apply `snapshot.solution` through the placement API, press Verify, and expect
exactly `success/meeting_prepared`. Submit one swapped pair and one incomplete map separately, expecting exactly
`failure/incorrect_seating_assignment`. After each terminal, repeat Verify, placement, take-back, and delayed
signals and assert one terminal plus an unchanged frozen map.

Unselected mode must assert Setup is hidden and processing-disabled, every task collision layer/mask is zero,
every task interaction is disabled, record contents remain their harmless scene defaults, no folder map or round
snapshot exists, and ordinary Lobby objects behave unchanged.

- [ ] **Step 2: Add the dual-mode shell wrapper and confirm RED**

Run the same test twice:

```bash
godot --headless --path . \
  --script tests/ai_play/test_ai_play_arrange_meeting_briefings_monitor.gd \
  -- --ai-play-scenario=arrange_meeting_briefings
godot --headless --path . \
  --script tests/ai_play/test_ai_play_arrange_meeting_briefings_monitor.gd
```

The wrapper must reject nonzero exit, `SCRIPT ERROR`, parser errors, and invalid UIDs, and require distinct selected
and isolation pass sentinels.

- [ ] **Step 3: Create the inert setup scene**

Reuse these resources:

```text
res://addons/cogito/DemoScenes/DemoPrefabs/carryable_books.tscn
res://addons/cogito/DemoScenes/DemoPrefabs/ripped_page_a_readable.tscn
res://addons/cogito/DemoScenes/DemoPrefabs/generic_button.tscn
res://addons/cogito/Components/Interactions/BasicInteraction.tscn
res://addons/cogito/CogitoObjects/cogito_object.gd
res://addons/cogito/AIPlay/ai_play_meeting_seat_interaction.gd
```

Root `ArrangeMeetingBriefingsSetup` starts with `visible = false` and `process_mode = 4`. Create stable nodes:

```text
PlayerSpawn
TaskCardAnchor
RecordCEO
RecordArchive
RecordBreakRoom
FolderAtlas
FolderBirch
FolderCrown
FolderDelta
SeatTVSide
SeatDoorSide
SeatOppositeTV
SeatInnerWall
ClockwiseLabel
VerifyButton
VerifyLabel
```

Each folder gets a child `Label3D` with its uppercase name. Each seat is a small `StaticBody3D` using the existing
CogitoObject script, a collision shape, visible marker mesh, environmental `Label3D`, `SnapAnchor`, and the custom
seat interaction. Use neutral colors that do not encode correctness.

Place the four folders on the existing meeting-room side desk near the television. Place four seat markers around
the conference table in the physical clockwise order TV → door → TV opposite → inner wall, with the arrow label on
the table. Put Verify beside the conference-room exit with its button and label fully clear of the wall and door
swing. Put records at reachable, readable positions in the CEO office, archive, and break room. Put spawn and task
card inside the entrance with a clear line of sight and no occluding backing wall.

All task rigid/static bodies start with collision layers and masks zero. All Carryable, Readable, seat, and Verify
interactions start disabled. Do not mutate the source prefabs.

- [ ] **Step 4: Implement Monitor activation and record setup**

Export explicit references for setup, player, task card, game-over screen, three ReadableComponents, four folder
RigidBody3Ds, four seat interactions, four SnapAnchors, Verify, spawn, task-card anchor, and `round_seed`.

In `_ready()`, return before any mutation unless the parent Controller selects the exact scenario. Deferred
activation must validate all exports, show/process Setup, restore task collision layers/masks, enable the task
interactions, move the player and task card, connect signals exactly once, and call `configure_round(round_seed)`.

`configure_round()` clears the logical maps and terminal state, returns all folders to their desk transforms,
unfreezes no folder, enables interactions, configures the pure model, and writes one natural-language clue into
each assigned record. It writes the public task-card rules but no clue text. Reconfiguration is a trusted test path,
not player interaction.

- [ ] **Step 5: Implement trusted placement and take-back**

Maintain both maps:

```gdscript
var _folder_to_seat: Dictionary = {}
var _seat_to_folder: Dictionary = {}
```

`place_carried_folder(seat_id, player_interaction)` must validate active/nonterminal state, empty seat, valid seat,
and that `player_interaction.carried_object` is the registered `CogitoCarryableComponent` of a task folder. On
acceptance, call `leave()`, zero linear/angular velocity, set `freeze = true`, assign the folder's global transform
to the seat SnapAnchor, and update both maps before returning `{"accepted": true}`.

Connect every folder's `carry_state_changed` with its folder ID. When it emits true for a placed folder, remove
both map entries immediately and idempotently. The Monitor must never use overlap or distance to infer occupancy.

- [ ] **Step 6: Implement Verify, locking, and restoration**

Verify first sets `_round_finished = true`, copies the map, disables folder/seat/Verify interactions, then checks
that the map has exactly all four folders and matches the hidden solution. Emit exactly one allowed pair.

`show_result()` forwards to the shared game-over screen. After terminal, placement and carry callbacks return
without mutation. `_exit_tree()` disconnects task signals. Since every visible object is a dedicated task instance,
ordinary Lobby state needs no restoration beyond keeping the task root inert when unselected.

- [ ] **Step 7: Wire the Lobby and static contract**

Instance `ArrangeMeetingBriefingsSetup` once at the Lobby root. Add
`ArrangeMeetingBriefingsMonitor` as a direct `AIPlayController` child and wire every export with explicit
NodePaths. Do not add hidden state to metadata or shared task nodes.

Extend `tests/check_ai_play_lobby.sh` to assert both new ext resources, the direct Monitor child, exact scenario ID,
setup instance, three records, four folders, four stable seat nodes, ClockwiseLabel, Verify, spawn/task-card anchors,
and inert root defaults. Parse task interaction blocks to require disabled defaults and task body blocks to require
zero collision defaults.

- [ ] **Step 8: Import and run focused integration tests**

```bash
godot --headless --path . --editor --quit
godot --headless --path . --script tests/ai_play/test_ai_play_meeting_briefing_round.gd
godot --headless --path . --script tests/ai_play/test_ai_play_meeting_seat_interaction.gd
bash tests/check_ai_play_arrange_meeting_briefings_monitor.sh
bash tests/check_ai_play_lobby.sh
```

- [ ] **Step 9: Perform local visual/playability QA**

Launch without MCP control:

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=arrange_meeting_briefings
```

Verify the player starts indoors; the task card is unobstructed; all three records are reachable and readable; all
four folder labels are readable; the TV, door, opposite-TV, inner-wall, and clockwise semantics are visually
unambiguous; seats accept and release folders; and Verify is outside walls and door motion. Adjust only task setup
transforms and marker sizes until these checks pass. Do not start an external agent.

- [ ] **Step 10: Commit the playable task**

```bash
git add \
  addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_monitor.gd \
  addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_monitor.gd.uid \
  addons/cogito/AIPlay/ai_play_arrange_meeting_briefings_setup.tscn \
  addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  tests/ai_play/test_ai_play_arrange_meeting_briefings_monitor.gd \
  tests/check_ai_play_arrange_meeting_briefings_monitor.sh \
  tests/check_ai_play_lobby.sh
git commit -m "feat(ai-play): add meeting briefing arrangement task"
```

---

### Task 6: Synchronize Documentation and Run Full Verification

**Files:**

- Modify: `README_AI_PLAY.md`
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/development/contributor-guide.md`

- [ ] **Step 1: Update user and MCP documentation**

Add both launch forms:

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play-scenario=arrange_meeting_briefings

godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  -- --ai-play --ai-play-scenario=arrange_meeting_briefings
```

Document the three investigation areas, four public folder names, four environmental seats, clockwise marker,
pre-submit rearrangement, one-shot Verify, 200-request cap, and exact terminal pairs. State that clues exist only in
world records and hidden solving state never enters the MCP result.

- [ ] **Step 2: Update architecture and contributor verification docs**

Explain the 24-permutation trusted solver, minimal-unique clue contract, logical placement map, and unselected
isolation. Add the two dedicated Godot tests and integration wrapper to the contributor guide.

- [ ] **Step 3: Run focused cross-layer verification**

```bash
PYTHONPATH=ai_play/src python3 -m pytest \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_bridge_server.py \
  ai_play/tests/test_game_session.py -q
godot --headless --path . --script tests/ai_play/test_ai_play_meeting_briefing_round.gd
godot --headless --path . --script tests/ai_play/test_ai_play_meeting_seat_interaction.gd
bash tests/check_ai_play_arrange_meeting_briefings_monitor.sh
godot --headless --path . --script tests/ai_play/test_ai_play_controller.gd
godot --headless --path . --script tests/ai_play/test_ai_play_game_over_screen.gd
bash tests/check_ai_play_lobby.sh
```

- [ ] **Step 4: Run affected full regressions and privacy checks**

```bash
PYTHONPATH=ai_play/src python3 -m pytest ai_play/tests -q
bash tests/check_ai_play_put_book_monitor.sh
bash tests/check_ai_play_repair_lighting_circuit_monitor.sh
bash tests/check_ai_play_greet_npc_meeting_monitor.sh
bash tests/check_ai_play_start_script.sh
bash tests/test_ai_play_secret_scan.sh
```

Confirm all previous Lobby tasks remain unchanged when this scenario is not selected. Inspect serialized public
briefing and terminal payloads again for hidden-state terms and actual clue text.

- [ ] **Step 5: Inspect the complete diff**

```bash
git status --short
git diff --stat 4149f75d
git diff --check
git diff -- \
  addons/cogito/DemoScenes/COGITO_3_Lobby.tscn \
  addons/cogito/AIPlay \
  ai_play/src/ai_play \
  ai_play/tests \
  tests \
  README_AI_PLAY.md \
  ai_play/README.md \
  docs/wiki
```

Do not add `.godot/`, caches, local logs, screenshots, credentials, runtime memory, or generated temporary files.

- [ ] **Step 6: Commit documentation**

```bash
git add \
  README_AI_PLAY.md \
  ai_play/README.md \
  docs/wiki/ai-play/system-guide.md \
  docs/wiki/development/contributor-guide.md
git commit -m "docs(ai-play): document meeting briefing task"
```

- [ ] **Step 7: Run final clean-tree verification and report**

```bash
git diff --check HEAD^
git status --short --branch
```

Report every executed test command and result, the manual visual checks performed, and the branch/commit IDs.
State explicitly that no real external model acceptance run was performed.
