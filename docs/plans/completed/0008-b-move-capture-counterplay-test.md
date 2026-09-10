> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0008 — B move-capture paired counterplay test

## Objective

Test the smallest direct interaction suggested by the failed stalemate treatment:
allow B's runner to enter a cell occupied by an A seed, remove that one seed, and
finish the move on that cell. Preserve the board, setup, goals, vectors, first
player, ply cap, generator membership, agents, evaluator gates, and schema-v1
terminal semantics. Measure counterplay leverage, overcorrection, and cycling; do
not present this diagnostic as a fairness-discovery experiment.

## Hypothesis

Capture-on-entry will change at least four paired-valid baseline A containment
wins into non-horizon B goal wins across at least two predeclared strata. At least
four paired-valid treatment principal variations across two strata will actually
execute a capture. The response is useful enough for separate validation only if
strong, shape-clean capture-engaged cases include at least one exact A win and one
exact B win; a one-sided B response or ply-limit cycling rejects this primitive as
the next discovery substrate.

## Expected result

All 128 treatment definitions solve below the frozen 100,000-state cap. Capture
reduces some A containment wins, but may either overcorrect toward B or create
18-ply replacement cycles. Any treatment draw is necessarily `PLY_LIMIT` under the
restored terminal semantics and is reported as unresolved horizon behavior, never
as fairness. A separately committed depth-5 lane tests at most 32 exact-completed,
paired-valid, non-horizon cases whose value or optimal line responds to capture.

## Definition of done

- [x] Add strict schema-v3 `MOVE_CAPTURE` parsing, canonicalization, derived prose,
  engine transitions, replay, D4 identity, and simplicity accounting while
  preserving every frozen schema-v1/v2 byte, hash, prose statement, and behavior.
- [x] Prove and test the 43,776-state structural upper bound for the paired 3×3,
  18-ply, one-runner capture family; preserve the 100,000-state exact cap.
- [x] Build a deterministic capture-outcome-free 128-pair manifest from all and
  only the `max_plies=18` cases in the original frozen landscape manifest.
- [x] Re-evaluate all 128 v1 baselines before treatment and seal timing-free
  candidate-level replay evidence or its ordered digest; never infer replay success
  from the treatment denominator.
- [x] Add exact and sampled capture-use evidence, monotonicity checks, paired
  transition summaries, adaptive depth-5 stress, and frozen inspection selection.
- [x] Add fail-closed one-shot manifest, raw, and stress runners with separate
  reservations, attempts, byte locks, Git provenance, and public validators.
- [x] Obtain independent pre-outcome review of the one-variable semantics,
  state-bound proof, outcome-free construction, replay attestation, monotonicity,
  capture evidence, assessment order, and evidence chain.
- [x] Commit implementation and protocol before computing any schema-v3 corpus
  outcome.
- [x] Freeze and commit the paired capture manifest from a clean implementation
  commit.
- [x] Run and commit the raw paired response once from the clean manifest commit.
- [x] Run and commit the predeclared adaptive stress once from the committed raw
  record unless an integrity or exact-censor stop condition fires.
- [x] Inspect the frozen qualitative sample, report every assessment, and choose
  the next branch without changing thresholds.

## Single interaction primitive

Schemas v1 and v2 are immutable. Schema v3 restores schema-v1 terminal behavior
and adds one action kind:

```json
{"kind": "MOVE_CAPTURE", "piece": "runner", "vectors": [[-1, 0], [1, 0]]}
```

`MOVE_CAPTURE` uses the same from/to action arity and listed one-step vectors as
`MOVE`. An in-bounds empty destination produces the existing move. A destination
occupied by an opponent piece is also legal: that one piece is removed and the
moving piece occupies its cell. A destination occupied by the mover's own piece
remains illegal. There is no jump, push, ranged capture, multi-capture, capture
obligation, capture quota, reserve, score, or new goal. In this corpus only B has a
moving piece, so the treatment gives no new action to A.

