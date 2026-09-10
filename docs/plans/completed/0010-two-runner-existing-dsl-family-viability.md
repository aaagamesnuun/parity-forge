> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0010 — Two-runner existing-DSL family viability

## Objective

Test whether the narrow 3×3 place-versus-move family can produce non-dominant
interaction through the smallest remaining setup change: give B two identical
ordinary runners instead of one. Preserve schema v1, movement, goals, terminal
semantics, board, agents, gates, and fixed all-case evaluation. Freeze 64 fresh
pairs without treatment outcomes, then compare every source and treatment exactly
and under depth-5 play.

This is the family reassessment required by Plan 0009. It is not a capture variant,
a new action primitive, a generator release, or a claim that an extra piece is
free complexity.

## Hypothesis

One runner leaves B vulnerable to monotone A containment, while unrestricted
capture removes too much of A's position. A second ordinary runner may provide an
alternate route and two-point spatial pressure without deleting or moving A seeds.
The setup is useful only if at least four treatment definitions across two
structural cells have non-dominant strong play, include both exact roles, and
actually expose the two-runner choice. Otherwise close this setup branch rather
than adding an action exception to rescue it.

## Expected result

All 128 exact slots and 128 depth-5 profiles should complete below the frozen
structural and node caps. The most likely result is another role-dominant shift,
but even a negative result is high-information: it tests the only simpler existing-
DSL counterplay intervention before 4×4 evaluator calibration or family retirement.

## Definition of done

- [x] Implement a pure one-to-two-runner transform whose source-witnessed removal
  of the frozen added setup entry restores the source canonical bytes and whose
  mechanical result commutes with every D4 transform.
- [x] Build and publicly reconstruct a closed evaluated-orbit ledger containing
  the 439 previously covered generator-v2 schema-v1 orbits plus the 64 disjoint
  Plan-0009 source orbits.
- [x] Authenticate a separate full-definition D4 projection over the same closed
  historical dependency graph plus the outcome-free Plan-0009 manifest, and use it
  to prove that neither side of a selected pair reuses any previously evaluated
  mechanical definition.
- [x] Reproduce without solver or play calls the planning census of 1,016 relevant
  corner-start source orbits, 907 after relevant exclusions, 738 paired-gate-valid
  pairs with 59 source/treatment gate disagreements, 477 treatment-unique pairs,
  16 strata, and at least 19 eligible pairs per stratum.
- [x] Add a deterministic outcome-free four-per-stratum manifest builder and
  validator with pool roots, selection fingerprint, source/treatment disjointness,
  and one-variable pair proofs.
- [x] Prove and validate natural termination by ply 13 when A starts and ply 14
  when B starts, plus the 69,120-state treatment bound under the existing
  100,000-state exact cap.
- [x] Add fixed source-then-treatment paired exact and all-case depth-5 evaluators
  with complete traces, runner-lineage diagnostics, aggregates, assessments, and
  inspection reconstruction.
- [x] Add fail-closed one-shot manifest, exact, and depth-5 runners with separate
  reservations, attempts, locks, failure evidence, clean commits, strict ancestry,
  byte seals, and noninjectable production boundaries.
- [x] Independently review membership blindness, D4 semantics, piece identity,
  state/termination proofs, fixed schedules, assessment priority, and evidence
  chains before any treatment outcome.
- [x] Run the complete dependency-free test suite and commit implementation,
  protocol, and review before freezing a treatment definition.
- [x] Freeze and commit the 64-pair manifest, run and commit paired exact once,
  then run and commit fixed depth 5 once unless a frozen stop condition fires.
- [x] Reconstruct all evidence, inspect the frozen sample, report every assessment,
  and close without changing membership, thresholds, agents, or budgets.

## Family-reassessment choice

The alternatives were compared lexicographically by rule complexity, retained
exact ground truth, causal isolation, and expected information value:

- moving directly to 4×4 changes the board and loses the current exact guarantee;
- PUSH needs a second destination plus boundary and occupancy conditions;
- adjacent REMOVE adds an action and invites place/remove stalls;
- SWAP preserves material but moves an opponent piece and adds easy reversible
  cycles;
- JUMP adds movement semantics without testing whether setup alone is sufficient;
- capture quotas or directional limits are outcome-driven exceptions to a rejected
  treatment;
- immediate retirement is premature while one low-complexity, already supported
  DSL setup intervention remains.

