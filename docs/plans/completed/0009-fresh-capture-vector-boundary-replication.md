> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0009 — Fresh capture vector-boundary replication

## Objective

Test on fresh generator-v2 3×3 D4 orbits whether the exact B-mobility boundary
observed under capture-on-entry reproduces between three and four movement vectors.
Freeze 64 paired-analysis-valid pairs without capture outcomes, run every source
and treatment through exact solving and depth-5 play, and distinguish a useful
mechanical boundary from broad B overcorrection or a cliff between two kinds of
role dominance.

This is a new replication, not completion of Plan 0008. Its 56 unselected cases,
32-case cap, formal `INCONCLUSIVE` result, and immutable artifacts remain unchanged.

## Prior-informed hypothesis

Plan 0008 informs the question and thresholds but never case membership. Its full
raw sample shifted from A/B = 93/35 to 32/96, while treatment outcomes by vector
band were A/B = 24/8 at one to three vectors, 4/28 at four, 4/28 at five, and 0/32
at six or seven. The three exact-A cases in the observed strong frontier included
two three-vector cases; every four-vector strong case was an exact and sampled B
win. No treatment ended at `PLY_LIMIT`, but every strong profile was 30–0 role-
dominant.

The replication hypothesis is therefore not that capture is fair. It is that a
fresh, structurally valid sample will show a reproducible three-to-four-vector
transition: at least eight exact A wins remain among the 32 three-vector
treatments, at least 24 exact B wins occur among the 32 four-vector treatments,
the global B-win increase `B4 - B3` is at least eight, and at least five of eight
matched structural cells satisfy `B4_cell > B3_cell`. A separate candidate-shape
assessment asks whether the boundary contains any non-dominant capture-engaged
games rather than merely switching which role wins every strong game.

## Expected result

All 128 exact solves and 128 depth-5 profiles complete within the frozen structural
and node caps. Capture again produces non-horizon value changes, but either the
three-vector side retains enough A results to establish a mechanical boundary or
both vector levels become broadly B-favored. Based on Plan 0008, the most likely
product-facing result is a replicated dominance cliff with zero candidate-shaped
interaction cases, which would trigger family-level reassessment rather than a
capture-aware generator.

## Definition of done

- [x] Implement and test an evaluated-orbit exclusion ledger with the frozen
  650/439 declared/matched D4 census and exact source byte identities.
- [x] Reproduce the planning census of 724 fresh three/four-vector orbits, 563
  paired-analysis-valid orbits, 16 strata, and at least 16 eligible orbits per
  stratum without solving or playing a treatment.
- [x] Add a deterministic outcome-free four-per-stratum manifest builder and
  public validator, including eligible-pool roots and one-variable pair proofs.
- [x] Reuse and validate the 43,776-state bound for both source and treatment.
- [x] Add a fixed all-case paired exact evaluator and one-shot runner with full PV,
  capture, monotonicity, schedule, reservation, attempt, lock, and ancestry
  evidence.
- [x] Add a fixed 128-profile source-then-treatment depth-5 evaluator and one-shot
  runner with no adaptive eligibility, cap, replacement, or outcome-based routing.
- [x] Add public validators for every exact and game trace, aggregate, assessment,
  inspection row, and type-sensitive frozen configuration field.
- [x] Independently review selection blindness, D4 freshness, one-variable
  semantics, state bound, fixed schedule, assessment order, and evidence chain.
- [x] Commit implementation and protocol before computing a frozen schema-v3
  treatment outcome.
- [x] Freeze and commit the outcome-free 64-pair manifest from a clean checkpoint.
- [x] Run and commit paired exact once from the clean manifest commit.
- [x] Run and commit fixed depth-5 once from the committed exact record unless an
  integrity or exact-censor stop condition fires.
- [x] Inspect the frozen sample, report every assessment, and close the plan without
  changing a threshold or extending either prior experiment.

## Pre-outcome checkpoint

Commit `33a735ec0e474de00100bc1adfa67249045097b2` freezes the implementation,
protocol, validators, and 261 passing dependency-free tests. Two independent final
reviews found no unresolved P0–P3 defect. At that commit no
`capture-boundary-v1` manifest, reservation, attempt, exact run, depth-5 run, or
fresh schema-v3 treatment outcome existed. The next permitted mutation is the
one-shot outcome-free manifest chain from a clean descendant checkpoint.

## Frozen components

- exhaustive generator-v2 3×3 vocabulary and canonical D4 orientation;
- strict schema v1 source and schema v3 capture treatment;
- 3×3 board, `max_plies=18`, A `PLACE`/connection goal, and one B runner with a
  reach-edge goal;