Schema v3 has no `terminal_policy`. Goal completion remains first, the 18-ply cap
second, and next-player immobility awards the acting player a win as in schema v1.
The treatment changes each source definition only by `schema_version: 1 → 3` and
B's action kind `MOVE → MOVE_CAPTURE`. Display name, board, setup, goals, vectors,
move order, and maximum plies remain byte-equivalent after those two declared
fields are excluded.

Derived prose must explain capture in its own statement. Simplicity accounting
adds one primitive and learned concept plus the capture condition, while retaining
the same action parameters and action substeps. This complexity change is reported;
it cannot be hidden by treating `MOVE_CAPTURE` as a renamed `MOVE`.

## Why capture-on-entry

The stalemate result showed that A's containment, not the terminal label, is the
mechanical bottleneck. Capture-on-entry directly contests a placed barrier and can
also break A's connection, while preserving B's existing movement vectors and one
from/to move.

- Adjacent `REMOVE` would add a separate stationary action and tempo choice.
- `PUSH` would add a second destination, boundary cases, and an empty-space
  precondition.
- `SWAP` would move an opponent piece and add a less legible cycle mechanism.
- Letting A capture the runner would strengthen the already dominant exact role.
- Combining capture with schema-v2 stalemate draw would change two primary variables
  and is forbidden in this experiment.

## Paired corpus

The sole membership source is the original outcome-free landscape manifest with
SHA-256 `f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1`.
Select every one of its 128 `max_plies=18` cases: four representatives in each of
32 structural strata. Do not select from the completed schema-v2 results. Protocol
design is informed by the known v1 containment and schema-v2 failure, but treatment
membership is capture-outcome-free.

The historical baseline source remains raw landscape run
`20260830T200230881318Z-landscape-f407aefb`, byte SHA-256
`1edf571bc140a0cd586340eafee2306bccf6ca3a0816f8809b07edc9ef1a9fa4`.
The freezer must not read this raw result. It validates the same board-size,
one-runner, A-place/B-move family and records source/treatment DSL and D4 hashes,
stratum, pair fingerprint, source-manifest byte hash, and frozen executable
fingerprints without any evaluation field.

## Exact-state bound and monotonicity

At every reachable treatment state there is exactly one B runner. Each of the
other eight cells is either empty or contains one A seed, so a fixed ply has at
most `9 × 2^8 = 2,304` board arrangements. Side to move is fixed by first player
and ply parity. Across plies 0 through 18, at most `19 × 2,304 = 43,776`
board/ply states exist; terminal status is a deterministic function of such a
reachable state. The frozen 100,000-state cap is therefore nonbinding for this
family. A censor is an implementation, provenance, or proof failure and stops
interpretation.

For every completed treatment solve, the public validator requires
`type(searched_states) is int` and `1 <= searched_states <= 43_776`; booleans are
rejected explicitly. Exceeding the structural bound is an integrity failure even
when the looser 100,000-state execution cap was not reached.

The treatment preserves every existing B move and adds capture choices only at B
nodes. In zero-sum exact minimax, use the A-value order
`B_WIN < DRAW < A_WIN`: treatment value must be less than or equal to baseline
value. Any increase, including `B_WIN → DRAW`, `B_WIN → A_WIN`, or
`DRAW → A_WIN`, is a monotonicity violation and an integrity stop, not an
observation.

For this plan, a `paired-valid` case means that both the replayed schema-v1 source
and the schema-v3 treatment have `analysis_gate_passes=true` under the unchanged
static, asymmetry, and simplicity gates. Whenever a response threshold, stress
eligibility rule, frontier, or cycling assessment says valid, it means this paired
criterion. Source-only or treatment-only validity is still reported separately but
cannot admit a case to those conclusions.

## Raw paired evaluation

Before any frozen-corpus schema-v3 solve, reparse and evaluate all 128 v1
definitions with the frozen static, asymmetry, simplicity, cheap-play, and exact
components. Require the same timing-free candidate evidence as the pinned
landscape raw source. Seal the ordered replay evidence (or a collision-resistant
ordered digest plus per-case digests) inside the raw artifact and validate it
against the pinned baseline on later reads. Elapsed time is descriptive and
excluded from equality.