Two runners add one initial piece instance, increase operational choice, and leave
action types, piece types, learned action concepts, victory clauses, and state
variables unchanged. The multiplicity cost must be reported explicitly even though
the frozen simplicity schema does not currently count piece instances as a separate
structural field. This experiment does not change that evaluator while testing the
setup.

## One-variable treatment

Every source is an ordinary schema-v1 generator-v2 3×3 definition with
`max_plies=18` and one B runner in a corner of the edge opposite B's target. Its
treatment appends one identical B runner at the other corner of that same edge.

Examples:

- target `TOP`: source start `(2,0)` maps to added runner `(2,2)`, and vice versa;
- target `BOTTOM`: `(0,0)` maps to `(0,2)`, and vice versa;
- target `LEFT`: `(0,2)` maps to `(2,2)`, and vice versa;
- target `RIGHT`: `(0,0)` maps to `(2,0)`, and vice versa.

No midpoint source is eligible. Board, first player, maximum plies, both roles,
action vectors, goals, schema version, and the original runner are unchanged. The
display name is derived and excluded from the mechanical one-variable comparison.
The added piece has the same owner and piece kind as the original runner. Removing
exactly that added setup entry and restoring the source name must reproduce the
source canonical bytes.

Runners remain mechanically indistinguishable. Engine states, hashes, and solver
keys never label them. A validator may derive trace-local lineages from the two
starting positions and each retained action solely to report which start lineage
moved; lineage cannot affect legal actions, outcomes, transpositions, or identity.

The source is stored in its canonical D4 orientation. The treatment is stored in
the exact source orientation so the one-variable proof remains byte-local; source
and treatment are never transformed independently for evaluation. Planning found
only 284/1,016 relevant derived treatments, and 198/738 paired-gate-valid derived
treatments, already in their own canonical orientation. Validators therefore
require the correct treatment D4 identity and D4-equivariant derivation, never
canonical orientation of the stored treatment itself. Pair fingerprints bind both
canonical source bytes and same-frame derived treatment bytes.

## Natural termination and exact-state bound

Schema v1 MOVE cannot remove a piece. With two persistent B runners, at most seven
cells can receive A seeds. If A starts, its seventh placement occurs by ply 13; if B
starts, it occurs by ply 14. At that point the board is full and the next B turn has
no legal move unless a goal already ended play. Any treatment `PLY_LIMIT` is
therefore an integrity or semantics failure, not horizon evidence.

At a fixed ply, choose the two indistinguishable B-runner cells in
`C(9,2) = 36` ways. Each remaining cell is empty or contains an A seed, giving at
most `36 × 2^7 = 4,608` board arrangements. Side to move is fixed by first player
and ply parity. Across ply layers 0 through 14:

```text
15 × C(9,2) × 2^7 = 69,120 states
```

For a one-runner source, A can place at most eight seeds. Its eighth placement
occurs by ply 15 when A starts and ply 16 when B starts, after which B has no legal
move unless a goal ended play earlier. Thus source `PLY_LIMIT` is also impossible;
source definitions retain the proved, looser 43,776-state bound.

Game-state outcome does not add another multiplicative factor. Within this family,
definition plus board, ply, and first-player parity determine the actor that just
moved and the next side. Goal satisfaction, then ply cap, then next-player
immobility are deterministic under the frozen engine precedence, while static
validation excludes an initial goal. Terminal status, winner, and reason are
therefore uniquely determined for every reachable board/ply state.

Public validators require integer searched-state counts within the applicable
structural bound; booleans are rejected. The execution cap remains 100,000. A
state censor stops before depth 5 and does not authorize a larger cap.

## Outcome-free census and selection

The closed source exclusion set is the union of the 439 generator-v2 schema-v1 D4
orbits already authenticated by Plan 0009 and the 64 Plan-0009 source orbits. The
two sets are disjoint, so the expected source exclusion count is 503. Resolve them
from their pinned artifact dependencies and definitions, never from outcome fields
or a scan whose future contents could change membership.

A result-blind planning census found:

- 1,016 generator-v2 schema-v1 D4 orbits with 3×3, `max_plies=18`, corner start,
  and one through seven movement vectors;
- 907 sources after intersecting the 503-orbit global exclusion set with this
  vocabulary slice;
- 738 pairs after unchanged source/treatment static, asymmetry, and simplicity
  gates; 59 of the 907 have different source/treatment gate results and remain
  excluded rather than treated as an integrity error (all 59 are source-fail /
  treatment-pass; no source-pass / treatment-fail case was observed);
