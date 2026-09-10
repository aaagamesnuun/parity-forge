> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan0029 — Four-structure bounded preselection

## Status and dependency

COMPLETED / DESIGN_STAGE_CLOSED / OLD_SIX_OVERLAP / CELL4_SLOT_DRIFT /
NOT_REGISTERED / PRODUCTION_COUNT_ZERO / NO_SELECTION.

Plan28 is closed as `GAME_NO_FLAG / TECHNICAL_ACCEPTANCE_FAILED /
FULL_REGRESSION_INTERRUPTED_BY_HOST_REBOOT`. Its immutable pilot remains valid,
but its candidate-specific screen is not an accepted dependency and must not be
reused as if accepted. Plan29 may use only previously accepted parser, schema-v4
engine, capped solver and existing T2/T3 agents. It does not resume Plan28,
change a frozen result, or create a generic discovery system.

## What the number means

`0029` is the next chronological research work unit. It is not a game version,
candidate count, attempt count, or success score. A Plan keeps its number after
success, rejection or technical failure and is then archived. Definitions inside
this Plan will be named `CELL-1` through `CELL-4`; a surviving definition would
move unchanged to a separately registered Plan0030. Failed cells are never
renumbered or replaced inside Plan29.

## One question and claim boundary

Can a fixed, structurally varied set of four simple no-draw definitions be
reduced by cheap existing checks to at most one definition worth a fresh-seed
existing-agent screen?

Plan29 is a preselection Plan only. It cannot establish fairness, depth,
learning value, fun or human-playtest eligibility. All corresponding flags stay
false. More than100,000 reachable states or capped-solver UNKNOWN is only a
bounded lower observation for this implementation, never a hardness pass.

## Development exposure is not selection evidence

The design record
`docs/reviews/2026-09-06-plan0029-bounded-preselection-ja.md` reports several
source-led short-win, state-width and dead-goal screens performed before this
Plan. Their canonical definitions, checker and raw outputs are not all preserved
in the repository, so classify every number there as
`UNREGISTERED_DEVELOPMENT_EXPOSURE_ONLY / NOT_SELECTION_EVIDENCE`. Do not rerun
those cases to manufacture confirmation. They may explain which regions were
avoided, but cannot pass or fail a Plan29 cell.

## Four provisional structural cells

These are design slots, not yet definitions and not permission to execute. Fix
one exact5x5 definition in each slot before registration:

1. forward HOP/CONNECT_EDGES versus forward SWAP/CONNECT_EDGES;
2. forward SWAP/REACH_EDGE versus forward MOVE_CAPTURE/REACH_EDGE;
3. forward PUSH/REACH_EDGE versus forward HOP/REACH_EDGE;
4. CONVERT/ELIMINATE versus forward HOP/REACH_EDGE.

The definitions must differ in action/goal attachment, not only coordinates,
vectors, first player or thresholds. Before any computation, freeze canonical
JSON, definition hash, `CELL-1..4` order, fixed rank, first player, setup,
vectors, max plies, seeds and policy order in one proposal. Check public
action/goal signatures against the old-six exclusion and Plans20–28 without
accessing protected candidate membership. If any slot cannot satisfy every
static requirement, close Plan29 in design stage; do not substitute a fifth
idea or silently edit the slot.

## Hard admission and resource proofs

Each fixed cell must pass, from source before registration:

- canonical parse/hash roundtrip, nonterminal initial state and legal first move;
- a positive-integer potential that strictly decreases on every legal action,
  proving every legal play ends with exactly one A/B winner before `max_plies`;
- from the fixed initial state, one complete alternating-turn legal prefix for
  each role's explicit GOAL and one for each role's special action effect, with
  no earlier terminal state anywhere in the prefix;
- a proved maximum branching factor `b`, maximum decisions per role `t`, and
  `t*(b+b^2+b^3) <= 100000` for the unchanged T3 accounting;
- a fixed upper bound for every later query, transition, file and byte count.

Observed zero draws, sampled completion, a PLY_LIMIT tiebreak or capped search
cannot replace the D-055 all-legal-play proof. A dead goal, proof defect or
resource-bound defect closes that cell before production.

## Prospective frozen cascade

Registration is forbidden until the four definitions and all numerical values
below are exact rather than placeholders. The registered cascade will then run
in this order, with canonical action order and no per-game LLM call:

1. For each cell and each target role, complete AND/OR through the role's first
   four decisions: ply7/8 for the first/second player. Each target query gets at
   most100,000 cache misses. A proved force closes the cell as
   `NOT_SELECTED_SHORT_FORCED_WIN`; a cap hit is
   `NOT_SELECTED_EVIDENCE_INCOMPLETE`.
2. For each surviving cell, play T2/T2 and T3/T3 in separate four-game cells
   with frozen fresh seeds. Each cell must finish4/4 decisively with A wins1..3;
   do not combine the two depths. Because the static T3 completion bound is an
   admission condition, any T2/T3 game censor is `FAILED_TECHNICAL`, not an
   ordinary UNKNOWN or game result, and stops the whole Plan.