- schema-v1 terminal precedence and semantics;
- static, asymmetry, and simplicity gates;
- exact-solver-v1 with a 100,000-state execution cap;
- minimax-v1-depth5 over seeds `0..29` with a cumulative 5,000,000-node cap per
  definition;
- `PlayGates(max_draw_rate=0.50, min_average_plies=4.0,
  max_average_plies_fraction=0.85, dominance_interval_margin=0.05,
  disagreement_threshold=0.15)`;
- sampled direction `None` or exactly `0.5 -> DRAW_OR_BALANCED`, greater than
  `0.5 -> A_WIN`, and less than `0.5 -> B_WIN`;
- play-evaluator-v1 Wilson interval with
  `z=1.959963984540054`, included in the component fingerprint;
- canonical JSON, definition hashes, D4 hashes, action replay, and the capture,
  repetition, replacement-recapture, and strict cycle definitions from Plan 0008.

Weak-random and medium-goal-directed play are not run. Their known policy bias is
not needed for this fixed exact/depth-5 boundary test. Omitting them is a
preregistered evaluation schedule, not an agent change or a reinterpretation of
earlier cheap evidence.

## Evaluated-orbit exclusion ledger

The freezer reads definitions and identities from exactly four pinned sources:

1. generator-v1 development run
   `20260830T154155824053Z-batch-g20260831`, SHA-256
   `b664e133cda42b494d7222735999f0d7b490d9e0108e13743cef8dd20824bb97`;
2. generator-v2 development run
   `20260830T154309225370Z-batch-g20260831`, SHA-256
   `374bfc58030f0acce32a3edd7ff3d10764fb001d130eda4b1da086550b7cb0f5`;
3. generator-v2 held-out run
   `20260830T184008717197Z-strong-g20260901`, SHA-256
   `cdf26f22c93a95f70e413e28257a6afddfaecf21008507a6557e019f2c5357dc`;
4. all 384 cases in landscape-v1 manifest, SHA-256
   `f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1`,
   whose completed all-case raw evidence has SHA-256
   `1edf571bc140a0cd586340eafee2306bccf6ca3a0816f8809b07edc9ef1a9fa4`.

The first three contain 300 definitions, 270 unique definition hashes, 266 unique
D4 hashes overall, and 77 relevant 3×3 input D4 hashes. Of those 77, exactly 55
intersect the generator-v2 vocabulary. Union with the 384 landscape hashes gives
650 declared exclusions, of which exactly 439 intersect the 4,776 generator-v2
vocabulary orbits; the landscape and prior-run D4 sets do not overlap. The
manifest stores ordered source metadata, each extracted D4 list, a domain-separated
union root, and the vocabulary-intersection root.

The evaluated-evidence cutoff is commit `034759a`. Freshness is defined against
the four authenticated sources above at that cutoff, not against an open-ended
future directory scan. A pre-outcome coverage witness must establish that every
generator-v2 schema-v1 source orbit evaluated by a completed run through that
commit is represented in the 439-orbit vocabulary intersection. Later evidence
cannot change this experiment's membership.

At the cutoff there are exactly 16 tracked `experiments/runs/*/run.json` files.
The registry payload is their lexicographically ordered list of exact
`{path, sha256}` objects, encoded as canonical JSON. Its frozen root is:

```text
sha256(b"capture-boundary-v1-evaluated-run-registry-v1\0" + payload)
= e85f0360182efcfcb7abf90fccafba912c440c8923883b1362031006724828a7
```

The coverage audit reconstructs those bytes from the cutoff commit, authenticates
this count and root, projects definitions without using outcomes, and requires the
439-orbit ledger to cover every in-vocabulary generator-v2 schema-v1 source orbit
it finds.

The closed dependency-artifact registry contains exactly these canonical objects,
ordered by path:

```text
{path: experiments/corpora/capture-v1/manifest.json,
 sha256: 6bc466453f60bc4ae2a6401fc76a77eebe4a7ebee82111e53ac4463400588f4f,
 identity_kind: manifest_id, identity: generator-v2-3x3-capture-paired-v1}
{path: experiments/corpora/landscape-v1/manifest.json,
 sha256: f407aefb5fdb8c926db282ff90d2feb1a8666cda3fdbd6925b9f5cc07abd87b1,
 identity_kind: manifest_id, identity: generator-v2-3x3-landscape-v1}
{path: experiments/corpora/stalemate-v1/manifest.json,
 sha256: ed9a9b93ad234f4375ded0e135f5436c82fb127988784a86aa33ab4f776ff176,
 identity_kind: manifest_id, identity: generator-v2-3x3-stalemate-paired-v1}
{path: experiments/corpora/static-v1/corpus.json,
 sha256: 4ad81a4019f072a6f47d88e86f1761c0f55ef792f647d1348d292085496ce208,
 identity_kind: corpus_id, identity: static-v1-2026-08-31}
```

