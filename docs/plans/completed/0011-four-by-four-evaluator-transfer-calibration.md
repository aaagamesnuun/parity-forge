> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0011 — Exact-backed 4×4 evaluator-transfer calibration

## Objective

Determine whether the frozen `minimax-v1-depth5` evaluator transfers from its
exactly calibrated 3×3 domain to a bounded 4×4 schema-v1 slice before either
retiring the narrow place-versus-move family or spending a separate experiment on
4×4 family viability. Freeze 32 outcome-blind definitions, exact-solve every case
under a proved sub-100,000-state bound, and then compare the fixed depth-5 profile
with exact A, B, and horizon-draw labels.

This is an evaluator-calibration experiment. It is not a generator release, a
candidate search, a prevalence estimate, a fairness test, or evidence that 4×4
rescues the family. A positive result authorizes only a separately planned 4×4
family-viability experiment. A negative or label-incomplete result ends this lane
without adding cases or changing budgets and retires the current family from
active discovery.

## Hypothesis

Depth 5 matched 20/20 development and 14/14 blind exact 3×3 directions, but the
blind result missed its preregistered 15-case floor and contained no exact draws.
The only prior 4×4 depth-5 evidence completed 12/12 profiles, but those definitions
were selected by outcome-sensitive high-draw admission, had no exact labels, and
already failed cheap shape. A fresh exact-backed 4×4 corpus should separate
evaluator transfer from that failed admission policy.

The primary hypothesis is that all 32 exact solves and all 32 depth-5 profiles
complete under their fixed deterministic caps; the exact sample supplies at least
15 decisive labels, at least four A wins, four B wins, and four horizon draws; and
depth 5 matches at least 90% of decisive directions while calling no exact draw
decisive. If the fixed sample cannot supply those labels, the calibration is
inconclusive but terminal rather than permission to search for a friendlier
corpus.

## Expected result

The exact state proof should make solver completion routine. Historical 4×4 depth
5 used at most 567,420 nodes per definition, so the existing cumulative
5,000,000-node cap should also be ample. The substantive uncertainty is label
transfer: an eight-ply horizon is intentionally binding, so the fixed sample may
expose exact draws that depth 5 turns into apparently decisive self-play. Either a
supported transfer or a clean failure has higher information value than moving to
4×4 discovery without ground truth.

## Definition of done

- [x] Implement a pure exhaustive generator-v2 4×4/`max_plies=8` census and
  reproduce the result-blind planning counts: 16,320 raw definitions, 2,040 D4
  orbits, 1,592 static/asymmetry/simplicity-valid orbits, and 1,578 fresh valid
  orbits after 14 closed-history exclusions.
- [x] Reconstruct the reviewed closed historical definition projection from
  authenticated bytes, prove the 14 fresh-pool exclusions, and reject every
  unknown dependency, outcome-routed source, open-ended scan, or hash mismatch.
- [x] Prove and publicly validate exact state bounds of 62,096 for A-first and
  40,272 for B-first definitions, both below the unchanged 100,000-state cap.
- [x] Add a deterministic outcome-free one-per-stratum selector over 32 fixed
  strata with complete pool roots, selection fingerprint, D4 freshness, and
  definition-only membership.
- [x] Add a fixed all-case exact evaluator and public validator that retain every
  slot, PV, state count, terminal reason, evidence digest, label-coverage
  assessment, and inspection row. `PLY_LIMIT/DRAW` is an expected calibration
  label, not candidate evidence or an integrity failure.
- [x] Add a fixed all-case depth-5 evaluator and public validator over seeds
  `0..29`, with one fresh agent and one cumulative 5,000,000-node budget per
  definition, complete game/action/node evidence, exact-direction confusion, and
  exact-draw decisive-error reconstruction.
- [ ] Add fail-closed one-shot manifest, exact, and depth runners with separate
  reservations, attempts, locks, failure evidence, clean commits, strict ancestry,
  byte seals, source fingerprints, and noninjectable production boundaries.