- 477 pairs after retaining one source for each unique treatment D4 orbit;
- 16 strata from
  `(first_player, goal_axis_relation, vector_band)`, where vector bands are
  `v1_3`, `v4`, `v5`, and `v6_7`;
- per-stratum eligible pools between 19 and 36.

Implementation must independently reproduce and freeze these counts. Any mismatch
blocks selection and requires a result-blind audit; it does not permit changing a
quota. Among the 477 treatment orbits, 261 have exactly two paired-gate-valid
source orbits. Group by treatment D4 hash and retain the candidate with the
lexicographically smallest source D4 hash; this representative choice occurs
before stratum selection and is bound into every root and fingerprint.

Select four retained pairs per ordered stratum for 64 total. Membership order is a
domain-separated SHA-256 score over only the source/treatment D4 identities and
stratum, with source then treatment D4 hashes as tie-breakers. Freeze the complete
eligible-pool root, ordered per-pool roots, representative-choice root, selection
fingerprint, and proof that selected source hashes are unique and outside the 503
evaluated source orbits. Separately authenticate a full-definition D4 projection
from every closed dependency and the Plan-0009 manifest; selected source and
treatment hashes must be absent from that exact historical set. The planning
census expects zero such collisions, but the reconstructed projection is
authoritative and any collision blocks freezing.

The selection adapter may authenticate full records, but the pure selector accepts
only detached definitions, identities, gates, and exclusion membership. Solver,
play, terminal result, admission, timing, or prior ranking fields are outside its
capability.

## Outcome-free implementation checkpoint

The pure implementation and its production adapters were independently rebuilt
and reviewed before any Plan-0010 manifest artifact or treatment outcome existed.
The closed graph contains the fixed Plan-0009 cutoff of 16 run artifacts, its four
supporting dependencies, and the outcome-free Plan-0009 manifest: 21 artifacts in
total. It projects 2,115 definition occurrences to 1,044 exact definitions and
1,040 D4 identities. The static corpus contributes its six valid definitions;
the authenticated `invalid-board-size` fixture remains an expected parse failure.

The reviewed production roots are:

- closed projection bundle:
  `755b5a5d8ae35d8222873275e87860effbdf7ec2266de3799814d20385b12ca3`;
- evaluated 503-orbit projection / D4 set:
  `7064501b4514b34420e6fe7f0d4927cb6b3fb84e8610cabb510f6265520471d6` /
  `0c83885bf5eb1e670327ae6618b67805ba3b023a4bab206e7d98d753544ff05a`;
- historical projection / D4 set:
  `0a4a38245c3666f215041d10383112e65c82f40bc5d2f510df2d4418d65c2f91` /
  `9c8b2d54659c5021fbc47dfa38cb435ed068132e6e790e5057d86a13f93c07ba`;
- relevant source, representative choice, and eligible-pool roots:
  `c8c598979357be9c04bb89d1b95cd10cb6536b853b10a0ee7c8354514d19827e`,
  `62ffa9c07ae84c7566330310f9029599b0c8d4e929a39272a583a2d5e4f4f859`,
  and `73dcda3d2845c01113b41ecf8d46b923f044e4ec11c1d80c205644de0028b706`;
- selection fingerprint:
  `8bb8feb104ce58e92729d593464acb6e08e2de9c59154440c15580a66db9eb91`.

All 8,128 D4-equivariance checks and the registered census reproduce without
solver or play imports. The complete dependency-free suite passes 277/277. Two
independent reviews found no remaining P0–P3 defect in the transformation,
closed projections, census, selector, root freeze, or manifest-root fail-closed
guards. This checkpoint does not freeze or write the production manifest and does
not authorize outcome computation.

## Exact evaluator checkpoint

The pure exact slice now fixes the all-source-then-all-treatment schedule and
accepts only an already frozen manifest or detached pair array. It has no
filesystem, Git, reservation, one-shot, or agent boundary. Before the first
treatment call it validates every source slot, reconstructs every completed PV,
and seals the ordered source evidence. A state-budget censor keeps its fixed slot
and does not suppress later definitions, but is valid only below the applicable
43,776/69,120 structural bound; reaching or exceeding that bound makes a censor a
proof contradiction. `PLY_LIMIT` is rejected on both sides before PV replay.