Every dependency reference has exactly `path`, `sha256`, `identity_kind`, and
`identity`. Each coverage record stores both its direct dependencies and its
lexically ordered transitive closure. The static fixture, including the single-play
and single-exact consumers, resolves the static corpus; stalemate and capture
manifests resolve landscape-v1; and every run reference must match the path, ID,
and SHA fields that its authenticated legacy configuration actually records. The
closed registry supplies and authenticates the complete path/ID/SHA identity even
where an older configuration stored only a path. The public validator rebuilds the
registry root from all coverage record paths and SHAs, then rebuilds the full
dependency DAG and both direct and transitive lists.

The dependency closure is closed-world and keyed by exact `experiment_type`:

- `structured-random-generation-screening` and
  `strong-cascade-held-out-generation` are direct carriers; project only each
  candidate's definition and identity;
- `frozen-3x3-exact-outcome-landscape` resolves its authenticated landscape
  manifest and projects all source cases;
- exact audit and calibration resolve the authenticated generator-v2 development
  batch; blind depth 5 resolves the authenticated held-out run; landscape stress
  resolves landscape raw; stalemate paired/stress resolve their paired manifest
  source sides and landscape raw; capture paired/stress resolve their outcome-free
  paired-manifest source sides and landscape raw;
- the frozen static, single-definition play, and single-definition exact fixture
  types are validated as outside the generator-v2 schema-v1 3×3 vocabulary; they
  contribute no orbit.

Each dependency must match the closed registry's path, run/manifest/corpus ID, and
byte SHA before projection, and every corresponding field present in the legacy
run configuration must agree. A reference-only run inherits the recursively
resolved source set and cannot add a hash from result fields. Cycles, an unknown
experiment type, an
unresolved reference, an in-vocabulary embedded definition outside the resolved
set, or any identity mismatch fail the coverage audit. The expected resolved
in-vocabulary union is exactly the same 439 D4 hashes, with zero missing hashes.
For every registry entry, the manifest records its frozen projection kind,
authenticated repository-relative dependency list, ordered projected D4 hashes,
count, and domain-separated root. These per-entry records and their union are
publicly reconstructed; none can read an outcome to decide inclusion.

The coverage witness and exclusion ledger have independent frozen roots. Their
payload is the complete respective object excluding only its own root field:

```text
sha256(b"capture-boundary-v1-coverage-projection-v1\0" + canonical_payload)
= aff92eed1ff9b218431d2a92432597c10b37ddd0445fbea74c497d97f5b89164

sha256(b"capture-boundary-v1-exclusion-ledger-v1\0" + canonical_payload)
= d257fb039ec8bd8c77ca1f955fcc94dc19658d527047983740eb72772eb36889
```

Plan 0008 source/treatment disjointness uses only its outcome-free manifest chain,
never its raw or stress results:

- reservation SHA-256
  `3f67d49fe50e2c6897a689c9c3b9bd8bfbd1154c961a6e49b4608aa7fd7c2cbe`;
- attempt SHA-256
  `5f65911bc875495b81f5a9032c1ea218d7214402eb40f8ac814a54861b197c8f`;
- manifest SHA-256
  `6bc466453f60bc4ae2a6401fc76a77eebe4a7ebee82111e53ac4463400588f4f`;
- lock SHA-256
  `496a87ac1f169d7d6b19c29bf176a7af6f11ddc481578fcdab889b46f79b429f`.

The fixed edge adapter alone may receive full authenticated records. It immediately
projects them into strict definition/identity objects and calls a separate pure
builder whose API cannot accept a run record. Manifest construction and selection
receive only that detached projection; they must not receive exact, sampled,
failure, admission, timing, or other run fields. The raw adapter is not injectable
at the freezer boundary. A poison test against the pure projection changes every
non-definition field and requires identical membership. The filesystem loader
must instead reject any such mutation because its pinned byte SHA no longer
matches. Selected source D4 hashes and their derived schema-v3 treatment D4 hashes
must be disjoint from every Plan-0008 source and treatment hash reconstructed from
the pinned manifest.

## Outcome-free selection

After exclusion, restrict canonical generator-v2 representatives to:

- schema v1, board size three, and `max_plies=18`;
- B exact vector count three or four;
- the same one-runner A-place/B-move family;
- source and derived treatment both passing the frozen static, asymmetry, and
  simplicity gates.

These are all outcome-free computations. The planning census contains 724 unused
orbits before gates and 563 paired-analysis-valid orbits after gates, with no
source/treatment gate disagreement.

Strata are the Cartesian product:

```text
first_player           A / B
goal_axis_relation     ALIGNED / ORTHOGONAL
runner_start_class     CORNER / EDGE_MIDPOINT
vector_count           3 / 4
```