The replay projection is versioned as `capture-v1-replay-attestation-v1`. In
manifest pair order, each projection contains `pair_id`, `case_id`, definition and
D4 hashes, stratum, vector count, canonical definition, static report, asymmetry
report, simplicity report and pass flag, analysis-gate flag, cheap profiles and
failure codes, and exact status/result/budget observation; all timing fields are
excluded. Canonical JSON uses UTF-8 with sorted keys, no insignificant whitespace,
and non-ASCII characters unescaped. Each case digest is SHA-256 over the ASCII
domain `capture-v1-replay-case-v1`, one NUL byte, and that canonical JSON. The
ordered root is SHA-256 over `capture-v1-replay-order-v1`, one NUL byte, and
canonical JSON of the ordered `(pair_id, case_id, case_digest)` list. The raw
record stores the version and separate `observed` and `pinned_expected` ordered
case-digest lists and roots. Its validator independently rebuilds both sides from
the fresh replay and the pinned source, requires byte equality, and rejects
missing, extra, duplicated, or reordered cases before treatment.

Then evaluate all 128 treatments exactly with the 100,000-state cap, independent
of gates. Run weak-random and medium-goal-directed over seeds `0..29` on every
treatment with `analysis_gate_passes=true` under the unchanged play gates. Store
enough per-game action evidence to replay capture counts rather than trusting
aggregate use fields.

For exact PVs and each sampled profile report:

- number of captures, first capture ply, games with capture, and capture-count
  histogram;
- baseline-to-treatment result and terminal transition;
- normalized PV common prefix, treating an empty `MOVE_CAPTURE` as the paired v1
  `MOVE`, plus PV length delta;
- whether value changed even though the selected treatment PV contains no capture,
  distinguishing capture threat from realized capture;
- `PLY_LIMIT`, repeated board-position, and capture/replace-cycle diagnostics;
- static, asymmetry, simplicity, cheap failures, direction confusion, exact state
  work, and every structural-stratum breakdown.

For every sampled game, seal the profile, seed, complete ordered action list,
terminal outcome, and terminal ply. A validator replays each action from the
definition and derives capture evidence from the pre-action destination occupant;
the `MOVE_CAPTURE` kind alone does not prove that a capture occurred. Exact PVs are
validated and measured by the same state-aware rule. Aggregate capture counts,
first-capture plies, histograms, repeated board-plus-side positions (ply excluded),
and capture/replacement-cycle flags must all be reconstructed from those traces.

Capture ply numbers are one-based action plies and are `null` when no capture
occurs. For each complete 30-game profile, the capture-count histogram maps a
nonnegative capture count to its number of games, sums to 30, and determines
`games_with_capture`. A node-censored strong record preserves the completed seed
prefix and its full traces, marks the next seed incomplete, and reports no complete
profile or frontier metrics; partial counts remain descriptive only. The repetition
key is the canonical ordered `(owner, piece, position)` board plus side to move,
excluding ply and outcome. `replacement_recapture` means that B captures on a cell,
A later places on that same cell, and B later captures there again. A
`capture_replace_cycle` requires both `replacement_recapture` and a repeated
repetition key; validators derive both flags from action/state history.

Normalized PV comparison walks the baseline and treatment states together. Equal
`PLACE` actions match. A treatment `MOVE_CAPTURE` matches a baseline `MOVE` only
when from/to coordinates match and the treatment destination is empty immediately
before that action; a realized capture, coordinate difference, or any other kind
difference ends the common prefix.

A primary counterplay response is a paired-valid baseline `A_WIN` ending in
`NO_LEGAL_ACTION` that becomes a treatment `B_WIN` ending in `GOAL`. Horizon draws
and static rejects never count. Semantic response is:

- `SUPPORTED` at four or more primary responses across at least two strata;
- `NOT_SUPPORTED` at zero;
- otherwise `INCONCLUSIVE`.

Realized-capture response is assessed separately with the same four-case,
two-stratum threshold on paired-valid, non-horizon exact PVs containing a capture.

## Adaptive interaction stress

Commit the raw record before stress. Eligible cases are paired-valid,
exact-completed, non-`PLY_LIMIT` treatments for which either exact value changed or
the treatment PV executes a capture. Select at most 32 without replacement:

1. cases with no cheap `EXCESSIVE_DRAWS`, `TOO_SHORT`, or `TOO_LONG`, ordered by
   `sha256("capture-stress-clean-v1:" + treatment_definition_hash)`;
2. remaining eligible cases ordered by
   `sha256("capture-stress-other-v1:" + treatment_definition_hash)`.

Run minimax-v1-depth5 over seeds `0..29` with a cumulative 5,000,000-node cap per
definition. Preserve per-game capture evidence. Exact outcomes remain authoritative;
any sampled-direction mismatch is an evaluator error and cannot support capture.

An interaction-frontier case completes without censoring, has no frozen strong
duration or draw failure, matches the exact A/B direction, and executes at least
one capture in its strong games. Dominance and weak/medium disagreement remain
visible but do not by themselves remove a diagnostic interaction case. General
strong-response support requires at least 15 completions, no exact/node/candidate
censor, and no directional error; fewer completions remain `INCONCLUSIVE` even
when interaction-frontier coverage is complete.

For this assessment, sampled direction `A_WIN` matches exact `A_WIN` and sampled
direction `B_WIN` matches exact `B_WIN`. Any other pairing is a directional
mismatch, including `DRAW_OR_BALANCED` against either non-horizon exact result.
Frozen dominance failure codes remain separate shape observations and do not
replace this exact-match rule.

## Predeclared assessment order and decisions

1. Any source, replay, pair, executable, lock, ancestry, reservation, aggregate,
   action-replay, 43,776-state-bound, or monotonicity mismatch is an integrity
   failure and stops.
2. Any exact state censor makes all response conclusions `INCONCLUSIVE` and stops
   before adaptive stress. Audit the 43,776-state proof or solver.
3. Report every treatment `PLY_LIMIT` as cycling/horizon evidence. Such cases do
   not count toward counterplay or interaction frontiers and the cap is not raised
   after inspection.
4. Apply the primary and realized-capture response thresholds independently.
5. Any depth-5 sampled direction unequal to the non-horizon exact result, including
   `DRAW_OR_BALANCED`, makes strong response `NOT_SUPPORTED` and frontier/overall
   response `INCONCLUSIVE` with evaluator-error priority.
6. Node censoring or any eligible case left unselected by the candidate cap makes
   frontier, general stress, and overall response `INCONCLUSIVE`. A cheap-shape
   failure cannot prove that an untested strong profile would fail the interaction
   frontier.
7. With complete evidence, classify the interaction frontier by exact result. It is
   `ROLE_DIVERSE` with at least one A-win and one B-win case, `ONE_SIDED_A` when all
   are A wins, `ONE_SIDED_B` when all are B wins, and `EMPTY` at zero.

Define cycling dominance before choosing a branch. Among paired-valid baseline
`A_WIN`/`NO_LEGAL_ACTION` cases whose treatment exact value changes, cycling is
`DOMINANT` only when the number ending at treatment `PLY_LIMIT` is strictly greater
than the number ending in a non-horizon treatment `B_WIN`; an empty pool or a tie is
not dominant. After the ordered assessments above:

- A supported primary response, supported realized-capture response, and
  `ROLE_DIVERSE` frontier with at least four total frontier cases across two strata
  triggers a separately frozen, outcome-blind capture validation corpus.
- With complete evidence and no cycling dominance, a `ROLE_DIVERSE` frontier that
  does not meet the full trigger receives only a focused outcome-blind validation.
- A `ONE_SIDED_B` frontier rejects unrestricted capture-on-entry as an overcorrection;
  do not add stalemate draw to rescue it.
- A `ONE_SIDED_A` frontier rejects capture as demonstrated interaction without
  useful B counterplay.
- Cycling dominance takes priority over every complete-evidence validation branch
  and rejects capture as a cycling/stall mechanism; do not silently extend the cap.
- Zero frontier cases with complete evidence rejects capture-on-entry and triggers
  a family-level reassessment before another primitive is added.
- Any incomplete exact or frontier evidence remains `INCONCLUSIVE`; do not infer a
  missing branch or raise a cap after outcomes are visible.