Runner diagnostics are a trace-local overlay witnessed by the source definition.
For every B decision the validator reconstructs legal-action counts by current
`ORIGINAL` and `ADDED` positions, the selected lineage, and whether both lineages
offered a legal action. It checks the overlay against the engine before and after
every retained move. Exact engagement is true only when the same treatment PV
moves `ADDED` and contains a both-lineage decision; saved lineage facts never enter
state, solver, D4, or definition identity.

The result validator rebuilds pair fingerprints, exact slots, lineage traces,
comparisons, response thresholds, fixed 4-cell/16-stratum breakdowns, timing, and
the exact-only inspection union from the manifest and raw slots. It rejects
manifest-validator input mutation or pair replacement. An independent review
found no remaining P0–P3 defect. Eleven focused and all 288 dependency-free tests
pass. No production manifest was written and no production solver or play call was
made at this checkpoint.

## Depth evaluator and evidence-chain checkpoint

The pure depth slice now reconstructs complete and node-censored profiles from
raw action traces. Each scheduled definition receives one fresh depth-5 agent,
reset once, whose 5,000,000-node limit is cumulative across both roles and seeds
`0..29`. All sources are executed, normalized, and timing-free sealed before any
treatment agent is constructed. A censor retains the completed seed prefix, the
next incomplete action and lineage prefix, and exact node accounting; it suppresses
only later seeds of that definition. Sampled `PLY_LIMIT` is an integrity failure on
both sides.

Strong frontier membership requires complete source and treatment profiles, both
sampled directions matching exact, no treatment duration/draw shape failure, and
one same completed treatment game whose lineage evidence is engaged. An exact PV,
events split across games, or a censored prefix cannot supply this condition.
Source shape failures do not remove the frontier. `A_DOMINANT` or `B_DOMINANT`
remains descriptive at the frontier and removes only candidate shape. Candidate
support retains the frozen four-case, two-structural-cell, both-exact-role gate.
The final validator rebuilds all fixed breakdowns, assessments, evidence seals,
and the manifest-ordered inspection union from exact evidence and raw profile
slots. Independent review found no remaining P0–P2 defect, and the recommended P3
boundary cases are permanent tests.

The filesystem edge now has three fixed, noninjectable production APIs and CLI
commands for manifest, exact, and depth. Manifest provenance binds the clean
freezer commit, active plan path/SHA/Git blob, a closed 31-file executable map,
the reviewed closed-projection root and exact ledger bytes, and only the
outcome-free five-file Plan-0009 manifest chain. The manifest lock binds ledger
and manifest hashes and byte lengths. Each later stage requires a strict descendant
commit and independently sealed reservation, attempt, upstream chain, source
chain, worktree, failure state, and completed record. Final checks re-seal the
completed chain immediately before returning. Internal, leaf, broken, and
reservation symlink redirections fail closed.

Independent one-shot and integrated pre-outcome reviews found no remaining P0–P3
defect after adversarial mid-stage, final-check, and authenticated-snapshot merge
mutations. All 330 dependency-free tests pass. This checkpoint creates no
Plan-0010 corpus or run artifact and computes no production outcome.

The reviewed depth implementation is committed at
`758a6b9e34435c7ad6b004f04e7e9b38bf81e909`; strict provenance and the three
one-shot edges are committed at
`50372757ce1a9c60d1a650000bcc2a845f6dd1b3`. The integrated review also verified
that the 31-file executable fingerprint closure is complete and that authenticated
snapshot maps reject a same-path/different-digest race before reservation or
evaluation.

## Fixed evaluation schedule

After an independently reviewed clean pre-outcome commit:

1. freeze and commit reservation, attempt, exclusion ledger, outcome-free
   manifest, and byte lock without calling solver or agents;
2. from the clean manifest commit, solve all 64 sources, validate and seal their
   ordered evidence, then solve all 64 treatments and commit the exact record;
3. only with 128 complete uncensored exact slots, run all 64 source depth-5
   profiles, seal them, then all 64 treatment profiles and commit the depth record;
4. use seeds `0..29`, minimax-v1-depth5, and a cumulative 5,000,000-node cap per
   definition, with fresh agents and budgets for every side and definition.

No gate, source result, treatment result, runner engagement, earlier profile, or
inspection reason may route, replace, or suppress a scheduled case. A node censor
retains the completed seed prefix and incomplete attempt, stops only later seeds of
that definition, and does not stop later scheduled definitions.