There are 16 strata. The exact eligible counts are frozen below; their sum is 563
and the minimum is 16:

The stratum ID is exactly
`f{A|B}-{aligned|orthogonal}-{corner|edge_midpoint}-p18-v{3|4}`; for example,
`fA-aligned-corner-p18-v3`.

| First | Axis | Start | v3 | v4 |
|---|---|---|---:|---:|
| A | aligned | corner | 37 | 57 |
| A | aligned | edge midpoint | 16 | 29 |
| A | orthogonal | corner | 39 | 56 |
| A | orthogonal | edge midpoint | 18 | 28 |
| B | aligned | corner | 39 | 57 |
| B | aligned | edge midpoint | 19 | 28 |
| B | orthogonal | corner | 38 | 57 |
| B | orthogonal | edge midpoint | 18 | 27 |

Within each stratum, sort by

```text
sha256("capture-boundary-v1:" + source_d4_canonical_hash)
```

and then source D4 hash, selecting the first four without replacement. Strata are
ordered by their exact string IDs in ascending Unicode code-point order, followed
by selection rank. The 64 selected source definitions remain in canonical
mechanical orientation. The manifest records every eligible count and pool root,
selection rank and score, source/treatment DSL and D4 hashes, stratum, pair
fingerprint, exclusion roots, and frozen executable/protocol fingerprints. It
recursively forbids outcome and timing fields.

The implementation and tests pin a domain-separated ordered eligible-pool root and
the ordered 64-source selection fingerprint stated in this plan. The freezer must
recompute both from the full vocabulary and fail its permanent attempt before
writing a manifest if either differs. A builder and validator sharing the same
drift therefore cannot bless a self-consistent but different cohort.

For the pool root, the payload is a list in lexicographic stratum-ID order. Each
entry has exactly `stratum` and `ordered_source_d4_hashes`; `stratum` is the exact
four-field object
`{first_player, goal_axis_relation, runner_start_class, vector_count}` with the
uppercase values shown above, and hashes are lexicographically sorted. The string
ID and constant `max_plies=18` are not in this root payload. With canonical JSON
(`sort_keys=True`, separators `(',', ':')`, UTF-8, no NaN):

```text
sha256(b"capture-boundary-v1-eligible-pools-v1\0" + payload)
= f739887b3f86f2e3652b8e526f1709efc706983329994f46afed4460843c1fcc
```

The selection fingerprint payload is only the ordered list of 64 selected source
D4 hashes in stratum-ID then rank order:

```text
sha256(b"capture-boundary-v1-selected-sources-v1\0" + payload)
= 8df3570000911a0d2c2ee3d052e5863f29fa2a72e64c33ccb7b9b544daa0ee56
```

The freezer records that prior capture outcomes informed this protocol, but it
must not read Plan-0008 raw or stress artifacts to rank, replace, or validate a
candidate.

## One-variable treatment and state bound

Each pair changes only:

```text
schema_version: 1 -> 3
roles.B.action.kind: MOVE -> MOVE_CAPTURE
```

Name, board, setup, goals, vectors, first player, maximum plies, and terminal
semantics are identical. Reverting those two fields must reproduce the source
canonical bytes. An engine-level property test covers every valid common board
state: every source B move has a coordinate-equivalent treatment action; an empty-
destination source `MOVE` and treatment `MOVE_CAPTURE` produce identical next
states after action-kind normalization; and only entries onto A-occupied
destinations are newly legal. Case-level replay validation remains separate.

Use the A-value order `B_WIN < DRAW < A_WIN`. Treatment value must never exceed
source value. A violation is an integrity failure, not an observation.

For both schemas, one B runner has nine possible cells and each other cell is empty
or holds one A seed. Side to move is fixed by first player and ply parity:

```text
9 × 2^8 = 2,304 board arrangements per ply
19 ply layers (0..18)
2,304 × 19 = 43,776 states
```

Schema-v1 reachability is a subset of schema v3. Public validators require
`type(searched_states) is int` and `1 <= searched_states <= 43_776` for source and
treatment; booleans are rejected. The looser execution cap remains 100,000.

Without capture, A can place at most eight seeds around the single B runner. Thus a
schema-v1 source ends naturally by at most ply 15 when A starts and ply 16 when B
starts. Any source `PLY_LIMIT` is an integrity or semantics failure. A schema-v3
treatment `PLY_LIMIT` remains horizon evidence.

## Fixed evaluation schedule

### Stage 1 — Manifest

Commit implementation, protocol, validators, tests, and independent pre-outcome
review before freezing. From a clean commit, the one-shot freezer writes a
reservation, attempt, exclusion ledger, outcome-free manifest, and exact-byte
lock. It calls no solver or play agent. Commit the complete manifest chain before
any treatment outcome.

