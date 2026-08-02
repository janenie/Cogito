# AI Play Four-Attempt Logging Design

## Goal

Keep up to four completed AI play attempts for one scenario in the same
trajectory run directory. A fifth attempt starts a new run directory.

## Root Cause

`TrajectoryLogger.MAX_ATTEMPTS` is fixed at `3`. The supervisor accepts
`--runs 4`, but the logger has no dependency on that CLI option, so it rotates
before the fourth attempt and produces a `3 + 1` log split.

## Design

Change the logger's fixed maximum from three attempts to four attempts. This
keeps the existing bounded logging model and does not add configuration or
couple the MCP server to the orchestrator CLI.

The run summary contract becomes:

- attempts 1 through 4 share one `run.json` and use `attempt-01` through
  `attempt-04`;
- after four completed failures, that run becomes `failure`;
- attempt 5 starts a new timestamped run directory as `attempt-01`;
- success and stopped status behavior remains unchanged.

## Files

- `ai_play/src/ai_play/trajectory_logger.py`: set the bounded run capacity to
  four.
- `ai_play/tests/test_trajectory_logger.py`: assert the fourth attempt remains
  in the current run and the fifth rotates.
- `ai_play/README.md`: document the four-attempt run summary limit.

Historical design documents remain unchanged because they describe the
contract at the time they were accepted.

## Verification

Use TDD: first update the focused rotation test and confirm it fails because
attempt 4 still rotates. Then change the production constant and confirm the
focused test passes. Finally run the full trajectory logger tests, the full
AI Play Python suite, and `git diff --check`.

No real Codex, Godot, credentials, screenshots, or paid model calls are needed.