## Measures

Report all 64 pairs, all four vector bands, both first-player halves, both goal-axis
relations, and all four structural cells:

- source/treatment exact result, terminal reason, transition, PV, searched states,
  and cache hits;
- outcome change, containment-to-goal response, normalized PV prefix, and length
  delta;
- per retained exact and sampled trace, which start lineage moved, whether the
  added lineage moved, whether both lineages moved, and whether a B decision offered
  legal actions from both current lineages;
- source/treatment strong A/B/draw, direction, Wilson interval, dominance,
  duration, nodes, failure codes, and complete action traces;
- every censor, mismatch, shortfall, descriptive timing, and explicit piece-
  multiplicity delta.

Trace-local lineage reconstruction begins with `ORIGINAL` and `ADDED` at their
frozen start cells. A B move transfers the lineage at `from` to `to`. Because MOVE
cannot enter an occupied cell, this update is unambiguous. Lineage diagnostics are
evidence derived from actions; removing them must not change any result or game
identity.

An exact containment response is a paired-valid source `A_WIN/NO_LEGAL_ACTION`
becoming treatment `B_WIN/GOAL`. An exact two-runner engagement response has
complete treatment evidence whose single retained PV both moves the `ADDED`
lineage at least once and contains at least one pre-action B decision where legal
moves originate from both current lineages. Assess each at `SUPPORTED` for at
least four cases across two strata, `NOT_SUPPORTED` at zero, and `INCONCLUSIVE`
otherwise. Engagement is not called choice unless the both-lineage decision
condition is present.

A strong two-runner frontier case has complete non-horizon exact and source/
treatment depth-5 evidence; both sampled directions match their respective exact
results; and the treatment profile has none of `EXCESSIVE_DRAWS`, `TOO_SHORT`, or
`TOO_LONG`. In addition, at least one *same completed treatment game* must both move
the `ADDED` lineage and contain a pre-action B decision where legal moves originate
from both current lineages. Exact-PV engagement is reported separately and cannot
substitute for this strong-trace condition. Source duration/draw failure does not
exclude a case, matching the treatment-facing Plan-0009 frontier semantics.
Dominance remains visible but does not remove the case from this mechanical
frontier.

A candidate-shaped case additionally has neither `A_DOMINANT` nor `B_DOMINANT` in
the treatment profile. Candidate-shape is:

- `SUPPORTED` at four or more cases across at least two structural cells with both
  treatment exact A and B roles represented;
- `NOT_SUPPORTED` at zero;
- `INCONCLUSIVE` otherwise, including one to three cases or one exact role only.

This is a synthetic family-viability gate, not a fairness, richness, or enjoyment
claim and not authorization to promote an inspected game.

## Predeclared assessment priority

1. Any dependency, membership, D4, one-variable, natural-termination, executable,
   reservation, lock, ancestry, schedule, replay, state-bound, aggregate, or
   lineage reconstruction mismatch is an integrity failure with no trusted result.
2. Any exact censor makes response and candidate conclusions `INCONCLUSIVE` and
   prevents a depth-5 reservation.
3. Any source or treatment `PLY_LIMIT` contradicts the natural-termination proof
   and is an integrity failure.
4. With complete exact evidence, apply containment and engagement-response
   thresholds independently and run the full fixed depth schedule.
5. Any node censor or source/treatment direction mismatch makes frontier,
   candidate-shape, and overall conclusions `INCONCLUSIVE` after the full schedule.
6. With complete strong evidence, zero candidate-shaped cases yields overall
   `NOT_SUPPORTED_TWO_RUNNER_SETUP` and a family-reassessment branch.
7. Four or more candidate-shaped cases across two structural cells and both exact
   roles yields `SUPPORTED_TWO_RUNNER_SETUP` and authorizes only a separately
   planned two-runner generator hypothesis.
8. Every other complete candidate-shape shortfall remains `INCONCLUSIVE`; do not
   add cases or relax the role/cell threshold.

If the setup is not supported, compare one bounded 4×4 evaluator-calibration lane
against retiring this place-versus-move family before adding an action primitive.

## Frozen inspection

The final artifact must include every censor, mismatch, response, strong frontier,
and candidate-shaped pair; four outcome changes and four unchanged controls per
vector band under separate domain-separated scores; and the selection-rank-zero
pair in every stratum. Reasons form one manifest-ordered union with explicit pool
sizes and shortfalls. Inspection cannot change membership, thresholds, categories,
or the next branch.

