# Find Contract AWM Comparison Runner Design

## Goal

Provide one unattended command on `feature/session-awm` that compares three
consecutive `find_contract` attempts without structured workflow memory against
three consecutive attempts with Agent Workflow Memory (AWM).

Both groups use the same checkout, scenario, Codex model, reasoning effort,
authentication source, supervisor limits, and game build. The only intentional
difference is whether the player can access and is instructed to use the two
workflow-memory tools.

Both groups also receive identical high-priority Codex developer instructions:
`briefing` is the authoritative game-rule source; the player should behave like
a human visual explorer; and it is explicitly allowed and expected to compare
the current screenshot with earlier `observe` screenshots in the same model
conversation. It uses visual changes to infer relative movement, rotation,
occlusion, and landmark relationships. This permission does not include reading
or saving screenshots on disk, trajectories, repository content, or hidden
state.

## Experiment Matrix

| Group | Attempts in one Codex session | Player tools | Prompt behavior |
| --- | ---: | --- | --- |
| `without_awm` | 3 | `briefing`, `observe`, `act` | May retain ordinary in-context notes, but receives no structured AWM lifecycle |
| `with_awm` | 3 | Baseline tools plus `workflow_memory_read` and `workflow_memory_update` | Reads memory at attempt start and submits an eligible summary after terminal outcomes |

Defaults are scenario `find_contract`, model `gpt-5.6-sol`, reasoning effort
`high`, and three attempts per group. Command-line options may override these
values for later experiments.

## Architecture

The existing Codex orchestrator gains a `--workflow-memory` choice with
`enabled` and `disabled` values. It selects both the MCP allowlist and the
matching black-box prompt from that choice. The trusted MCP sidecar may still
implement AWM in the disabled group, but the Codex player cannot discover or
call those tools.

`tools/run_find_contract_awm_comparison.py` launches the current checkout's
orchestrator twice, sequentially. It never checks out another branch or invokes
another worktree. Sequential execution avoids collisions on the fixed Godot
bridge port and default MCP port.

Each subprocess streams output to the terminal and to a group-specific log.
The runner continues to the second group even if the first exits unsuccessfully,
so the requested unattended comparison does not pause for user input.

## Isolation and Outputs

The runner creates a timestamped directory under an isolated comparison root,
defaulting to `/tmp/cogito_ai_player_comparisons`. Each group gets a separate
orchestrator session root, preserving trusted trajectories and screenshots
without exposing them to the other player session.

After both groups exit, the runner writes `comparison_summary.json` containing:

- fixed experiment inputs and group order;
- command exit code and elapsed seconds for each group;
- parsed terminal success/failure counts and reasons;
- orchestrator run and trusted-log paths;
- paths to captured console logs.

The summary remains trusted output and is never placed in a player workspace or
fed back to either Codex session.

## Failure and Shutdown Behavior

The runner does not retry, prompt, or silently change configuration. A non-zero
group exit is recorded, then the other group runs. The wrapper exits zero only
when both orchestrator processes exit zero; otherwise it exits non-zero after
writing the summary. Keyboard interruption is propagated to the active
orchestrator, whose existing cleanup releases Codex, supervisor, MCP, Godot,
and simulated input.

## Safety and Fairness

- The same current branch and orchestrator implementation serve both groups.
- The two groups run in the fixed order `without_awm`, then `with_awm`.
- Codex's built-in persistent memories remain disabled in both groups.
- Both groups have the same screenshot-understanding and screenshot-comparison
  developer instructions; visual skill is not treated as an AWM feature.
- Only the approved runtime briefing and observations reach the player.
- Repository files, trusted logs, screenshots on disk, developer notes, and
  hidden game state remain unavailable to the player.
- Authentication is copied into each existing temporary isolated Codex home;
  no credential is written into experiment output.

This is a practical paired configuration comparison, not proof that AWM alone
causes any observed score difference. Game randomness and model sampling are
not controlled by a shared seed.

## Verification

Unit tests cover tool allowlists, the two prompt variants, argument defaults,
sequential command construction, output parsing, summary writing, and
continue-after-failure behavior without invoking real Codex or Godot. The
existing orchestrator and AI Play suites must remain green, followed by
`git diff --check`. The real six-attempt run is manual acceptance initiated by
this task and stores its artifacts only under the isolated comparison root.