### Stage 2 — Paired exact

From the committed clean manifest, follow its order exactly:

1. solve all 64 schema-v1 sources;
2. validate and seal the ordered source evidence and digest;
3. solve all 64 schema-v3 treatments;
4. validate every pair, PV, state bound, capture trace, and monotonicity claim;
5. construct and publicly reconstruct the complete aggregate.

The timing-free ordered source and treatment slot digests use domains
`b"capture-boundary-v1-source-exact-slots-v1\0"` and
`b"capture-boundary-v1-treatment-exact-slots-v1\0"`, respectively. Their
canonical-JSON payloads omit only each slot's `elapsed_seconds` field.

No case is routed by a gate, source result, treatment result, or observed capture.
Every PV replays to its recorded terminal result and reason. Timing is descriptive
and excluded from equality. Commit the raw exact reservation, attempt, and run
before depth 5.

An exact state censor occupies its scheduled slot but does not suppress later exact
attempts: finish the fixed 64-source then 64-treatment schedule, recording every
censor in place. The validated exact run is the terminal artifact for that branch,
sets every response, boundary, candidate-shape, and overall assessment to
`INCONCLUSIVE_EXACT_CENSOR`, and freezes an exact-only inspection. Pools requiring
complete paired evidence are marked unavailable or partial and are never
backfilled. Do not create a depth-5 reservation. Integrity failures instead remain
permanent failure sidecars and produce no trusted run.

### Stage 3 — Fixed paired depth 5

The manifest seals this source-then-treatment schedule before outcomes:

```text
64 source definitions × minimax-v1-depth5 × seeds 0..29
64 treatment definitions × minimax-v1-depth5 × seeds 0..29
```

Run all 128 profiles. There is no eligibility filter, adaptive sample, candidate
cap, replacement, or outcome-based order. Each definition receives a fresh
cumulative 5,000,000-node budget. For each definition, construct exactly one
`MinimaxAgent(depth=5, max_total_nodes=5_000_000)`, share that instance between A
and B, reset its budget once before seed 0, and accumulate across seeds `0..29`.
Source and treatment receive separate fresh agents and budgets. A node-censored
profile preserves its completed seed prefix and next incomplete seed, is never
replaced, and does not prevent attempting later fixed-schedule definitions.

After all 64 source profiles, validate every source game, action trace, node
ledger, censor prefix, and slot identity and seal the ordered source evidence
before constructing any treatment agent. Then run and validate all 64 treatment
profiles. The timing-free ordered source and treatment slot digests use domains
`b"capture-boundary-v1-source-depth5-slots-v1\0"` and
`b"capture-boundary-v1-treatment-depth5-slots-v1\0"`; their canonical-JSON
payloads omit only each slot's `elapsed_seconds` field.

Every game stores its complete action sequence, terminal outcome/reason/ply, and
node evidence. Treatment capture is derived from the pre-action destination
occupant; `MOVE_CAPTURE` alone is not a capture. Non-horizon source/treatment
sampled direction is compared independently with its exact A/B result. Treatment
exact terminal reason `PLY_LIMIT` has direction status
`NOT_APPLICABLE_HORIZON`, not a match or mismatch. A sampled game ending at
`PLY_LIMIT` is only a profile draw and shape observation; it never invokes the
exact-horizon branch. Candidate-level and aggregate evidence must reconstruct from
traces.

On node censor during seed `s`, seeds `0..s-1` remain ordinary complete game
records and seed `s` is not a game record. Store an incomplete-attempt object with
the seed, completed action prefix, cumulative nodes before the seed, nodes consumed
by the incomplete attempt, final cumulative nodes, limit, and censor scope. Do not
attempt later seeds for that definition, but do attempt all later fixed-schedule
definitions. Only the completed contiguous seed prefix contributes descriptive
game, capture, terminal, length, and node totals. A censored profile has status
`INCOMPLETE_NODE_CENSOR`; sampled direction, direction match, complete-profile
failure codes, frontier membership, and candidate-shape status are null or not
applicable. Aggregate its partial metrics separately from fully completed profiles.
For every bucket and the top aggregate, store completed-game nodes, incomplete-
attempt nodes, and their expanded-node total separately, and require
`expanded_nodes_total == completed_game_nodes + incomplete_attempt_nodes`.

## Measures and definitions

Report the full 64-case result, each vector-count half, and all eight matched
structural cells `(first_player, goal_axis_relation, runner_start_class)`:

- exact result, terminal reason, source-to-treatment transition, states, and cache
  hits;
- primary response and realized exact capture response;
- normalized PV prefix, capture threat, capture count/ply, repetition,
  replacement-recapture, and strict cycle;