The composite `overall_interaction_response` is applied only after integrity and
completeness checks. Integrity failure yields no trusted assessment. Exact censor,
node/candidate censor, or directional mismatch yields `INCONCLUSIVE`. With complete
evidence, cycling dominance or an `EMPTY`, `ONE_SIDED_A`, or `ONE_SIDED_B`
frontier yields `NOT_SUPPORTED`. It is `SUPPORTED` only when both raw response
assessments are `SUPPORTED` and a `ROLE_DIVERSE` frontier contains at least four
cases across at least two strata. Any other complete `ROLE_DIVERSE` result is
`INCONCLUSIVE` and takes the focused-validation branch. General strong-response
status is reported independently: its fewer-than-15 rule does not override a
complete interaction-frontier assessment.

## Frozen exploratory inspection

The raw record freezes a pre-stress inspection selection containing every exact
censor and treatment `PLY_LIMIT`, plus 16 primary outcome changes ordered by
`sha256("capture-inspection-change-v1:" + treatment_definition_hash)` and 16
outcome-unchanged controls ordered by
`sha256("capture-inspection-control-v1:" + treatment_definition_hash)`. It also
seals `adaptive_stress_disposition` as `ELIGIBLE` or
`BLOCKED_EXACT_CENSOR`. In the blocked case, no stress reservation is created and
the raw selection is final.

When stress is eligible, its separately committed record extends that frozen
selection with every depth-5 censor, interaction-frontier case, and stress-selected
case. Record overlapping inclusion reasons and every pool shortfall. An integrity
failure, including a monotonicity violation, produces permanent failure evidence
instead of a trusted raw result and is audited as a protocol failure rather than as
qualitative game evidence. Inspection cannot change a label, threshold, cap, or
branch.

## Outcome

The outcome-free manifest froze 128 pairs across 32 strata. Fresh baseline replay
matched the pinned landscape evidence case-for-case and root-for-root. Treatment
exact solving completed 128/128 without censoring or `PLY_LIMIT`, used at most
19,158 of the proved 43,776 states, and passed all monotonicity checks. Exact
outcomes changed from baseline A/B = 93/35 to treatment A/B = 32/96: 61 A wins
became B wins. The primary response was `SUPPORTED` at 37 cases across 23 strata,
and realized-capture response was `SUPPORTED` at 74 cases across 26 strata.
Cycling dominance was `NOT_DOMINANT`, although 45 exact PVs contained the strict
replacement/repetition motif.

Stress eligibility was much broader than expected: 88 cases, of which the frozen
cap selected 32 clean cases and left 56 untested. All selected cases completed
depth 5 without node censoring or direction mismatch and entered the descriptive
interaction frontier. They comprised three exact A wins and 29 B wins across 17
strata. Every profile was 30–0 in its exact direction, producing three
`A_DOMINANT` and 29 `B_DOMINANT` failures.

## Interpretation

Capture-on-entry is real counterplay rather than a terminal relabel: it breaks A
containment across many structures, including 14 value changes whose selected PV
does not execute a capture. It does not yet establish a useful discovery
substrate. Results turn sharply toward B at four or more movement vectors, all
strongly evaluated cases are internally role-dominant, and long replacement-
recapture motifs remain common in exact lines.

The formal frontier and overall result remain `INCONCLUSIVE`. The 56 unselected
eligible cases make the registered category `null`; `ROLE_DIVERSE` is descriptive
only. Neither that observation nor the 29-to-3 B skew may be promoted to a
validation or rejection branch after inspecting the capped sample.

## Decision

Close as `CLOSE_INCONCLUSIVE_WITHOUT_CAP_EXTENSION`. Do not run the 56 unselected
cases, alter the cap, adopt or reject capture from this run, combine it with
stalemate draw, or promote an inspected definition as a candidate. A new,
outcome-blind fixed-membership replication may test the fresh three-versus-four
vector boundary while leaving this result unchanged.

Result report:
[`../../../experiments/reports/0008-b-move-capture-counterplay-result.md`](../../../experiments/reports/0008-b-move-capture-counterplay-result.md).
