# AI Play Supervisor Design

## Goal

Run `find_contract` three times for an isolated Codex player without giving that player process control over Godot or access to the repository.

## Design

Godot remains the authority for terminal game state. `AIPlayController` prints one machine-readable terminal line when a validated game-over is reached:

```text
AI_PLAY_GAME_OVER outcome=<success|failure> reason=<reason>
```

Godot exits after game-over only when both `--ai-play` and `--ai-play-exit-on-game-over` are present. Ordinary launches and manual AI test launches keep the existing result screen behavior.

An external supervisor starts Godot, streams output, watches for the terminal line, waits for process exit, and then starts the next run. Runs without the terminal marker are treated as abnormal and retried with a fixed per-run retry limit. Timeouts terminate the current Godot process and retry. The supervisor never reads trajectory logs, repository files, scene state, screenshots, or model context.

An optional Codex orchestrator starts both the isolated player Codex and the supervisor. Each orchestrator run creates a fresh directory under a configurable `--session-root`, with `player_workspace/` for the player Codex startup location and `player_workspace/mcplogs/` for that run's `AI_PLAY_LOG_ROOT`. The log root is written to `player_workspace/ai_play_run_config.json` and passed as an environment variable, but it remains a run parameter, not gameplay context.

## Boundaries

- Player Codex uses only `briefing`, `observe`, `act`, and `stop`.
- Supervisor owns Godot process lifecycle only.
- Supervisor does not summarize, learn, inspect logs, or change prompts.
- Escape/manual interruption stops the full supervisor run.

## Verification

- Godot controller tests cover the opt-in exit flag parser.
- Python supervisor tests cover terminal marker parsing and timeout handling.
- Static shell checks verify the lobby wiring and documented command surface.
- `git diff --check` must pass.
