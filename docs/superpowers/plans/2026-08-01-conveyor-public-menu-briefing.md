# Conveyor Profit Public Menu Briefing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the six fixed conveyor recipes as a structured, allowlisted `briefing.menu` so the AI can calculate recipe profit without OCR-reading the in-world menu.

**Architecture:** Keep the contract entirely in the scenario-specific Python briefing loader. `load_conveyor_profit_briefing()` continues returning a deep copy, while tests pin the public catalog independently with literal expected values. Godot gameplay, observations, semantic actions, window generation, and the in-world menu remain unchanged.

**Tech Stack:** Python 3, pytest, MCP scenario briefing registry, Markdown project documentation.

## Global Constraints

- The public menu contains only fixed information already visible on the in-world recipe board.
- Do not expose current or future window supplies, candidate recipes, optimal recipes, random seeds, theoretical totals, or absolute passing profit.
- Keep the six in-world recipe stickers unchanged and simultaneously visible.
- Do not change gameplay economy, semantic actions, observation DTOs, or persistence behavior.
- Update `ai_play/README.md`, `docs/wiki/ai-play/system-guide.md`, and relevant tests with the public contract.
- Do not commit screenshots, trajectories, workflow memory, Python caches, or `.godot/` output.

---

### Task 1: Publish the fixed recipe catalog

**Files:**
- Modify: `ai_play/tests/test_briefing.py`
- Modify: `ai_play/src/ai_play/conveyor_profit_briefing.py`

**Interfaces:**
- Consumes: `load_scenario_briefing("conveyor_profit") -> tuple[dict, None]`.
- Produces: `briefing["menu"] -> list[dict]`, where each entry has `id: str`, `name: str`, `ingredients: list[str]`, `sale_price: int`, and `net_profit: int`.

- [ ] **Step 1: Write the failing public-contract test**

Extend `test_conveyor_profit_briefing_teaches_semantic_strategy_without_hidden_state` with the following hand-checked literal:

```python
expected_menu = [
    {
        "id": "salad",
        "name": "SALAD",
        "ingredients": ["lettuce", "tomato", "mushroom"],
        "sale_price": 7,
        "net_profit": 3,
    },
    {
        "id": "egg_toast",
        "name": "EGG TOAST",
        "ingredients": ["bread", "egg"],
        "sale_price": 8,
        "net_profit": 4,
    },
    {
        "id": "cheese_toast",
        "name": "CHEESE TOAST",
        "ingredients": ["bread", "cheese"],
        "sale_price": 10,
        "net_profit": 5,
    },
    {
        "id": "burger",
        "name": "BURGER",
        "ingredients": ["bread", "meat", "lettuce", "tomato"],
        "sale_price": 15,
        "net_profit": 6,
    },
    {
        "id": "fish_sandwich",
        "name": "FISH SANDWICH",
        "ingredients": ["bread", "fish", "lettuce"],
        "sale_price": 14,
        "net_profit": 7,
    },
    {
        "id": "mushroom_omelet",
        "name": "MUSHROOM OMELET",
        "ingredients": ["egg", "cheese", "mushroom"],
        "sale_price": 14,
        "net_profit": 7,
    },
]
assert briefing["menu"] == expected_menu

second, _ = load_scenario_briefing("conveyor_profit")
briefing["menu"][0]["ingredients"].append("bread")
assert second["menu"] == expected_menu
```

This test catches a missing menu, a wrong recipe ingredient, wrong price/profit, or a shallow-copy regression.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest ai_play/tests/test_briefing.py::test_conveyor_profit_briefing_teaches_semantic_strategy_without_hidden_state -q
```

Expected: FAIL with `KeyError: 'menu'`.

- [ ] **Step 3: Add the minimal public menu payload**

Add the following `menu` key to `PUBLIC_BRIEFING` in `conveyor_profit_briefing.py` using the exact six dictionaries from Step 1:

```python
"menu": [
    {
        "id": "salad",
        "name": "SALAD",
        "ingredients": ["lettuce", "tomato", "mushroom"],
        "sale_price": 7,
        "net_profit": 3,
    },
    {
        "id": "egg_toast",
        "name": "EGG TOAST",
        "ingredients": ["bread", "egg"],
        "sale_price": 8,
        "net_profit": 4,
    },
    {
        "id": "cheese_toast",
        "name": "CHEESE TOAST",
        "ingredients": ["bread", "cheese"],
        "sale_price": 10,
        "net_profit": 5,
    },
    {
        "id": "burger",
        "name": "BURGER",
        "ingredients": ["bread", "meat", "lettuce", "tomato"],
        "sale_price": 15,
        "net_profit": 6,
    },
    {
        "id": "fish_sandwich",
        "name": "FISH SANDWICH",
        "ingredients": ["bread", "fish", "lettuce"],
        "sale_price": 14,
        "net_profit": 7,
    },
    {
        "id": "mushroom_omelet",
        "name": "MUSHROOM OMELET",
        "ingredients": ["egg", "cheese", "mushroom"],
        "sale_price": 14,
        "net_profit": 7,
    },
],
```

Change the existing menu rule to:

```python
"使用 briefing 的公开 menu 核对配方、售价和净利润；再根据截图识别当前食材并比较可行菜。",
```

Do not read repository files at runtime and do not add window-specific values.

- [ ] **Step 4: Run focused and scenario-boundary tests and verify GREEN**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest \
  ai_play/tests/test_briefing.py \
  ai_play/tests/test_scenarios.py \
  ai_play/tests/test_mcp_server.py -q
```

