> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0006 — Three-by-three exact-outcome landscape (completed)

## Objective

Map the existing generator-v2 3×3 vocabulary without conditioning selection on
cheap-play or exact outcomes, so the next generator decision rests on structural
coverage rather than another small random batch.

## Hypothesis

An outcome-blind, D4-symmetry-deduplicated sample stratified across the main v2
structural variables will reveal whether any sampled cases combine an exact draw
with no frozen duration or draw-shape failure. If none appears across this broad
sample, blind changes to generator weights become a lower-value next step than a
targeted mechanic test.

## Expected result

A frozen 384-definition corpus covers 96 declared strata with four distinct
symmetry orbits each. All 384 definitions receive a budgeted exact solve independent
of static or cheap classification; static-valid cases also receive frozen cheap
profiles. Exact draws then receive a separate depth-5 stress run. The result selects
a validation experiment, generator-v3 hypothesis, solver-diversity task, or mechanic
test by a predeclared branch rather than post-hoc score tuning.

## Definition of done

- [x] Implement and test D4 structural symmetry canonicalization without changing
  authoritative DSL hashes.
- [x] Exhaustively enumerate the 36,720 generator-v2 3×3 definitions.
- [x] Exclude every definition from the three prior generated runs and its D4
  orbit, independent of prior status or outcome.
- [x] Select four deterministic, outcome-blind orbit representatives in each of 96
  strata and verify the ordered 384-case selection fingerprint.
- [x] Commit the frozen manifest before evaluating any selected case.
- [x] Add separate fail-closed runners for manifest freezing, raw landscape
  evaluation, and draw stress, with deterministic budgets and immutable provenance.
- [x] Freeze and commit the outcome-free manifest from a clean code commit.
- [x] Run the raw corpus once from a clean manifest commit and preserve its record.
- [x] Run the predeclared draw stress once from the committed raw landscape record.
- [x] Inspect every exact draw, every censored case, every diagnostic-frontier case,
  and 16 otherwise ordinary cases chosen by a predeclared hash rule; record the
  result and next decision.

## Frozen components

DSL v1, engine v1, generator-v2 vocabulary, static/simplicity/asymmetry evaluators,
play gates, random-v1, goal-directed-v1, minimax-v1-depth5, exact-solver-v1, seeds
`0..29`, the 100,000-state exact cap, and the 5,000,000-node depth-5 cap. Seed
`20260902` is not used.

## Outcome-blind corpus construction

Enumerate every v2 definition with board size 3. A D4 orbit transforms board
coordinates, connection edges, reach edge, runner start, and movement vectors;
role labels, first player, and maximum plies do not change. The orbit key ignores
the non-mechanical `name` field. It supplements rather than replaces the canonical
DSL definition hash.

Exclude the D4 orbits of every definition in the generator-v1 development run,
generator-v2 development run, and seed-`20260901` held-out run, regardless of its
evaluation status. Collapse the remaining vocabulary to one canonical-orientation
representative per orbit. Definitions with eight movement vectors are then excluded
because the frozen structural complexity gate rejects that entire class, so they
cannot answer the discovery question. Record their census rather than spending
exact compute on them. Define strata by:

- first player: A or B;
- relation between A's connection axis and B's travel-to-target axis: same or
  orthogonal;
- runner start on the opposite edge: edge midpoint or corner;
- maximum plies: 6, 9, or 18;
- movement-vector count: 1–3, 4, 5, or 6–7.

This gives 96 strata. A result-blind structural census found 36,720 definitions and
4,776 D4 orbits before exclusions; after known-orbit removal, every proposed stratum
has at least 19 eligible orbits. The uneven vector-count bands avoid spending a
quarter of the sample on the deterministically ineligible eight-vector class and
keep sparse vector classes adequately represented. Results remain descriptive and
cannot estimate population prevalence from four cases per stratum. Within each
stratum, order canonical-orientation representatives by
`sha256("landscape-v1:" + orbit_key)` and take the first four. The manifest must
contain definitions, DSL hashes, orbit keys, stratum labels, selection metadata,
exact vector counts, per-stratum eligible counts, and exact source fingerprints,
but no evaluation outcome. The three source run files necessarily contain prior
outcomes; the freezer parses those files but consults only run identity,
configuration, definition, and definition-hash fields for exclusion. Provenance
therefore records `source_files_contain_outcomes=true`,
`selection_outcome_fields_consulted=false`, and `outcomes_computed=false` rather
than claiming the source files were never accessed. If any stratum has fewer than
four eligible orbits, stop before freezing and revise the design openly.

## Manifest freeze sequence

Complete D4 code, census/selection code, all three runners, tests, and this protocol
without generating any outcomes, then commit that state. From the clean commit,
run the manifest freezer once. It must refuse prior attempt evidence, write
`manifest-attempt.json` before enumeration, call no evaluator or solver, recompute
all quotas and exclusions, and write the 384 cases plus provenance. Commit the
manifest, a separate byte-SHA lock record, and attempt evidence under
`experiments/corpora/landscape-v1/` without changing scientific rules. No case may
be substituted after an evaluation budget is exhausted.

The active plan's exact bytes are preserved in the freezer commit and manifest
provenance. Later runners verify that historical plan blob while comparing current
bytes only for executable sources, so ordinary execution-checkbox updates cannot
invalidate a stage. Editing current prose does not alter the frozen protocol or
runner constants; a scientific rule change requires a new protocol ID.

## Evaluation protocol