- source and treatment strong A/B/draw counts, direction, duration, dominance,
  nodes, and capture traces;
- every censor, mismatch, failure code, and descriptive timing value.

Every exact group (`ALL`, each vector half, and each structural cell) stores the
normalized-PV common-prefix and PV-length-delta histograms, value-change count,
and capture-threat-without-PV-capture count. Each exact side additionally stores
PV capture-count and first-capture-ply histograms plus repetition, replacement-
recapture, and strict-cycle counts. Depth buckets also store first-capture-ply
histograms. Histogram ply/count keys are canonical decimal strings; the
first-capture histogram always includes the literal key `"null"`, including at
zero, for traces with no capture.

A primary response is a paired-valid source `A_WIN/NO_LEGAL_ACTION` becoming a
non-horizon treatment `B_WIN/GOAL`. A realized response is a paired-valid,
non-horizon treatment PV that captures at least one A seed. Each response is
`SUPPORTED` at `count >= 4` across `strata >= 2`, `NOT_SUPPORTED` at `count == 0`,
and otherwise `INCONCLUSIVE`.

A strong interaction-frontier case has completed non-horizon exact and source/
treatment depth-5 evidence, both sampled directions match exact, the treatment has
no `EXCESSIVE_DRAWS`, `TOO_SHORT`, or `TOO_LONG`, and at least one treatment strong
game executes a capture. Dominance remains visible but does not remove a case from
this mechanical frontier.

A candidate-shaped interaction case is additionally free of `A_DOMINANT` and
`B_DOMINANT` in the treatment profile. Its assessment is `SUPPORTED` at
`count >= 4` across `structural_cells >= 2` and with both treatment exact roles
represented, `NOT_SUPPORTED` at `count == 0`, and otherwise `INCONCLUSIVE`. This
is still only a synthetic qualification, not a candidate or human enjoyment claim.

An A- or B-frontier case is a mechanical interaction-frontier case whose treatment
exact result is respectively `A_WIN` or `B_WIN`. Cell and vector frontier counts
always use treatment exact roles.

Vector count is not a nested action-set intervention: different vector sets at
three and four are different definitions. The result is an equal-stratum
structural association, never an individual-game monotonic causal claim.

## Predeclared assessment order

1. Any source, exclusion, pair, D4, executable, protocol, reservation, attempt,
   lock, ancestry, schedule, action-replay, aggregate, state-bound, source-natural-
   termination, or monotonicity mismatch is an integrity failure and yields no
   trusted assessment.
2. Any exact censor makes every response `INCONCLUSIVE` and stops before creating a
   depth-5 reservation. Audit the solver or 43,776-state proof; do not change the
   cap.
3. After complete exact evidence, run the fixed 128-profile schedule even when a
   treatment exact terminal reason is `PLY_LIMIT`. Later scheduled cases are never
   routed by earlier outcomes or censors.
4. Apply primary and realized response thresholds independently.
5. Any `treatment.exact.terminal_reason == "PLY_LIMIT"` is horizon evidence and
   cannot enter either frontier. If cycling dominance holds, overall is
   `REJECT_CYCLING`. Otherwise any such exact terminal makes boundary, candidate-
   shape, and overall `INCONCLUSIVE` after the full schedule; non-horizon evidence
   remains descriptive. Sampled-game `PLY_LIMIT` terminals do not enter this rule.
6. Among non-horizon cases, any node censor or source/treatment direction mismatch
   makes strong, boundary, candidate-shape, and overall conclusions `INCONCLUSIVE`,
   except that an already established exact `REJECT_CYCLING` retains priority.
7. Let `B3` and `B4` be treatment exact B wins out of the fixed 32 cases at three
   and four vectors. For each of eight structural cells, let `B3_cell` and
   `B4_cell` be B wins out of four.
8. Mechanical boundary is `SUPPORTED_VECTOR_BOUNDARY` only if:

   - both raw responses are supported;
   - `B4 >= 24`, `B3 <= 24`, and `B4 - B3 >= 8`;
   - at least five cells have `B4_cell > B3_cell`;
   - the vector-three A frontier has at least four cases across two cells; and
   - the vector-four B frontier has at least four cases across two cells.

9. Broad B overcorrection is `OVERCORRECTION` when the boundary rule is not met,
   both raw responses are supported, total treatment B wins are at least 48/64,
   both `B3` and `B4` are at least 24, the B frontier has at least eight cases
   across four cells, and the total A frontier has at most three.
10. With complete evidence, capture is `NOT_SUPPORTED_CAPTURE` if primary response,
   realized response, B frontier, or total interaction frontier is zero. The
   three/four-vector lever is separately `NOT_SUPPORTED_VECTOR_BOUNDARY` when it is
   not overcorrection, `B4 <= B3`, and the vector-four B frontier does not exceed
   the vector-three B frontier.
