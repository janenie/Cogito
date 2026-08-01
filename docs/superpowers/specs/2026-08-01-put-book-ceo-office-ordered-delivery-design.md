# Put Book CEO Office Ordered Delivery Design

## Goal

Replace the current archive-box sorting round with an ordered delivery task. Six
books are visible on shelves in the archive, three marked books are selected as
the round targets, and the player must carry those targets one at a time to one
clearly marked placement point in the CEO office. The required order is the
targets' authored height tier: low, then middle, then high.

The round remains deterministic when configured with a nonzero seed. A fresh
unseeded round may randomize normally.

## Player Contract

At round start, the task card tells the player to:

1. find the three visibly marked task books among the six books in the archive;
2. identify the low, middle, and high task books from their shelf positions;
3. carry only the low task book to the CEO office placement point;
4. return for the middle task book and then the high task book; and
5. carry no more than one book at a time.

All six books are physically available from the start. The game does not block
an incorrect first choice: picking up an unmarked book or a marked book from a
later height tier immediately ends the round as a scored failure. This makes
observing the targets and planning the order part of the task.

The old posture rules are removed. Every generated shelf slot must be reachable
with an ordinary standing interaction; jumping and crouching are neither
required nor checked.

## Authored Shelf Slots

The archive receives a pool of authored book-slot markers rather than using six
fixed book transforms. Each marker records:

- a stable slot identifier;
- a logical shelf identifier; and
- exactly one height tier: `low`, `middle`, or `high`.

The pool spans multiple visually distinct shelves and contains more than six
slots so different seeds can produce visibly different layouts. Each tier must
have enough valid slots on multiple shelves to support balanced selection. Slot
transforms are authored and manually checked for collision, visibility, and
standing reachability; the monitor never invents unconstrained coordinates at
runtime.

The existing decorative book props remain hidden during this scenario. Six
runtime carryable book objects occupy the selected slots, so every visible task
book follows the same pickup and delivery mechanics.

## Seeded Layout Selection

For each round, the monitor uses one `RandomNumberGenerator` seeded by the
configured round seed. The seed controls the six occupied shelf slots and which
book in each tier is marked as a target.

Layout selection chooses exactly two unique slots from each height tier. Among
valid six-slot layouts, it prefers the most even distribution across logical
shelves: compare per-shelf book counts from highest to lowest and choose the
lexicographically smallest count vector. This first minimizes crowding on any
one shelf, then minimizes secondary crowding. The seeded RNG resolves ties
between equally balanced layouts. If the authored geometry cannot produce a
perfectly even distribution, the same rule selects the least concentrated
available layout.

The result must satisfy these invariants:

- exactly six books are visible;
- exactly two books occupy each of `low`, `middle`, and `high`;
- no slot is occupied twice;
- books are spread over as many shelf groups as the valid slots permit;
- the same nonzero seed produces the same layout and targets; and
- a representative seed range produces more than one layout and uses every
  registered valid slot.

After selecting the layout, the monitor chooses one of the two books in each
tier as a task book. The required sequence is always the selected low book,
then the selected middle book, then the selected high book.

## Target Affordance

Because choosing an unmarked book is an immediate failure, the three task books
must be distinguishable before pickup. Each target receives the same visible
`task book` marker or highlight; ordinary books do not. The marker identifies
membership only. It does not label a book as first, second, or third—the player
derives order from the books' shelf heights.

Interaction probing may describe a marked object as a task book and an
unmarked object as an ordinary book, but probing must not expose internal node
paths, exact coordinates, seed state, or the selected sequence. The task card
and public briefing explain the visible marker and the low-to-high rule.

## Carry and Order State Machine

The monitor owns an ordered list of the three target books and a current target
index.

When any book enters the carried state:

- if it is not the target at the current index, the monitor immediately emits
  terminal failure `wrong_book_pickup`;
- if it is the current target, the monitor records it as the sole carried book
  and temporarily disables pickup on every other unfinished book; and
- a completed book remains locked and cannot be carried again.

The underlying carry system should already prevent two simultaneous held
objects, but the monitor-level gate is still required so the one-book rule is
explicit and testable.