3. For each survivor, run exactly one existing exact call at100,000 states.
   COMPLETE closes as `NOT_SELECTED_TOO_EASILY_SOLVED`; UNKNOWN alone opens the
   state-prefix check and is not positive depth evidence. Save and replay exactly
   one external PV only for COMPLETE, using the previously accepted adapter.
4. Enumerate a canonical reachable-state prefix capped at100,001 distinct
   states. Before registration, fix a transition ceiling, durable-output byte
   ceiling and deterministic stop order. Exhaustion at or below100,000 closes as
   too small; reaching100,001 merely permits the next stage.
5. For each survivor and target role, complete AND/OR through its first seven
   decisions: ply13/14 for the first/second player, at100,000 misses per target.
   Only COMPLETE false for both targets survives. A force closes as short; a cap
   hit is incomplete evidence.

The registered manifest must state the arithmetic total: at most32 games, eight
four-decision queries, eight seven-decision queries, four exact calls, at most
four COMPLETE-result external PV replays, four BFS prefixes, all T3 node bounds,
maximum replay/BFS transitions, memory proxy, immutable files and publication
bytes. Name and pin the previously accepted replay adapter before registration.
Host wall time and RSS are descriptive only. Fix the rank before results; if
multiple cells survive, select the lowest fixed rank and label the others
`NOT_SELECTED_FIXED_RANK`. Never rerank from wins, nodes or state width.

## Stops, evidence and technical acceptance

Scientific cell labels are `NOT_SELECTED_STATIC_FAILURE`,
`NOT_SELECTED_SHORT_FORCED_WIN`, `NOT_SELECTED_POLICY_GATE`,
`NOT_SELECTED_TOO_EASILY_SOLVED`, `NOT_SELECTED_EVIDENCE_INCOMPLETE`,
`NOT_SELECTED_FIXED_RANK`, and at most one `SELECTED_FOR_PLAN0030`.
UNKNOWN never means loss, draw, difficulty or selection.

Any exception, source/hash/publication drift, invalid replay, impossible agent
censor, draw, PLY_LIMIT or potential violation is `FAILED_TECHNICAL` and stops
the whole Plan. No retry, resume, backfill, replacement definition, seed
substitution, threshold relaxation, cap/depth increase or extra game/query.

If implementation is needed, add only a Plan29-specific thin script and focused
synthetic tests; do not edit `src/`, DSL, engine, solver, agents or old adapters.
Independent definition/proof/protocol review and focused tests precede a clean
registration with production count zero. Launch the registered preselection
once, save and independently audit all evidence, and launch one registered full
regression. Technical acceptance requires that suite's actual final `Ran`, `OK`
and exit0; an interruption fails acceptance and is not retried.

## Closeout and next Plan

If no cell survives, close Plan29 and use Plan0030 for a new structural question;
do not spend a play screen on these cells. If one cell survives and technical
acceptance passes, Plan0030 receives only that unchanged definition and fresh
seeds for a separate existing-agent play screen. Even then, only Plan0030 could
decide whether the user's first playtest is worth requesting.

## Activation checklist

- [x] Plan28 pilot/result preserved and technical interruption independently
  classified; no retry.
- [x] Four structural slots and a bounded cascade reviewed as compatible with
  the existing-method scope.
- [ ] Four exact canonical definitions, hashes, fixed rank, seeds and policy
  order frozen with no substitute slot.
- [ ] D-055, goals/effects, old-six exclusion and `b/t/T3` proofs independently
  reviewed.
- [ ] Exact per-stage compute/output totals and durable log locations frozen.
- [ ] Minimal implementation and focused synthetic tests independently PASS.
- [ ] Register from production count zero, then run exactly one preselection and
  one full regression from that clean commit.
- [ ] Saved/source audit, Japanese findings, technical closeout and honest labels.

## Design-stage closeout — 2026-09-07

One attempted materialization of the four slots was saved in
`experiments/proposals/plan0029-four-structure-rejected-v0.json`. Canonical parse
and definition hashes matched the fixed rank. Before registration or production,
the public `typed_occupancy.is_plan0013_semantic_region()` predicate was applied
in both role orders. CELL-1, CELL-2 and CELL-4 were false; CELL-3
PUSH/REACH_EDGE versus HOP/REACH_EDGE was true in the role-neutral old-six
closure. In addition, the materialized CELL-4 used HOP/CONNECT_EDGES even though
the active contract specified HOP/REACH_EDGE. That is a slot-definition drift,
not a permissible materialization of the described fourth slot. A root
reproduction and an independent review agreed on both defects.

The old-six match violates mandatory exclusion and the CELL-4 mismatch violates
the fixed structure. The Plan expressly forbids replacing a failed slot with a
fifth idea, so close the whole four-cell question rather than repairing either
defect in place. No registered production game, exact solve, replay, AND/OR
selection query, BFS, run directory, candidate-specific
script/test or full regression occurred. Unregistered source-led observations
remain development exposure only. There is no selected game and no technical
acceptance claim.

Plan0030 may pose a new bounded cohort question. It must perform cheap public
signature and D-055 checks while drafts are still explicitly drafts, impose a
finite draft ceiling, and freeze the admitted cohort before any selection
computation. This closeout does not authorize retrying CELL-3 or reclassifying
the three other Plan29 cells as selected evidence.
