# Laboratory Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `COGITO_4_Laboratory.tscn` into a deterministic three-attempt experiment puzzle that is playable by humans and by the existing protocol-3 AI Play MCP tools.

**Architecture:** A pure case library computes all battery/sample/treatment outcomes and rejects invalid cases. A scene-local manager owns round state, interactions, UI, reset, and terminal signals. AI Play reuses the current controller, executor, probe, bridge, and four MCP tools; a Laboratory observer contributes one strictly validated public DTO.

**Tech Stack:** Godot 4.7 GDScript and `.tscn`, Python 3.12, FastMCP, pytest.

## Global Constraints

- AI Play remains disabled unless Godot receives exact user argument `-- --ai-play`.
- Godot connects only to numeric loopback `127.0.0.1:8765`; protocol version remains 3.
- MCP tools remain exactly `briefing`, `observe`, `act`, and `stop`.
- Do not add a shoot/wield action; all required experiment operations use current `interact` or `interact2` actions.
- Each complete experiment consumes one of exactly three attempts; incomplete setup consumes none.
- The third successful experiment wins before attempt exhaustion can fail the round.
- Hidden case IDs, mappings, seeds, and unexecuted outcomes never enter briefing or observations.
- Escape, stop, disconnect, invalid data, and node teardown release simulated input.

---

### Task 1: Deterministic Experiment Case Library

**Files:**
- Create: `addons/cogito/DemoScenes/Laboratory/laboratory_experiment_cases.gd`
- Test: `tests/laboratory/test_laboratory_experiment_cases.gd`

**Interfaces:**
- Produces: `LaboratoryExperimentCases.build_round(seed: int) -> Dictionary`.
- Produces: `LaboratoryExperimentCases.evaluate(round_data: Dictionary, battery: String, sample: String, treatment: String) -> Dictionary`.
- Produces result fields `power`, `current`, `stability`, `temperature`, `lamp`, `safe`, and `success`.

- [ ] **Step 1: Write a failing exhaustive case test**

```gdscript
var round_data := Cases.build_round(31)
var successes: Array[Dictionary] = []
for battery: String in ["alpha", "beta", "gamma"]:
	for sample: String in ["a", "b", "c"]:
		for treatment: String in ["dry", "wet", "heated"]:
			var result := Cases.evaluate(round_data, battery, sample, treatment)
			if result.success:
				successes.append({"battery": battery, "sample": sample, "treatment": treatment})
_assert(successes.size() == 1, "each generated round has one solution")
```

- [ ] **Step 2: Run the test and verify it fails because the case library is missing**

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_cases.gd`
Expected: non-zero exit with missing preload.

- [ ] **Step 3: Implement 12 allowlisted cases and deterministic mapping**

```gdscript
class_name LaboratoryExperimentCases
extends RefCounted

const BATTERIES := ["low", "nominal", "high"]
const LABELS := ["alpha", "beta", "gamma"]
const SAMPLES := ["a", "b", "c"]
const TREATMENTS := ["dry", "wet", "heated"]

static func build_round(seed: int) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var case: Dictionary = CASES[rng.randi_range(0, CASES.size() - 1)].duplicate(true)
	case["battery_map"] = _shuffled_map(rng, LABELS, BATTERIES)
	case["sample_map"] = _shuffled_map(rng, SAMPLES, case.sample_profiles)
	_validate_unique_solution(case)
	return case
```

Each protocol has four fixed cases. Evaluation is table-driven and applies at most one public environment modifier; it never calls a random function.

- [ ] **Step 4: Run the exhaustive test for seeds 0 through 255**

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_cases.gd`
Expected: `Laboratory experiment case tests passed` and exit 0.

- [ ] **Step 5: Commit the case library**

```bash
git add addons/cogito/DemoScenes/Laboratory/laboratory_experiment_cases.gd tests/laboratory/test_laboratory_experiment_cases.gd
git commit -m "feat: add laboratory experiment case library"
```

### Task 2: Three-Attempt Experiment State Machine

**Files:**
- Create: `addons/cogito/DemoScenes/Laboratory/laboratory_experiment_manager.gd`
- Test: `tests/laboratory/test_laboratory_experiment_manager.gd`

**Interfaces:**
- Consumes: `LaboratoryExperimentCases.build_round()` and `.evaluate()`.
- Produces: `select_battery(label: String)`, `select_sample(label: String)`, `select_treatment(state: String)`, `set_metal_bar_installed(installed: bool)`, `run_experiment()`.
- Produces: `ai_play_public_state() -> Dictionary` with the exact Laboratory DTO fields from the game script.
- Emits: `round_finished(outcome: String, reason: String)` and `public_state_changed()`.

- [ ] **Step 1: Write failing state-machine tests**

Cover these assertions:

```gdscript
manager.run_experiment()
_assert(manager.attempts_used == 0, "incomplete setup does not consume an attempt")

manager.force_setup_for_tests(wrong_setup)
manager.run_experiment()
_assert(manager.attempts_used == 1, "complete wrong setup consumes one attempt")

manager.force_setup_for_tests(correct_setup)
manager.run_experiment()
await manager.round_finished
_assert(events == [["success", "experiment_completed"]], "success emits once")
```

