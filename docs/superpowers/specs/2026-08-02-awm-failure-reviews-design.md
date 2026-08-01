# AWM Failure Reviews Design

## Goal

Extend session-scoped Agent Workflow Memory (AWM) with bounded, structured
reviews of eligible failed attempts. A later attempt should learn where the
previous attempt lost time and how to improve without treating a failed route
as a successful workflow or retaining a randomized answer.

## Motivation

The current memory promotes `workflow`, `landmarks`, and `avoid` after a
successful attempt, but promotes only merged `avoid` strings after a normal
failure. That preserves safety but loses useful context: which stage failed,
which reusable bottlenecks caused the failure, and which strategic changes
would make the next attempt more efficient.

The observed `find_key` run illustrates the gap. The player eventually reached
the target environment but spent too many `act` requests on distant room-label
guesses, doorway alignment, furniture-state probing, and late budget recovery.
The next attempt received generic avoidance rules but no compact explanation of
where to optimize.

## Scope

This change adds an optional `failure_review` candidate to
`workflow_memory_update` and exposes accepted reviews as `failure_reviews` in
`workflow_memory_read`.

Each accepted review records:

- `stage`: the reusable task stage where progress broke down;
- `bottlenecks`: a bounded list of the main reusable causes;
- `optimizations`: a bounded list of concrete improvements for the next run.

The trusted server supplies the terminal reason from the completed attempt.
The model cannot declare or override the outcome or reason.

## Non-goals

- Persisting memory across orchestrator invocations.
- Saving screenshots, image references, trajectories, or raw observations.
- Saving randomized answers, passwords, object locations, absolute routes,
  coordinates, or timed action sequences.
- Promoting failed workflows or landmarks.
- Generating a review automatically from trusted trajectory logs.
- Changing request limits, supervisor retry policy, or confidence scoring.

## Public Data Shape

`workflow_memory_update` gains an optional argument:

```json
{
  "failure_review": {
    "stage": "接近目标并准备交互",
    "bottlenecks": [
      "在相似家具间反复判断",
      "为最终拾取预留的请求不足"
    ],
    "optimizations": [
      "先组合验证房间标牌与家具特征",
      "进入请求预算末段后只执行接近和拾取"
    ]
  }
}
```

The argument defaults to `null` for compatibility with existing MCP clients.
The internal candidate has the exact keys used by the existing memory schema
plus `failure_review`.

When memory exists, `workflow_memory_read` includes:

```json
{
  "failure_reviews": [
    {
      "terminal_reason": "max_requests",
      "stage": "接近目标并准备交互",
      "bottlenecks": ["在相似家具间反复判断"],
      "optimizations": ["先组合验证房间标牌与家具特征"]
    }
  ]
}
```

`terminal_reason` is copied from the trusted attempt lifecycle, not from the
candidate.

## Eligibility and Update Semantics

The existing trusted attempt outcome remains authoritative:

- On `failure`, the server continues to promote only `avoid` from the existing
  sections. If `failure_review` is present, the server validates and stores it.
  An omitted review remains accepted for backward compatibility.
- On `success`, the server continues to promote `goal_pattern`, `workflow`,
  `landmarks`, and `avoid`. A non-null `failure_review` is rejected because it
  does not describe the trusted outcome.
- On `stopped`, `disconnected`, or `shutdown`, the update remains ineligible.
- A malformed or outcome-incompatible review rejects the entire update. No
  workflow, landmark, avoidance rule, or review is partially promoted.

The update result adds `failure_reviews` to the `accepted` counts. A stored
review contributes one accepted item; a normalized duplicate contributes zero.

## Retention and Deduplication

Memory stores at most the three most recent unique failure reviews. Reviews are
compared after normalization, including the trusted terminal reason. When a
fourth unique review is accepted, the oldest review is discarded.
A duplicate contributes zero accepted items and does not refresh its recency.
When a memory snapshot exists but no review has been stored, the snapshot
returns `"failure_reviews": []`.

Reviews remain scoped to one `SessionWorkflowMemory` instance and disappear
when the MCP process exits. They are never sent to `TrajectoryLogger` and are
not written to disk.

The existing `completed_runs` and `confidence` calculations do not change. A
failed attempt still counts as an eligible completed run after its update, but
its review never increases success confidence.

## Validation and Privacy

The review uses the existing normalized-text safety boundary:

- exact object keys only;
- NFC Unicode normalization and whitespace folding;
- no control characters;
- bounded list sizes and bounded string lengths;
- rejection of URLs, repository paths, internal file types, node paths,
  six-digit secrets, coordinates, absolute positions, and timed actions.

Required bounds are one non-empty `stage`, one to three non-empty
`bottlenecks`, and one to four non-empty `optimizations`, with each text value
limited to the existing 240-character maximum.

The review must describe reusable decision or execution improvements. Player
instructions explicitly forbid current-run answers, absolute routes, exact
object locations, and frame-by-frame action histories.

## Player Behavior

The AWM-enabled Codex prompt changes in two places:

1. After an eligible failure, the player submits only `avoid` plus a structured
   `failure_review`; `workflow` and `landmarks` remain empty.
2. At the start of a later attempt, the player treats `failure_reviews` as
   high-level optimization advice. Each optimization still requires support
   from the latest briefing and observation before use.

The prompt should encourage reviews of target classification, navigation,
interaction selection, and request-budget management. It should not encourage
narrative retellings of the failed run.

## Error Handling

The public error remains `invalid_workflow_memory` for malformed or unsafe
content. Existing lifecycle errors (`attempt_in_progress`,
`attempt_not_eligible`, `attempt_already_updated`, and scenario errors) remain
unchanged.

A success candidate with a non-null review is invalid. A failure candidate with
an omitted review remains valid for compatibility. Review validation happens
before taking the memory lock, while outcome compatibility and promotion happen
atomically under the lock.

## Tests

Unit tests cover:

- a failure promoting `avoid` and one trusted-reason review;
- a success rejecting a non-null review;
- a failure accepting an omitted review for old-client compatibility;
- exact keys, types, list bounds, empty text, normalization, and all existing
  unsafe-text filters;
- duplicate review suppression and oldest-first eviction after three reviews;
- copy isolation of returned reviews;
- unchanged confidence and completed-run behavior;
- atomic rejection without partially promoted sections.

MCP and orchestrator tests cover:

- the optional tool argument and returned snapshot shape;
- trusted terminal reason injection;
- absence of AWM calls and review contents from trajectory logs;
- prompt requirements for producing and consuming failure reviews;
- unchanged disabled-AWM tool and prompt behavior.

Documentation in `ai_play/README.md` and
`docs/wiki/ai-play/system-guide.md` will describe the new shape, eligibility,
retention, and privacy boundary.

## Verification

Run the focused workflow-memory, MCP-server, and orchestrator tests first, then
the affected Python AI Play test suite and `git diff --check`. After automated
verification, launch one explicitly approved real `find_key` run with AWM,
`gpt-5.6-sol`, and high reasoning effort.

Because AWM is process-scoped, this fresh one-run invocation starts with empty
memory. It can validate real tool compatibility and, if the run ends in an
eligible failure, failure-review submission. It cannot demonstrate consumption
of a prior review unless a later attempt runs in the same orchestrator process.