- [ ] Independently review the census, history closure, state proof, selection
  blindness, horizon semantics, label thresholds, fixed schedule, raw
  reconstruction, and evidence chain before any selected exact outcome exists.
- [ ] Run the complete dependency-free test suite and commit implementation,
  protocol, and review before freezing production membership.
- [ ] Freeze and commit the 32-definition manifest once, run and commit exact once,
  and run and commit depth 5 once only if the exact stage completes without an
  integrity failure or censor.
- [ ] Reconstruct every artifact and assessment, report the full fixed sample, and
  close either with permission for a separate 4×4 viability plan or with family
  retirement; do not extend the corpus, increase a cap, or add a mechanic.

## Why calibration precedes retirement

Plan 0010 closes the last simple 3×3 setup intervention. Immediate retirement is
defensible, but one unresolved confound remains: the 3×3 board may force early
spatial saturation while the only existing 4×4 evidence lacks exact ground truth.
A bounded native 4×4 exact slice can test the evaluator at modest cost without
changing DSL, generator, agent, gate, or search algorithm.

The alternative max-32 4×4 slice has natural termination by ply 29/30 but a loose
one-runner state bound near 1,048,576 states per definition, outside the current
100,000-state exact cap and with unproven Python cache cost. A max-8 slice is the
only generator-native 4×4 lane whose structural bound preserves the existing
exact execution cap. Its horizon labels cannot establish game quality, but they
can calibrate whether depth 5 distinguishes exact forced directions from
nonresolution.

The prior 12 held-out 4×4 cases are excluded from membership. They entered depth 5
only through `WEAK_RANDOM_HIGH_DRAW`, all had retained cheap shape failures, seven
had cheap/strong direction disagreement, and two became 30/30 ply-limit draws.
They supply only a cost prior: 4,719,607 total nodes and 567,420 maximum nodes.

## Frozen definition universe

Use ordinary schema-v1 generator-v2 definitions with exactly:

- board size 4;
- one B runner on the edge opposite B's target;
- A `PLACE` with a `CONNECT_EDGES` goal;
- B `MOVE` with a `REACH_EDGE` goal;
- first player A or B;
- every nonempty subset of the eight generator movement vectors;
- `max_plies=8`.

The raw vocabulary has
`2 first players × 2 A edge pairs × 4 B target edges × 4 opposite-edge starts ×
(2^8 - 1) vector sets = 16,320` definitions. Canonical D4 grouping is
supplemental identity and must not change stored DSL hashes or orientations.

Apply the unchanged static, asymmetry, and simplicity gates using definitions
only. The simplicity gate removes eight-vector definitions because their numeric
parameter count exceeds the frozen limit; reachability and initial-state checks
remove other invalid structures. The result-blind planning census expects 1,592
valid D4 orbits.

## Closed history and freshness

Reconstruct the Plan-0010 reviewed historical full-definition projection from its
closed 21-artifact graph and exact ledger bytes. Intersect that authenticated D4
set with the 4×4 max-8 census; do not select history by a result, admission status,
or future directory scan.

The planning intersection contains 22 previously seen max-8 4×4 D4 orbits. Eight
already fail the frozen definition gates, leaving 14 exclusions from the valid
pool and 1,578 fresh valid orbits. The 14 are carried by exactly three historical
runs: one orbit in the generator-v1 development run, five in the generator-v2
development run, and nine in the held-out strong run, with one overlap between the
first two. These counts and identities are expectations to reconstruct, not
editable selection inputs.

Plan-0009 and Plan-0010 production definitions are 3×3 and therefore have zero
intersection, but their authenticated outcome-free manifests remain part of the
closed provenance boundary. Later artifacts cannot retroactively change this
experiment's freshness set.

## Outcome-free strata and selection

Partition the 1,578 fresh valid D4 orbits by:

- first player: `A`, `B`;
- relation between A's connection axis and B's target axis: `ALIGNED`,
  `ORTHOGONAL`;