Expected: all tests PASS.

- [ ] **Step 5: Commit the public contract**

```bash
git add ai_play/src/ai_play/conveyor_profit_briefing.py ai_play/tests/test_briefing.py
git commit -m "feat(ai-play): publish conveyor recipe menu"
```

### Task 2: Document the public-menu boundary

**Files:**
- Modify: `ai_play/README.md`
- Modify: `docs/wiki/ai-play/system-guide.md`
- Modify: `conveyor_profit/README.md`

**Interfaces:**
- Consumes: `briefing.menu` from Task 1.
- Produces: Maintainer and operator documentation that distinguishes fixed public recipes from hidden per-window state.

- [ ] **Step 1: Update the AI Play README**

In the conveyor section, state that `briefing` publishes the six fixed recipes with ingredient lists, sale prices, and net profits. State that `observe` still does not return a structured current ingredient inventory or candidate recipes.

- [ ] **Step 2: Update the Wiki contract**

In `docs/wiki/ai-play/system-guide.md#conveyor_profit-语义动作契约`, replace the claim that the AI must read the menu from the screenshot. Document that the fixed public menu is allowlisted in `briefing`, while the screenshot remains the only source for current visible supplies.

- [ ] **Step 3: Update the game README**

Explain that MCP clients receive the same fixed catalog displayed on the wall, but do not receive current candidates, supply generation, per-window optimum, future windows, seed, or target amount.

- [ ] **Step 4: Run documentation/static safety checks**

Run:

```bash
tests/check_ai_play_mcp_only.sh
tests/check_ai_play_start_script.sh
tests/check_ai_play_secrets.sh
git diff --check
```

Expected: all scripts exit 0 and `git diff --check` prints nothing.

- [ ] **Step 5: Commit documentation**

```bash
git add ai_play/README.md docs/wiki/ai-play/system-guide.md conveyor_profit/README.md
git commit -m "docs(ai-play): describe public conveyor menu"
```

### Task 3: Verify and run the real AWM acceptance

**Files:**
- No tracked file changes expected.
- Runtime output only: `/private/tmp/cogito_ai_player_runs/<timestamp>/`.

**Interfaces:**
- Consumes: the public menu briefing and existing `gpt-5.6-sol` high-reasoning AWM orchestrator path.
- Produces: three trusted terminal results and local trajectories outside the repository.

- [ ] **Step 1: Run the complete affected automated suites**

Run:

```bash
PYTHONPATH=ai_play/src ../../.venv/bin/python -m pytest ai_play/tests -q
../../.venv/bin/python -m pytest tests/test_ai_play_codex_orchestrator.py tests/test_ai_play_supervisor.py -q
godot --headless --path . --script tests/conveyor_profit/test_conveyor_profit_scene.gd
godot --headless --path . --script tests/conveyor_profit/test_recipe_catalog.gd
godot --headless --path . --script tests/conveyor_profit/test_profit_session.gd
godot --headless --path . --script tests/conveyor_profit/test_profit_window_session.gd
godot --headless --path . --script tests/conveyor_profit/test_window_supply_generator.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_gameplay.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_ai_play_observer.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_ai_play_monitor.gd
godot --headless --path . --script tests/conveyor_profit/test_conveyor_motion.gd
tests/check_ai_play_mcp_only.sh
tests/check_ai_play_start_script.sh
tests/check_ai_play_secrets.sh
git diff --check
```

Expected: all commands exit 0; no tracked runtime artifacts appear.

- [ ] **Step 2: Run three unattended AWM attempts**

The user already authorized screenshot transmission, token cost, and local trajectory persistence for this acceptance. Run:

```bash
../../.venv/bin/python tools/ai_play_codex_orchestrator.py \
  --runs 3 \
  --scenario conveyor_profit \
  --model gpt-5.6-sol \
  --reasoning-effort high \
  --workflow-memory enabled
```

Do not provide gameplay hints outside the allowlisted briefing and do not manually operate the game. Record each trusted `CONVEYOR_PROFIT_RESULT` line and whether AWM reports `completed_runs` 1 then 2.

- [ ] **Step 3: Audit repository cleanliness and push**

Run:

```bash
git status --short --branch
git log -8 --oneline
git diff --check
git push origin feature/session-awm
```

Expected: only pre-existing untracked Python cache directories remain; the current branch is pushed without switching branches, merging, opening a PR, or cleaning the worktree.