Dropping the correct current book outside the CEO destination is recoverable.
The target index does not advance, and that same book may be picked up again.
Once it is no longer being carried, other books become physically available
again; picking any of them before completing the current target still causes
the same immediate order failure.

## CEO Office Placement Point

The CEO office receives one visible, named book placement point with an
`Area3D` acceptance volume and three internal display anchors. The point must be
reachable while carrying a book and must not overlap unrelated CEO-office
interactions.

When the current target enters the placement area after being carried, or the
player invokes the destination's assisted-drop interaction while holding it,
the monitor:

1. releases the carry state;
2. snaps the book to the next display anchor;
3. freezes and disables that completed book;
4. advances the current target index; and
5. enables the next archive pickup cycle.

The three display anchors are presentation details within one logical placement
point. They keep delivered books from overlapping while preserving the user's
single-destination rule.

The route from the archive to the CEO office must be traversable in this
scenario. Required doors are left unlocked and operable; the scenario does not
add a door puzzle to the delivery task.

## Outcomes and Scoring

The round succeeds only after the low, middle, and high target books have been
accepted in that order. The success terminal reason becomes
`books_in_ceo_office`.

Picking up any ordinary book or any later target before the current target is
completed immediately fails with `wrong_book_pickup`. Merely looking at or
probing the wrong book does not fail. Dropping the current correct book outside
the destination also does not fail.

The scenario registry, controller terminal allowlist, result presentation, and
tests must agree on the new terminal reasons. The old archive-box reasons and
nearest-box assignment behavior are removed from this scenario.

Moving three books between rooms requires materially more navigation than the
old in-room box task. Increase the AI-play action allowance from 50 to an
initial 150 requests, then confirm the value with a controlled successful run.
Timeout at the configured limit remains a failure.

## Task Text, Briefing, and Internal Snapshot

The in-world task card and approved `put_book` briefing describe only facts the
player may know: six visible books, three visible task markers, low-to-high
order, one-at-a-time carrying, immediate failure on a wrong pickup, and the CEO
office placement point. They remove all references to archive floor boxes,
nearest-box matching, jumping, and crouching.

The public briefing may identify common visual classes such as task marker,
carryable book, office sign, door, and placement point. It must not reveal the
generated slot IDs, target identities, hidden state, or correct route.

`get_round_snapshot()` remains an internal testing aid and reports at least:

- the effective seed;
- all six occupied slot IDs, shelf IDs, and height tiers;
- the three target identities in required order;
- the current target index and carried book, if any; and
- completed delivery state.

None of this hidden snapshot data is added to MCP observations.

## Verification

Automated Godot tests cover:

- six visible, carryable runtime books and no old archive boxes;
- exactly two selected slots per height tier;
- deterministic layout and targets for the same nonzero seed;
- layout variation and full slot-pool coverage across a representative seed
  range;
- balanced distribution across shelf groups;
- all pickup components enabled at round start without posture gates;
- one low, one middle, and one high target in the required order;
- immediate failure when an ordinary or out-of-order target book is picked up;
- no failure from probing a wrong book;
- explicit single-book pickup gating while the correct book is carried;
- recoverable drops outside the CEO destination;
- correct snapping and locking at each destination display anchor; and
- success only after all three ordered deliveries.

Python tests cover the revised public briefing, scenario request limit, and
terminal-reason registration. Scene and headless smoke tests verify that all
exported slot and CEO-destination nodes resolve without parse or UID errors.

Manual acceptance verifies that multiple seeds visibly move books between
different shelf positions, distribute them reasonably evenly across the
available shelves, keep all six reachable while standing, make the three task
markers unambiguous, and allow a complete low-to-high delivery run without
carrying two books at once.

## Out of Scope

- procedural bookshelf geometry or unconstrained random coordinates;
- jump- or crouch-gated pickups;
- carrying more than one book;
- sorting into multiple archive boxes;
- assigning a different CEO destination to each book;
- inventory storage, throwing-based scoring, or automatic pathfinding; and
- exposing generated targets or spatial answers through the MCP protocol.