- runner start class on the opposite edge: `CORNER`, `EDGE_INTERIOR`;
- movement-vector count band: `v1_3`, `v4`, `v5`, `v6_7`.

This creates 32 ordered strata. The planning census found 35–61 eligible orbits
per stratum. Any reconstructed count outside the frozen census, an empty stratum,
or a missing historical exclusion blocks freezing; it does not permit merging a
stratum or changing a quota.

The result-blind planning pool sizes are:

| Structural prefix | `v1_3` | `v4` | `v5` | `v6_7` |
|---|---:|---:|---:|---:|
| fA-aligned-corner | 55 | 60 | 54 | 36 |
| fA-aligned-edge_inner | 45 | 57 | 53 | 35 |
| fA-orthogonal-corner | 55 | 61 | 54 | 35 |
| fA-orthogonal-edge_inner | 45 | 56 | 53 | 35 |
| fB-aligned-corner | 56 | 60 | 54 | 36 |
| fB-aligned-edge_inner | 45 | 57 | 53 | 35 |
| fB-orthogonal-corner | 55 | 61 | 53 | 35 |
| fB-orthogonal-edge_inner | 45 | 57 | 52 | 35 |

Select one D4 orbit per stratum by a domain-separated SHA-256 score over only the
stratum and D4 identity, with D4 hash and exact definition hash as tie-breakers.
Store one canonical D4 orientation per selected orbit. Freeze the complete
eligible-pool root, every ordered stratum root, the selection fingerprint, and the
proof that all 32 selected identities are unique and fresh. Solver, play, timing,
historical outcome, admission, and prior rank fields are outside selector
capability.

## Exact state proof

At every reachable state there is one persistent B runner and `k` A seeds. For a
fixed ply layer, choose the runner cell in 16 ways and the A cells from the
remaining 15 in `C(15,k)` ways. First player and ply fix side to move; terminal
outcome is deterministic from definition, board, and ply under the frozen engine.

For A-first definitions, plies `0..8` contain respectively
`0,1,1,2,2,3,3,4,4` A seeds, giving:

```text
16 × [C(15,0) + 2 × (C(15,1)+C(15,2)+C(15,3)+C(15,4))]
= 62,096 states
```

For B-first definitions, the counts are `0,0,1,1,2,2,3,3,4`, giving:

```text
16 × [2 × (C(15,0)+C(15,1)+C(15,2)+C(15,3)) + C(15,4)]
= 40,272 states
```

These bounds count ply/to-move layers separately and include unreachable boards,
so they are conservative. Public validators reject boolean or out-of-bound state
counts. The execution cap remains 100,000. A budget censor would contradict the
proved state bound and is an integrity failure, not permission to raise the cap.
Across the fixed 16 A-first and 16 B-first strata, the summed structural bound is
1,637,888 states.

Unlike Plans 0007–0010, `PLY_LIMIT` is expected here because the eight-ply horizon
is deliberately binding. Under schema v1 it produces an exact `DRAW`. It remains
horizon/nonresolution evidence and can calibrate draw classification, but cannot
enter a fairness, frontier, or family-viability claim.

## Fixed evaluation schedule

After an independently reviewed clean pre-outcome commit:

1. freeze and commit the 32-definition outcome-free manifest, reservation,
   attempt, historical ledger, and lock without solver or agent calls;
2. from the clean manifest commit, exact-solve all 32 definitions in manifest
   order under the unchanged 100,000-state cap, validate every PV and state bound,
   seal the complete raw evidence, and commit it;
3. only after 32/32 exact completion, run all 32 depth-5 profiles in the same order
   over seeds `0..29`, then validate and commit the raw result.

Each profile constructs exactly one fresh
`MinimaxAgent(depth=5, max_total_nodes=5_000_000)`, assigns that one instance to
both roles, resets its cumulative budget exactly once before seed 0, and retains
every completed action trace and per-game node delta. A node censor retains the
completed contiguous seed prefix and incomplete attempt, suppresses only later
seeds for that definition, and does not route later definitions.