11. Apply the candidate-shape assessment after the mechanical categories.

The composite category and next branch use this frozen priority after integrity
and completeness checks:

| Priority | Condition | Overall | Next branch |
|---:|---|---|---|
| 1 | cycling dominance | `REJECT_CYCLING` | family reassessment |
| 2 | capture response or required frontier is zero | `NOT_SUPPORTED_CAPTURE` | family reassessment |
| 3 | broad B overcorrection | `OVERCORRECTION` | family reassessment |
| 4 | supported vector boundary + supported candidate shape | `SUPPORTED` | separately plan generator v3 |
| 5 | supported vector boundary + zero candidate-shaped cases | `NOT_SUPPORTED` dominance cliff | family reassessment |
| 6 | vector boundary explicitly not supported | `NOT_SUPPORTED_VECTOR_BOUNDARY` | family reassessment |
| 7 | any other complete threshold-adjacent result | `INCONCLUSIVE` | no new cases or rule |

A supported boundary with one to three candidate-shaped cases, cases from only one
exact role, or another candidate-shape threshold shortfall remains `INCONCLUSIVE`.
The capture-response and vector-boundary sub-assessments are preserved separately
even when the composite result is not supported.

Cycling dominance uses the Plan-0008 denominator: among paired-valid source
`A_WIN/NO_LEGAL_ACTION` cases whose treatment exact value changes, it is dominant
only when the count with `treatment.exact.terminal_reason == "PLY_LIMIT"` strictly
exceeds the non-horizon treatment `B_WIN` count. An empty pool or tie is not
dominant.

Any complete `OVERCORRECTION`, `NOT_SUPPORTED_CAPTURE`, `REJECT_CYCLING`,
`NOT_SUPPORTED_VECTOR_BOUNDARY`, or dominance-cliff result rejects unrestricted
capture as the next discovery substrate and triggers a place-versus-move family
reassessment without stacking a rule. Overall `SUPPORTED` authorizes only a
separately planned capture-aware generator-v3 hypothesis; it does not adopt schema
v3 or nominate a game. All other complete but threshold-adjacent results remain
`INCONCLUSIVE` and do not silently add cases.

## Evidence chain and one-shot controls

Use distinct protocol IDs:

- `capture-boundary-v1-manifest-freeze`;
- `capture-boundary-v1-paired-exact`;
- `capture-boundary-v1-fixed-depth5`.

The manifest ID is `capture-boundary-v1-64-pair-manifest` and its canonical corpus
directory is `experiments/corpora/capture-boundary-v1`.

Every stage has its own atomic reservation, immutable attempt, permanent failure
evidence, completed record, and canonical path checks. Manifest provenance pins
the clean pre-outcome commit, protocol plan, executable fingerprints, all exclusion
source bytes, and ledger roots. Exact revalidates the full manifest/upstream chain.
Depth 5 additionally pins and revalidates exact reservation, attempt, and `run.json`
bytes. Run-directory collision writes a separate failure sidecar without modifying
the colliding directory.

The explicit ancestry chain is freezer commit -> exact commit -> depth-5 commit;
each edge is checked with Git ancestry, not inferred merely because both commits
are ancestors of a later `HEAD`. At stage start and immediately before a successful
record, the runner rechecks the active-plan and executable working-tree bytes.
The manifest stage also rechecks every pinned/supporting/Plan-0008 upstream byte,
and exact/depth recheck their complete upstream chains. Each current stage's own
reservation and attempt bytes are sealed before evaluation and rechecked before
completion. A protocol-level or run-level failure sidecar blocks completion, and
a pre-existing protocol-level failure blocks any new reservation even if another
evidence file was removed.

The manifest records the plan path, byte SHA-256, Git blob SHA, and freezer commit.
After manifest freeze, downstream stages validate the historical blob at that
commit rather than comparing mutable working-tree bytes. The plan and fingerprinted
executables remain unedited from manifest freeze through depth-5 completion; DoD
checkboxes and outcome sections are updated only after the full evidence chain.

Frozen configurations, schedules, exact keys, seeds, thresholds, agents, depths,
node/state caps, component versions, and aggregate maps use type-sensitive
canonical JSON comparison so `true` cannot equal `1`. A failed protocol ID is
never rerun. The public one-shot runners accept no injectable builder, evaluator,
or validator callable: they invoke the fingerprinted selection, exact, depth-5,
and public-validation implementations by their fixed module symbols.

## Frozen inspection

The successful final artifact freezes:

- every censor, treatment exact `PLY_LIMIT`, direction mismatch, A-frontier case,
  and candidate-shaped case;