Also verify a wrong third run emits only `failure/experiment_attempts_exhausted`, while a correct third run emits success.

- [ ] **Step 2: Run the manager test and confirm missing implementation failure**

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_manager.gd`
Expected: non-zero exit with missing preload.

- [ ] **Step 3: Implement the manager state machine**

Use states `READY`, `RUNNING`, `RESETTING`, and `FINISHED`. Lock the setup at run start, evaluate once, expose the measurement immediately, then wait three seconds only for a successful stable-lamp result. Failed runs reset transient treatment state without removing placed objects.

```gdscript
func run_experiment() -> void:
	if state != State.READY or not _setup_ready():
		status_code = "setup_incomplete"
		public_state_changed.emit()
		return
	attempts_used += 1
	state = State.RUNNING
	last_result = Cases.evaluate(round_data, battery_installed, selected_sample, sample_state)
	if last_result.success:
		await get_tree().create_timer(3.0).timeout
		_finish("success", "experiment_completed")
	elif attempts_used >= 3:
		_finish("failure", "experiment_attempts_exhausted")
	else:
		_reset_transient_state()
```

- [ ] **Step 4: Run manager and case tests**

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_manager.gd`
Expected: pass.

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_cases.gd`
Expected: pass.

- [ ] **Step 5: Commit the manager**

```bash
git add addons/cogito/DemoScenes/Laboratory/laboratory_experiment_manager.gd tests/laboratory/test_laboratory_experiment_manager.gd
git commit -m "feat: add laboratory experiment state machine"
```

### Task 3: Experiment Station and Laboratory Scene Integration

**Files:**
- Create: `addons/cogito/DemoScenes/Laboratory/laboratory_experiment_station.tscn`
- Create: `addons/cogito/DemoScenes/Laboratory/laboratory_experiment_station.gd`
- Modify: `addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn`
- Test: `tests/laboratory/test_laboratory_experiment_scene.gd`

**Interfaces:**
- Consumes manager selection and run methods.
- Produces fixed interactables for sample A/B/C, dry/wet/heated, run, and reset.
- Updates a readable task card and visible 3D status/history labels from public manager state.

- [ ] **Step 1: Write a failing scene contract test**

Load and instantiate `COGITO_4_Laboratory.tscn`; assert `LaboratoryExperiment`, its manager, task card, eight fixed buttons, status labels, battery anchors, bar anchors, and existing Player/Cathodes/slots are all present. Assert all required buttons use `interact` or `interact2` only.

- [ ] **Step 2: Run the scene test and confirm the station is missing**

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_scene.gd`
Expected: fail with missing `LaboratoryExperiment`.

- [ ] **Step 3: Build the station as a focused subscene**

Instance existing `generic_button.tscn`, `note_welcome.tscn`, battery, metal bar, slots, lamp, and Label3D resources. Connect each `pressed` signal to one manager method. Treatment buttons call manager state changes and trigger existing water/fire VFX; they do not synthesize weapon input.

- [ ] **Step 4: Instance the station in the Laboratory scene**

Place it inside `NavigationRegion3D/SYSTEMIC_PROPERTIES`, wire existing Cathodes and lamp references, and add six battery, three bar, and two task-card safe anchors. Move the player spawn near the station only when this experiment scenario is requested; normal Laboratory layout remains usable.

- [ ] **Step 5: Run scene and state-machine tests**

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_scene.gd`
Expected: pass.

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_manager.gd`
Expected: pass.

- [ ] **Step 6: Commit the playable scene**

```bash
git add addons/cogito/DemoScenes/Laboratory addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn tests/laboratory
git commit -m "feat: add playable laboratory experiment"
```

### Task 4: Godot AI Play Integration

**Files:**
- Create: `addons/cogito/AIPlay/ai_play_laboratory_observer.gd`
- Create: `addons/cogito/AIPlay/ai_play_laboratory_monitor.gd`
- Create: `addons/cogito/AIPlay/ai_play_laboratory_controller.tscn`
- Modify: `addons/cogito/AIPlay/ai_play_controller.gd`
- Modify: `addons/cogito/AIPlay/ai_play_game_over_screen.gd`
- Modify: `addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn`
- Test: `tests/ai_play/test_ai_play_laboratory.gd`

**Interfaces:**
- Observer adds only `laboratory = manager.ai_play_public_state()` to the standard observation.
- Monitor exports `scenario_id = "laboratory_experiment"` and forwards manager terminal signals.
- Controller keeps protocol version 3 and current action schema.

- [ ] **Step 1: Write a failing AI scene contract test**

Assert explicit disablement, numeric loopback, observer-manager wiring, monitor scenario ID, exact public DTO keys, hidden-key absence, allowlisted terminal pairs, and one-shot terminal behavior.