Depth 3 is not rerun. Exact minimax is the independent baseline, and adding a
second sampled strength would enlarge the evidence chain without changing the
primary question of whether the already promoted depth-5 evaluator transfers.

## Measures

Report all 32 cases and every stratum:

- exact result, terminal reason, PV, searched states, cache hits, and bound margin;
- exact A/B/draw counts and terminal-reason counts;
- depth-5 A/B/draw counts, decisive A share and Wilson interval, average plies,
  terminal reasons, failure codes, direction, and cumulative nodes;
- complete action traces, per-game node ledgers, every censor, and every direction
  mismatch;
- confusion matrices for exact decisive labels and exact horizon draws;
- exact-draw decisive misclassifications separately from decisive-direction
  accuracy;
- definition-only stratum breakdowns and descriptive timing.

Dominance, duration, draw rate, and other play-shape codes remain visible but do
not route the calibration result. A horizon draw is not a candidate, and a balanced
depth profile is not a fairness claim.

## Predeclared assessment priority

1. Any dependency, census, D4, freshness, gate, state-bound, executable,
   reservation, lock, ancestry, schedule, replay, node-ledger, aggregate, or raw
   reconstruction mismatch is an integrity failure with no trusted result.
2. Any exact state censor contradicts the proved sub-cap bound, prevents a depth
   reservation, and yields no trusted transfer assessment. Do not increase the
   cap or replace the case.
3. With 32 complete exact labels, calibration coverage requires at least 15
   decisive cases, at least four exact A wins, four exact B wins, and four exact
   horizon draws, with each of the three labels represented in at least two
   strata. A shortfall is `INCONCLUSIVE_LABEL_COVERAGE` and stops before depth 5.
4. After sufficient labels, run the full fixed depth schedule. Any node censor
   leaves the completed raw evidence intact but makes transfer
   `INCONCLUSIVE_NODE_BUDGET`; later definitions still run and no case is added.
5. A completed depth result is `SUPPORTED_4X4_DEPTH5_TRANSFER` only when at least
   90% of exact decisive A/B directions match and zero exact draw is called
   decisive by the frozen sampled-direction rule.
6. Any completed result with a decisive-direction accuracy below 90% or at least
   one exact-draw decisive error is `NOT_SUPPORTED_4X4_DEPTH5_TRANSFER`.

`SUPPORTED_4X4_DEPTH5_TRANSFER` authorizes only a separate outcome-blind 4×4
family-viability plan. `INCONCLUSIVE_LABEL_COVERAGE`,
`INCONCLUSIVE_NODE_BUDGET`, or `NOT_SUPPORTED_4X4_DEPTH5_TRANSFER` is terminal for
this one-shot lane and directs `RETIRE_PLACE_VS_MOVE_FAMILY`. Do not add cases,
change strata, rerun with another seed set, increase a budget, or substitute
cross-strength agreement for exact truth.

## Frozen inspection

The final artifact includes all 32 definitions in manifest order. Reasons annotate
exact A, exact B, exact horizon draw, direction mismatch, node censor, and exact-
draw decisive error, but no reason filters the inspection. This small complete
inspection avoids adaptive samples or controls and cannot alter membership,
thresholds, assessment, or next branch.

## Non-goals

- Do not use the prior 12 outcome-admitted 4×4 cases as labels or members.
- Do not run seed `20260902`, 5×5, max-12/max-32 4×4, or a larger exact cap.
- Do not change generator weights, gates, depth, heuristic, seeds, node budget, or
  sampled-direction semantics.
- Do not add capture, stalemate draw, a second runner, or a new action primitive.
- Do not infer fairness, richness, fun, prevalence, generator quality, or family
  viability from this calibration corpus.
- Do not nominate a game or ask for human playtesting from this plan.

## Pure pre-outcome checkpoint

The first implementation slice is complete and independently reviewed. It adds a
dedicated exhaustive generator-v2 4×4/max-8 enumerator plus a pure calibration
module that accepts only authenticated bytes and detached JSON. Importing that
module does not load solver, play, agents, filesystem loaders, or experiment
edges.