- eight forced-result changes and eight forced-result-unchanged controls per vector
  count, ordered by separate domain-separated treatment-hash scores;
- the lowest-score selected pair in each of the 16 `structural cell × vector`
  strata.

Reasons may overlap. A node-censored depth-5 pair is included even when its exact
evidence is complete. Store every pool size and shortfall. Inspection cannot change
membership, an outcome, threshold, category, or branch.

An outcome change means exactly
`source.exact.forced_result != treatment.exact.forced_result`; terminal-reason-only
changes are controls. Any integrity failure is stored in the permanent stage
failure sidecar and closeout audit rather than requiring a successful final
artifact.

For each vector count separately, forced-result changes are ordered by

```text
sha256(b"capture-boundary-v1-inspection-change-v1\0"
       + treatment_d4_canonical_hash.encode("ascii"))
```

and unchanged controls use domain
`b"capture-boundary-v1-inspection-control-v1\0"`. Ties break by treatment D4 hash
and then `pair_id`. Each quota selects `min(8, pool_size)` and records
`max(0, 8 - pool_size)` shortfall; there is no borrowing or replacement across
pools or vector counts. The per-stratum floor case is the manifest pair with
`selection_rank == 0`, meaning the lowest original source-selection score, not a
new inspection score.

The inspection is a union keyed by `pair_id`, emitted in manifest order. Inclusion
reasons use the frozen enum order `EXACT_CENSOR`, `NODE_CENSOR`, `EXACT_HORIZON`,
`DIRECTION_MISMATCH`, `A_FRONTIER`, `CANDIDATE_SHAPED`,
`OUTCOME_CHANGE_SAMPLE`, `OUTCOME_UNCHANGED_CONTROL`, `STRATUM_FLOOR`. Overlap
creates one row with multiple reasons. Every pool records its size and shortfall;
a shortfall never fails the run or changes another quota.

## Outcome

The outcome-free manifest froze 64 pairs across all 16 registered strata from the
clean checkpoint and reproduced the declared 724 fresh, 563 paired-valid census.
Paired exact completed all 128 source/treatment slots without censoring or horizon
results. Source A/B was 49/15 and treatment A/B was 6/58, with 43 A-to-B changes.
Primary response was `SUPPORTED` at 26 cases across 15 strata, and realized
response was `SUPPORTED` at 32 cases across 14 strata.

Fixed depth 5 completed all 128 profiles and 3,840 games without node censoring or
direction mismatch. All 64 treatment profiles were 30–0 in their exact direction.
The mechanical interaction frontier contained 52 cases, with exact A/B = 6/46,
but candidate-shaped interaction contained zero cases.

The proposed vector boundary did not reproduce. Treatment outcomes were A/B =
3/29 at both v3 and v4, so `B4 - B3 == 0`; only one of eight cells increased its
B-win count. The v3 A frontier had three cases across two cells and the v4 B
frontier had 23 across eight. The frozen assessment is
`NOT_SUPPORTED_VECTOR_BOUNDARY`, not `OVERCORRECTION` and not a dominance cliff.
Its next branch is `FAMILY_REASSESSMENT`.

The manifest, exact record, and depth record were archived at `b52fbd4`,
`ec1492b`, and `1145de2`, respectively. A post-commit public reconstruction and an
independent post-outcome audit matched the complete evidence chain and found no
P0–P3 defect.

## Interpretation

Capture is a real non-horizon counterplay primitive, but B vector count is not a
usable calibration lever in this family. The fresh three-vector half was already
as B-favored as the four-vector half, directly contradicting the prior-informed
separator. The six exact A cases do not establish within-game balance because
strong play was uniformly 30–0 for A; the 58 B cases were uniformly 30–0 for B.

The experiment therefore resolves Plan 0008's formal uncertainty without
rescuing capture. There is no candidate, no capture-aware generator hypothesis,
and no justification for adding a second exception. The useful remaining question
is whether the base place-versus-move family has a simpler setup-level adjustment
with enough information value to test, or should be left for a different family.

## Decision

Close as `NOT_SUPPORTED_VECTOR_BOUNDARY` and follow `FAMILY_REASSESSMENT`. Reject
unrestricted capture as the next discovery substrate. Do not run Plan 0008's 56
unselected cases, extend this replication, retune the registered thresholds, stack
stalemate draw or another rule on capture, or generate toward schema v3.

Perform the family reassessment before any new action primitive. Prefer an existing
DSL setup change over a new learned rule when it can answer the viability question
with a bounded one-variable test.

Result report:
[`../../../experiments/reports/0009-fresh-capture-vector-boundary-replication-result.md`](../../../experiments/reports/0009-fresh-capture-vector-boundary-replication-result.md).