## Non-goals

- Do not inspect or run Plan 0008's 56 unselected cases.
- Do not change Plan 0009's thresholds or formal category.
- Do not add or limit capture, or combine it with stalemate draw.
- Do not add schema v4, PUSH, REMOVE, SWAP, JUMP, a new goal, or a terminal policy.
- Do not change generator-v2 weights, agents, gates, dominance thresholds, or
  seeds while testing setup.
- Do not run 4×4/5×5, seed `20260902`, evolutionary search, or human playtesting in
  this experiment.
- Do not infer prevalence, proven fairness, strategic richness, or fun from an
  equal-stratum 64-pair diagnostic sample.

## Outcome

The outcome-free manifest froze all 64 pairs from the reviewed clean checkpoint
and reproduced the registered census, projections, roots, four-per-stratum
selection, and zero historical collision. It was archived at `eb0e032` with
manifest SHA-256
`3b7757ade9bd745eb1aff838455927115005dd8efe4d96ebaef51af213d228b9`.

Paired exact completed all 128 source/treatment slots without state censoring or
`PLY_LIMIT`. Source A/B was 35/29 and treatment A/B was 34/30. Only pair 064
changed value, from `A_WIN/GOAL` to `B_WIN/GOAL`. The exact containment response
was zero and is `NOT_SUPPORTED`. Thirty-one treatment PVs across 12 strata met the
strict two-runner engagement condition, so exact engagement is `SUPPORTED`. The
exact record was archived at `3450947`; its `run.json` SHA-256 is
`2353bfb8dbf545d6c3430a998b5fe60c5db9822c28c965f7a2adbacce0844e39`.

Fixed depth 5 completed all 128 profiles and 3,840 games without node censoring,
direction mismatch, draw, or incomplete node evidence. The run expanded 5,027,783
nodes; its largest profile used 117,030 of the frozen 5,000,000-node cap. Fifty-
four treatment cases had a same completed game that moved the added lineage and
exposed a both-lineage decision. The strong frontier retained 46 cases across all
16 strata and all four structural cells, with exact A/B = 24/22.

Every one of those 46 frontier profiles was 30–0 role-dominant: 24
`A_DOMINANT` and 22 `B_DOMINANT`. Candidate-shaped evidence is therefore empty.
Under priority 6, the formal overall result is
`NOT_SUPPORTED_TWO_RUNNER_SETUP` and the next branch is `FAMILY_REASSESSMENT`.
The depth record was archived at `d430e83`; its `run.json` SHA-256 is
`dd77cfbd1cb76763ed394d767ce5c296191d25f2589d0a48819de242526f8cda`.

Post-commit public reconstruction matched every manifest, exact, depth, lineage,
node, aggregate, assessment, inspection, narrative, and evidence-chain value.
Independent scientific and provenance audits found no remaining P0–P3 defect.

## Interpretation

The second runner is mechanically active but not a useful family-level balance
intervention. It produces alternate routes and both-lineage decisions in many
optimal and sampled traces, yet changes exact value in only one of 64 fixed pairs
and leaves every strong profile completely one-sided. Across-definition A/B
diversity therefore does not translate into within-definition candidate shape.

This is a complete negative result, not a threshold-adjacent one. There is no
candidate case to rescue by extending the sample, changing a quota, adding a third
runner, or combining the setup with a rejected capture or stalemate rule.

## Decision

Close as `NOT_SUPPORTED_TWO_RUNNER_SETUP` and follow `FAMILY_REASSESSMENT`. Do not
build a two-runner generator, extend this corpus, relax its candidate threshold,
or stack another exception on the setup.

Before introducing a new action primitive, compare one bounded 4×4 evaluator-
calibration lane against retiring this narrow place-versus-move family. Treat any
4×4 work first as evaluator calibration outside the exact 3×3 domain, not as a
candidate-discovery or family-viability claim.

Result report:
[`../../../experiments/reports/0010-two-runner-existing-dsl-family-viability-result.md`](../../../experiments/reports/0010-two-runner-existing-dsl-family-viability-result.md).

## Next action

Archive this completed plan and open one bounded, outcome-blind 4×4 evaluator-
calibration plan. Its first slice must establish what trustworthy ground truth or
cross-strength agreement is possible at fixed cost before any new 4×4 discovery
claim or action primitive.