The byte-replayed closed history contains 22 fixed sources: the reviewed
Plan-0010 21-artifact ledger graph plus the separately authenticated outcome-free
Plan-0010 manifest. It reconstructs 2,243 definition occurrences, 1,172 exact
definition identities, 1,168 D4 identities, and 31 historical schema-v1
4×4/max-8 identities. The native vocabulary intersects 22 of those identities;
eight fail the frozen definition gates and 14 are eligible exclusions. The 14
are carried by the three declared runs as 1/5/9 occurrences with one overlap.

The implemented census reproduces 16,320 raw definitions, 2,040 D4 orbits,
1,592 gate-valid orbits, and 1,578 fresh gate-valid orbits. Every one of the 32
strata has the declared 35–61 members. The pure selector fixes one canonical D4
orientation per stratum and publicly reconstructs all cases, pool roots, state
bounds, and fingerprints. The principal frozen roots are:

- closed-history projection:
  `b576e88bee320df83d4e2aa73c981e5f2a20e8db8b2b88744b832a0e6f50f3ae`;
- eligible pools:
  `963ab02ee731c8f4d42574f92d98bd2f5772e1e380b2e4c5bff1b95adba44e99`;
- selection fingerprint:
  `bcf9992cd2479536da193b7a206f5988e993f5eb700f1e421c7b453480bce834`.

The public state proof reconstructs every ply layer, the 62,096/40,272 per-case
bounds, and the 1,637,888 fixed-corpus sum. Independent review found and closed a
boolean-as-integer array validation defect and a forged-`GameDefinition` parser
bypass; final algorithm and provenance reviews report no remaining P0–P3 defect.
All 343 dependency-free tests pass. No production manifest, exact label, sampled
profile, reservation, lock, or outcome artifact exists at this checkpoint.

## Pure exact-evaluator checkpoint

The second implementation slice adds `four_by_four_evaluation.py`, a pure fixed
32-case exact schedule, executor, builder, and public validator. Its public
execution surface accepts only the frozen manifest and closed-history witness;
the solver, 100,000-state cap, and monotonic clock are fixed at the production
boundary. The module has no filesystem, Git, reservation, lock, or one-shot
capability.

Every raw slot is bound to manifest order, case and stratum identity, definition
and D4 hashes, case fingerprint, and the public per-case state bound. Completed
evidence retains the exact value, forced result, terminal reason, full principal
variation, searched states, cache hits, and descriptive elapsed time. Public
reconstruction reparses every definition, replays every action to a terminal
state, checks the result/value/reason relation, enforces the frozen solver's
minimum search and PV-reconstruction accounting, and rejects unknown fields,
non-finite numbers, booleans disguised as integers, schedule changes, or derived
field tampering.

`DRAW/PLY_LIMIT` is normalized as `HORIZON_DRAW`; a ply-8 `GOAL` remains decisive.
Any `CENSORED_STATE_BUDGET` payload is rejected immediately because it contradicts
the structural proof. The result rebuilds all-case, first-player, goal-relation,
runner-start, vector-band, and all-32-strata summaries; a timing-free,
domain-separated raw-slot digest; and all 32 manifest-order inspection rows with
definitions and replay traces.

Coverage is `SUFFICIENT_LABEL_COVERAGE` only with at least 15 decisive labels,
four A wins, four B wins, four horizon draws, and two strata for every label. A
shortfall is `INCONCLUSIVE_LABEL_COVERAGE`, blocks depth 5, and preserves the
predeclared `RETIRE_PLACE_VS_MOVE_FAMILY` branch. Sufficient coverage makes depth
5 only `ELIGIBLE`; exact labels alone cannot support transfer.

The implementation and tests use only legal synthetic/test-double traces. They
have not invoked the fixed public solver on selected cases and have not created a
production manifest, exact result, reservation, lock, or label.