- [ ] **Step 2: Run the test and confirm missing AI nodes**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_laboratory.gd`
Expected: fail with missing AI controller.

- [ ] **Step 3: Implement observer, monitor, and controller subscene**

Reuse `AIPlayController`, `AIPlayExecutor`, `AIPlayHomeInteractionProbe`, `AIPlayBridge`, and `ObservationTimer`. Do not add action types. Add terminal pairs to `SCENARIO_TERMINAL_RESULTS` and display strings for `experiment_completed` and `experiment_attempts_exhausted`.

- [ ] **Step 4: Run Godot AI tests**

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_laboratory.gd`
Expected: pass.

Run: `tests/check_ai_play_mcp_only.sh`
Expected: pass.

- [ ] **Step 5: Commit Godot AI integration**

```bash
git add addons/cogito/AIPlay addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn tests/ai_play/test_ai_play_laboratory.gd
git commit -m "feat: connect laboratory experiment to AI Play"
```

### Task 5: Python MCP Registry, Briefing, and Observation DTO

**Files:**
- Create: `ai_play/src/ai_play/laboratory_experiment_briefing.py`
- Modify: `ai_play/src/ai_play/scenarios.py`
- Modify: `ai_play/src/ai_play/observation_schema.py`
- Modify: `ai_play/tests/test_scenarios.py`
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/tests/test_observation_schema.py`
- Modify: `ai_play/tests/test_game_session.py`

**Interfaces:**
- Registers `laboratory_experiment`, max 150 act requests, and exactly three terminal pairs.
- Validates optional `laboratory` DTO with exact fields and bounded enums.
- Briefing describes only public controls, rules, and panel meanings.

- [ ] **Step 1: Add failing Python tests**

```python
assert scenario_act_request_limit("laboratory_experiment", 500) == 150
assert is_allowed_game_over("laboratory_experiment", "success", "experiment_completed")
assert is_allowed_game_over(
    "laboratory_experiment", "failure", "experiment_attempts_exhausted"
)
assert is_allowed_game_over("laboratory_experiment", "failure", "max_requests")
```

Add DTO tests that accept every enum boundary and reject extra fields, hidden mappings, wrong types, attempts above 3, and oversized objective text.

- [ ] **Step 2: Run focused Python tests and verify failure**

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests/test_scenarios.py ai_play/tests/test_briefing.py ai_play/tests/test_observation_schema.py ai_play/tests/test_game_session.py -q`
Expected: fail because the scenario and DTO are unregistered.

- [ ] **Step 3: Implement registry, briefing, and strict DTO validation**

Add `laboratory` to `OPTIONAL_OBSERVATION_FIELDS`; validate exact keys and enum strings before copying into the safe observation. Do not expose case IDs, seed, maps, clues that have not been read, or unexecuted outcomes.

- [ ] **Step 4: Run all Python AI Play tests**

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q`
Expected: all pass.

- [ ] **Step 5: Commit Python MCP integration**

```bash
git add ai_play/src/ai_play ai_play/tests
git commit -m "feat: register laboratory experiment MCP scenario"
```

### Task 6: Documentation and End-to-End Verification

**Files:**
- Modify: `ai_play/README.md`
- Modify: `README_AI_PLAY.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `docs/wiki/architecture/repository-map.md`
- Modify: `docs/wiki/development/contributor-guide.md`
- Create: `tests/check_ai_play_laboratory.sh`

**Interfaces:**
- Documents exact launch command and public scenario behavior.
- Static check keeps Godot/Python IDs, limits, terminal results, and scene wiring synchronized.

- [ ] **Step 1: Add the static synchronization check**

The script must verify `laboratory_experiment` appears in the Laboratory scene, Godot terminal map, Python registry, public briefing, observation schema, and docs; it must also reject `auto_start = true` and non-loopback bridge hosts.

- [ ] **Step 2: Document launch commands**

```bash
godot --path . addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn \
  -- --ai-play-scenario=laboratory_experiment

godot --path . addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn \
  -- --ai-play --ai-play-scenario=laboratory_experiment
```

- [ ] **Step 3: Run all affected verification**

Run: `tests/check_ai_play_laboratory.sh`

Run: `tests/check_ai_play_mcp_only.sh`

Run: `PYTHONPATH=ai_play/src .venv/bin/python -m pytest ai_play/tests -q`

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_cases.gd`

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_manager.gd`

Run: `godot --headless --path . --script tests/laboratory/test_laboratory_experiment_scene.gd`

Run: `godot --headless --path . --script tests/ai_play/test_ai_play_laboratory.gd`

Run: `git diff --check`

Expected: every command exits 0.

- [ ] **Step 4: Start the playable scene for manual verification**

Run: `godot --path . addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn -- --ai-play-scenario=laboratory_experiment`

Verify task card readability, fixed interaction prompts, three-attempt feedback, reset behavior, success/failure screen, text fit, and no overlapping labels at the experiment station.

- [ ] **Step 5: Commit documentation and checks**

```bash
git add ai_play/README.md README_AI_PLAY.md docs/wiki tests/check_ai_play_laboratory.sh
git commit -m "docs: add laboratory experiment runbook"
```