For all 384 cases, run the frozen static, asymmetry, and simplicity evaluators and
attempt exact solving up to 100,000 searched states. Exact routing is independent
of all other classifications. For every case that passes the static, asymmetry, and
simplicity gates, also run:

1. weak-random over seeds `0..29`;
2. medium-goal-directed over the same seeds.

Budget exhaustion is censored evidence, not a win, draw, rejection, or survivor.
Seal and commit this raw landscape record before any draw stress. From its completed
exact draws, select at most 32 cases: first all cases with no frozen cheap shape
failure among the static-valid, cheap-evaluated cases, ordered by
`sha256("draw-stress-clean-v1:" + definition_hash)`, then fill remaining slots from
other draws ordered by
`sha256("draw-stress-other-v1:" + definition_hash)`. Run depth 5 over seeds
`0..29` with a cumulative 5,000,000-node cap per definition. This adaptive lane is
an adversarial draw-handling diagnostic; its accuracy is not representative of the
full corpus. If more than 32 shape-clean draws exist, frontier completeness is
censored even when all selected searches finish.

A diagnostic-frontier case passes static, asymmetry, and simplicity gates; has an
exact draw and no frozen cheap shape failure (`EXCESSIVE_DRAWS`, `TOO_SHORT`, or
`TOO_LONG`); completed depth-5 stress; remains non-decisive under that stress; and
has no depth-5 failure code. It is not called fair or fun: exact draws may merely
encode the finite ply cap.

## Predeclared reporting and decision branches

Report static pass/failure counts, exact completion and A/B/draw distributions by
every stratum dimension and exact vector count, state/node/time budgets, cheap/exact
direction confusion, draw terminal reasons, and diagnostic-frontier definitions.
The equal-stratum design does not estimate generator-v2 outcome prevalence.

- Any corpus, source, selection, or provenance mismatch is an integrity failure and
  stops the run before outcome computation.
- Any exact censor makes a frontier-absence conclusion `INCONCLUSIVE`; improve
  exact-search efficiency or narrow the inference, never fill labels from play.
- Any completed exact draw called decisive at depth 5 makes draw stress
  `NOT_SUPPORTED` and prioritizes an independent solver or leaf-evaluator family.
  Otherwise draw stress is `SUPPORTED` only with at least 15 completions, no node
  or candidate-cap censoring, and no decisive error; fewer cases or any censoring
  is `INCONCLUSIVE`.
- Four or more diagnostic-frontier cases spanning at least two predeclared strata
  justify only a generator-v3 hypothesis, to be tested in a separately frozen run.
- One to three diagnostic-frontier cases trigger a focused, outcome-blind validation
  sample around those structures before changing the generator.
- Four or more diagnostic-frontier cases confined to one predeclared stratum trigger
  a separate single-stratum validation sample rather than a generator-wide change.
- Zero diagnostic-frontier cases with complete exact and frontier stress evidence
  makes blind generator-v2 reweighting low value and advances the smallest
  evidence-driven mechanic test. It does not prove the unsampled vocabulary empty.
- Exact draws that all retain shape failures must not become a generator objective.

The draw-stress support assessment and frontier-completeness assessment answer
different questions. Fewer than 15 completed draws, or any untested draw caused by
the 32-case cap, keeps general depth-5 draw handling `INCONCLUSIVE`. Decision
branches may nevertheless proceed when every shape-clean exact draw was tested
without node censoring and no exact draw was called decisive; unselected draws that
already have a frozen cheap shape failure cannot conceal a diagnostic-frontier
case. Exact censoring, an unselected shape-clean draw, or a node-censored
shape-clean draw makes the frontier itself `INCONCLUSIVE`.

After raw statuses are sealed, exploratory inspection includes every exact draw,
exact or depth-5 deferral, and diagnostic-frontier case, plus 16 remaining cases
with the smallest `sha256("landscape-inspection-v1:" + definition_hash)` values.
The stress record freezes this inspection list and the inclusion reason for every
case. Inspection cannot change any outcome or threshold.

## Outcome

The manifest froze 384 definitions across all 96 strata. Raw exact solving completed
384/384 without censoring: 256 A wins, 115 B wins, and 13 draws. Every draw ended at
the ply cap; 11 used six plies, two used nine, and none used 18. Only one exact draw
had no cheap duration or draw-rate failure, although it still had `B_DOMINANT`.

Depth-5 completed all 13 draw diagnostics without node censoring or decisive
misclassification. Every profile was 30/30 `PLY_LIMIT` draws and failed both
`EXCESSIVE_DRAWS` and `TOO_LONG`. The general stress assessment remains
`INCONCLUSIVE` because 13 is below the declared minimum of 15, while frontier
coverage is `COMPLETE` because the sole shape-clean draw was tested. The diagnostic
frontier contains zero cases.

## Interpretation

The broad equal-stratum sample found no evidence that generator-v2 weights conceal
a sampled exact-draw frontier with acceptable play shape. Its draw labels encode a
binding finite horizon rather than resolved strategic balance. These descriptive
counts do not estimate prevalence across the uneven generator vocabulary and do
not prove unsampled orbits empty.

## Decision

Follow the predeclared `DESIGN_MINIMAL_MECHANIC_TEST` branch. Preserve DSL v1 and
generator-v2, keep seed `20260902` untouched, and test one explicit terminal-policy
counterfactual on the fixed 18-ply subset: next-player immobility yields a draw
instead of an acting-player win. Do not combine this treatment with capture,
movement, generator, or evaluator changes.

Result report:
[`../../../experiments/reports/0006-three-by-three-outcome-landscape-result.md`](../../../experiments/reports/0006-three-by-three-outcome-landscape-result.md).