Three independent adversarial reviews found and closed finite-timing aggregation,
impossible search-accounting, and private-callback input-mutation defects. They
then reported no remaining P0–P3 defect. The responsibility boundary remains
explicit: replay proves terminal consistency, while minimax origin will depend on
the fixed public executor plus later executable fingerprints and one-shot byte
seals. All 353 dependency-free tests pass.

## Pure depth-5 evaluator checkpoint

The third implementation slice adds `four_by_four_depth.py`, a pure fixed
all-case depth-5 schedule, executor, result builder, and public validator. The
public executor accepts only the manifest, closed-history witness, and validated
exact result. Depth 5, seeds `0..29`, the cumulative 5,000,000-node cap, one fresh
agent per definition, one reset before seed 0, and the production `MinimaxAgent`
are not injectable at that boundary. The private callback seam exists only for
legal synthetic tests and is not exported.

Exact evidence is fully reconstructed before the first agent is created and must
show 32/32 completion, zero censor, sufficient trusted A/B/horizon-draw coverage,
and an eligible depth disposition. Factory schedule entries contain only
definition-derived case identities; no exact label, forced result, terminal
reason, or principal-variation fact reaches the agent. Every successful action
is an exact legal `Action`, round-trips through the engine encoding, and is bound
to an immediate strict snapshot of agent identity, configuration, and cumulative
nodes. Cross-definition agent reuse, a nonzero post-reset budget, configuration
drift, nonmonotone or insufficient node growth, cap overflow, callback input
mutation, and malformed budget exceptions fail closed.

Completed profiles retain all 30 seed-ordered games, full action traces,
terminal outcomes, per-game and cumulative node ledgers, and descriptive timing.
A genuine node censor retains the completed seed prefix plus the next nonterminal
action prefix, permits zero consumed nodes only when no completed action requires
more, suppresses only later seeds for that definition, and leaves later
definitions scheduled. Public reconstruction verifies root-action lower bounds,
all raw slot identities, exact-direction confusion, exact-draw decisive errors,
all definition-only breakdowns, the timing-free evidence digest, and all 32
inspection rows.

Transfer assessment gives any node censor priority as
`INCONCLUSIVE_NODE_BUDGET`. With all profiles complete it requires an integer
90% floor on exact decisive-direction matches and zero decisive classification of
an exact horizon draw. Play-shape and dominance codes remain descriptive and
cannot route the result. The standalone assessor independently rechecks the
frozen exact-label coverage floor.

Three independent adversarial reviews cover transfer semantics, callback and
node-budget integrity, and raw-result provenance. They found and closed
standalone coverage, strict-boolean, incomplete-prefix node, runtime agent-drift,
and hostile-container context-mutation gaps, then reported no remaining P0–P3
defect. The fixed public Minimax path has not been invoked, and no production
manifest, exact result, sampled profile, reservation, lock, or outcome artifact
has been created. All 367 dependency-free tests pass.

## Closure — `SUPERSEDED_PRE_OUTCOME`

This plan was superseded before its irreversible production boundary because the
project was explicitly redirected from further place-versus-move calibration to
broader family discovery. This is a strategic closure, not a negative calibration
result and not evidence that depth 5 does or does not transfer to 4×4.

The three reviewed pure slices remain preserved at commit `96fa5b7`:

- the outcome-free 16,320-definition census, authenticated history projection,
  32-stratum selector, and exact state proof;
- the fixed 32-case exact executor and public raw-result reconstruction;
- the fixed 32-profile depth-5 executor and public trace/node reconstruction.

All 367 dependency-free tests passed at that checkpoint. The frozen planning
roots, deterministic selector, schedules, thresholds, seeds, caps, and tests must
not be rewritten or reinterpreted. They remain an available, unspent 4×4
evaluator-audit design if a later family-independent question justifies resuming
it under a new decision.

No Plan-0011 production manifest, selected exact label, sampled profile, run,
reservation, attempt, failure record, lock, or outcome artifact was created. The
planned one-shot edge was not implemented or invoked. Consequently no one-shot
membership or evaluator outcome was spent, and no production conclusion may be
inferred from this closure.
