> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Decisions

Append-only record. Corrections add a new entry rather than rewriting history.

## D-001 — 2026-08-31 — Dependency-free Python foundation

- **Decision:** Use Python 3.9 standard-library code and `unittest` for the first
  vertical slice, with a `src/` package layout.
- **Reason:** Python is available on the host; avoiding bootstrap dependencies
  makes validation and replay immediately reproducible.
- **Alternatives:** TypeScript; Python plus Pydantic/Pytest.
- **Reversibility:** High. Dependencies can be added behind existing contracts.
- **Evidence:** Host inspection found Python 3.9.6 and no pytest, Ruff, or mypy.
- **Reconsider when:** Static typing or experiment scale produces recurring defects
  that a focused dependency demonstrably prevents.

## D-002 — 2026-08-31 — Minimal v1 primitive vocabulary

- **Decision:** Begin with `PLACE`, one-step vector `MOVE`, `CONNECT_EDGES`, and
  `REACH_EDGE`; all other movement, capture, and board mechanics are excluded.
- **Reason:** This is the smallest vocabulary that expresses the initial asymmetric
  place-versus-move family and two different goal experiences.
- **Alternatives:** A generic rule AST; capture and push in v1; one shared goal.
- **Reversibility:** Medium. New versioned primitives can be added without changing
  v1 semantics.
- **Evidence:** Architectural analysis of the first technical target; no game-quality
  claim has yet been made.
- **Reconsider when:** Frozen-corpus experiments show this family cannot produce
  qualifying candidates or a missing primitive blocks a high-information test.

## D-003 — 2026-08-31 — Fixed terminal semantics in schema v1

- **Decision:** Goal-after-own-action, next-player-stuck loss, and a required ply
  cap are schema semantics rather than configurable rule clauses.
- **Reason:** This guarantees finiteness and avoids spending rule complexity on
  policies that are not yet experimental variables.
- **Alternatives:** Configurable stalemate and simultaneous-goal policies.
- **Reversibility:** Medium through a future schema version.
- **Evidence:** The initial family needs a deterministic total transition contract.
- **Reconsider when:** A promising candidate requires a different terminal policy.

## D-004 — 2026-08-31 — Freeze the initial static corpus and complexity gates

- **Decision:** Preserve corpus `static-v1-2026-08-31` and the v1 default complexity
  limits as the baseline for subsequent evaluator work.
- **Reason:** They were declared before their first run and matched exactly; changing
  them silently would destroy the comparison point.
- **Alternatives:** Continue adjusting cases and thresholds during implementation.
- **Reversibility:** High through a new versioned corpus/evaluator, not by overwrite.
- **Evidence:** Run `20260830T153256441950Z-static-4ad81a40` matched 7/7 cases.
- **Reconsider when:** A documented false classification is demonstrated; preserve
  v1 and create a successor with the correction.

## D-005 — 2026-08-31 — Advance exact solving for tractable candidates

- **Decision:** Use full-width memoized minimax now for 3×3 diagnostic finalists,
  earlier than the provisional solver-diversity phase.
- **Reason:** Two sampled profiles reversed role advantage; exact resolution had
  higher information value than tuning either heuristic, and the state space proved
  small.
- **Alternatives:** Add search depth gradually; tune goal-progress weights; average
  the sampled profiles.
- **Reversibility:** High. Exact solving remains a late cascade stage and can be
  limited by measured state/time budgets as boards grow.
- **Evidence:** Crossing Seeds solved after 1,314 states as a forced A win.
- **Reconsider when:** Search cost exceeds the batch budget or state representation
  requires proven symmetry/transposition improvements.

## D-006 — 2026-08-31 — Promote depth-5 minimax only as a late-stage profile

- **Decision:** Add minimax-v1-depth5 after cheap screens; do not replace or average
  away weak/medium profiles, and continue exact checks for tractable cases.
- **Reason:** It matched 20/20 frozen exact directions, but its calibration cost was
  materially higher and the corpus is small.
- **Alternatives:** Depth 3 (16/20); goal-directed only (12/20); depth 5 on every
  generated game; replace sampled evaluation with exact solving.
- **Reversibility:** High; admission and budget policy remain versioned evaluator
  configuration.
- **Evidence:** Calibration runs at depth 3 and depth 5 on exact-v1.
- **Reconsider when:** Held-out accuracy falls, compute dominates the cascade, or a
  different search/leaf family achieves comparable evidence more cheaply.

## D-007 — 2026-08-31 — Freeze cascade-v2 before held-out generation

- **Decision:** Admit non-short candidates when weak random draws are at least 50%
  or no cheap dominance code exists. Independently exact-audit every cheap-play
  3×3 case; apply depth 5 to admitted 4×4 cases and exact 3×3 draws; defer 5×5.
  After primary statuses are sealed, blindly test depth 5 on all exact-completed
  held-out 3×3 cases; audit results cannot rescue a non-admitted candidate.
- **Reason:** On exact-v1 this rule retained 2/2 draws while admitting 25/57 cases
  and only 1/18 forced results. Exact auditing all twenty 3×3 cases took about 1.12
  seconds versus 28.89 seconds for their depth-5 calibration and avoids verification
  bias.
- **Alternatives:** Wilson-overlap admission (missed both draws); disagreement-only
  admission (missed one); depth 5 before exact on every 3×3 case; unbounded 5×5.
- **Reversibility:** High through a new cascade version and untouched generator seed.
- **Evidence:** Frozen generator-v2 batch and exact-v1 audit; no held-out seed was
  inspected while making this decision.
- **Reconsider when:** Held-out draw recall fails, over half of cheap cases are
  admitted, deterministic budgets censor results, or held-out evaluator accuracy
  falls below its predeclared threshold.

## D-008 — 2026-08-31 — Deterministic search budgets yield unknowns

- **Decision:** Bound depth-5 work by expanded nodes per candidate and exact work by
  searched states. Exceeding either produces `DEFERRED_BUDGET`, never a rejection.
- **Reason:** Board size and wall time do not provide reproducible compute bounds;
  observed 5×5 depth-5 games varied from seconds to more than twelve seconds each.
- **Alternatives:** Wall-clock timeout; board size alone; unbounded searches.
- **Reversibility:** High through versioned numeric budgets.
- **Evidence:** Development timing probes and code review before held-out generation.
- **Reconsider when:** A platform-independent work counter or substantially faster
  transposition architecture changes the cost model.

## D-009 — 2026-08-31 — Held-out attempts are one-shot and fail closed

- **Decision:** Before seed `20260901` is generated, require the exact preregistered
  configuration, development run ID/SHA/definition fingerprint, canonical output
  directory, and a clean commit. Write `attempt.json` first and refuse any later
  attempt when matching evidence exists; preserve exceptions in `failure.json`.
- **Reason:** A crash after partial inspection must spend the held-out seed rather
  than disappear and invite an undisclosed rerun.
- **Alternatives:** Write only successful results; rely on manual command review;
  permit reruns after failures.
- **Reversibility:** High for future protocol IDs, but this seed becomes immutable
  once its attempt record exists.
- **Evidence:** Independent pre-run review found that the original runner created
  its directory only after all computation, leaving no evidence on failure.
- **Reconsider when:** A transactionally equivalent experiment registry replaces
  local attempt/result/failure records.

## D-010 — 2026-08-31 — Preserve cascade-v2 as a failed discovery policy

- **Decision:** Do not retune cascade-v2 on its held-out result and do not run depth
  5 on its thirteen deferred 5×5 cases. Future cascade designs must distinguish
  candidate eligibility from evaluator-audit routing and must not route strong
  compute to a candidate that later evidence cannot rescue.
- **Reason:** All 26 admissions were caused by ply-limit-heavy weak random play, and
  all 26 already had a retained cheap shape failure. The 4×4 searches completed
  within budget but could not change candidate status; the 5×5 searches would have
  the same zero discovery value under the frozen finalizer.
- **Alternatives:** Remove cheap shape failures after strong play; raise 5×5 budgets;
  tune the draw threshold against seed `20260901`; immediately replicate on seed
  `20260902`.
- **Reversibility:** High through a preregistered cascade-v3. Cascade-v2 and its
  immutable runs remain unchanged evidence.
- **Evidence:** Primary run `20260830T184008717197Z-strong-g20260901` and report
  `experiments/reports/0005-cascade-v2-heldout-result.md`.
- **Reconsider when:** A new final-gate semantics is justified independently of
  this held-out result, or a diagnostic question makes a non-rescuable case useful.

## D-011 — 2026-08-31 — Map the 3×3 vocabulary before another random batch

- **Decision:** Keep seed `20260902` untouched. Instead, take an outcome-independent
  384-case sample from an exhaustive census of generator-v2's 3×3 vocabulary,
  remove known D4 symmetry orbits and the deterministically too-complex eight-vector
  class, and exact-solve every selected case independent of cheap play.
- **Reason:** The held-out batch supplied no exact draws, while another comparable
  batch would likely repeat that information gap. Exact 3×3 solving has been cheap,
  and balanced structural coverage can locate hypotheses without changing generator
  or evaluator semantics.
- **Alternatives:** Run seed `20260902`; increase 5×5 depth-5 compute; select cases
  by cheap draw rate; immediately add a mechanic; enumerate and solve all 4,776 D4
  orbits.
- **Reversibility:** High. The manifest is a new frozen corpus, not a modification
  of generator-v2 or existing runs.
- **Evidence:** Report 0005; a result-blind census counted 36,720 definitions and
  4,776 D4 orbits, with at least 19 eligible post-exclusion orbits in every proposed
  stratum.
- **Reconsider when:** A stratum cannot meet its quota, exact-state censoring is too
  high to interpret the sample, or symmetry tests expose a non-isomorphism.

## D-012 — 2026-08-31 — Keep DSL identity separate from D4 orbit identity

- **Decision:** Preserve the canonical DSL hash as the exact stored-definition
  identity and add a versioned, name-independent D4 mechanical hash only for
  symmetry grouping and outcome-blind sampling.
- **Reason:** Rotations and reflections are game-tree isomorphisms for the current
  square-board mechanics, but collapsing them in the DSL hash would erase the exact
  authored orientation and silently change existing fixture and run identities.
- **Alternatives:** Redefine the DSL hash modulo symmetry; deduplicate only exact
  hashes; normalize coordinates in the generator.
- **Reversibility:** High. D4 identity is supplemental and versioned; DSL v1 remains
  unchanged.
- **Evidence:** Transform-table, group-composition, hash-domain, canonicalization,
  and exact-outcome invariance regression tests; exhaustive census yields 4,776 D4
  orbits from 36,720 definitions.
- **Reconsider when:** A mechanic depends on absolute orientation, a non-square
  board is introduced, or role-swapping equivalence becomes an explicit hypothesis.

## D-013 — 2026-08-31 — Separate landscape selection, raw labels, and draw stress

- **Decision:** Commit three immutable stages: an outcome-free manifest and byte
  lock, a raw all-case exact record, then adaptive exact-draw stress. Pin source-code
  fingerprints across all stages, atomically reserve one-shot protocol IDs, and
  fail closed on any attempt/provenance/lock/source mismatch.
- **Reason:** Combining selection and outcomes would make it impossible to prove
  that exact or cheap results did not influence replacement, while running stress
  before sealing raw labels would make its adaptive sample unverifiable.
- **Alternatives:** One combined run; manual manifest review without a lock; allow
  failed or concurrent reruns; trust aggregate fields without candidate-level
  reconstruction.
- **Reversibility:** High for a new protocol ID. Evidence created under this
  protocol remains immutable and cannot be retried.
- **Evidence:** Independent pre-run reviews identified circular provenance,
  incomplete census pins, malformed-exact fallthrough, and adaptive-input trust;
  the corrected runners cross-check all 384 manifest identities, structural gates,
  cheap summaries, exact aggregates, source commits, and sibling attempts.
- **Reconsider when:** A transactional experiment registry provides equivalent or
  stronger reservation, attestation, and immutable artifact guarantees.

## D-014 — 2026-08-31 — Test stalemate draw before another generator change

- **Decision:** Preserve DSL v1, generator v2, and seed `20260902`. Before adding a
  movement primitive or changing generation, test one schema-v2 counterfactual in
  which next-player immobility is a draw. Use every 18-ply case from the frozen
  outcome-free landscape manifest as a paired corpus and change no other semantic
  or evaluator variable.
- **Reason:** The landscape solved 384/384 cases, but all 13 draws ended at a binding
  ply cap and all failed strong play shape. The 18-ply subset has a provably
  nonbinding horizon and 68 baseline optimal lines ending in no-legal-action wins,
  so it isolates whether a natural stalemate policy can create non-horizon balance.
- **Alternatives:** Reweight generator-v2; run seed `20260902`; optimize for exact
  ply-cap draws; extend only the 13 observed horizons; add capture at the same time.
- **Reversibility:** High. Schema v1 and all frozen evidence remain unchanged;
  schema v2 is only a diagnostic treatment until independently validated.
- **Evidence:** Runs `20260830T200230881318Z-landscape-f407aefb` and
  `20260830T200513661140Z-draw-stress-1edf571b`; report
  `experiments/reports/0006-three-by-three-outcome-landscape-result.md`.
- **Reconsider when:** Treatment outcomes are censored, the nonbinding-horizon proof
  fails, all stalemate draws are trivial or shape-invalid, or a separate validation
  contradicts the discovery result.

## D-015 — 2026-08-31 — Reject stalemate draw as the next discovery direction

- **Decision:** Preserve schema v2 as a negative diagnostic result and do not adopt
  or generate toward it. Test one schema-v3 B-side capture-on-entry primitive under
  schema-v1 terminal semantics before changing generator weights or combining
  mechanics.
- **Reason:** The stalemate treatment created 20 exact draws, but 18 were static
  rejects and the two static-valid cases became 30/30 short or draw-heavy
  stalemates at depth 5. A terminal relabel did not give B a way to contest A's
  placed barriers.
- **Alternatives:** Lower the four-case semantic threshold; optimize sparse-vector
  strata; combine stalemate draw with capture; run seed `20260902`; add adjacent
  remove, push, or swap instead.
- **Reversibility:** High. Schema v1, schema v2, generator v2, and every immutable
  run remain unchanged; capture is a separately versioned diagnostic treatment.
- **Evidence:** Raw run `20260830T214033891685Z-stalemate-ed9a9b93`, stress run
  `20260830T214159802995Z-stalemate-stress-239ad79d`, and report 0007.
- **Reconsider when:** Capture-on-entry has no material non-horizon effect, merely
  overcorrects toward B, or produces mostly finite-horizon cycling; then reassess
  the place-versus-move family before stacking primitives.

## D-016 — 2026-08-31 — Close capture discovery inconclusive without extending its cap

- **Decision:** Preserve Plan 0008 as `INCONCLUSIVE`, do not evaluate its 56
  unselected stress-eligible cases, and do not promote its descriptive
  `ROLE_DIVERSE` sample to a formal category. Test the observed three-versus-four
  vector boundary only through a new, disjoint, outcome-blind fixed-membership
  replication in which every selected case receives the strong profile.
- **Reason:** Capture produced 61 exact A-to-B value changes and met both raw
  response thresholds, but 88 cases were stress-eligible and the preregistered
  32-case cap censored frontier completeness. The selected 32 were descriptively
  three A wins and 29 B wins, and every one was 30–0 role-dominant; neither a
  validation branch nor a one-sided rejection branch can be inferred under the
  frozen rules.
- **Alternatives:** Raise the cap after outcomes are known; treat the selected
  frontier as formally role-diverse; reject capture as one-sided B; adopt capture
  and change generator weights; abandon the family immediately.
- **Reversibility:** High. The schema-v3 primitive and immutable evidence remain
  diagnostic only; a new validation protocol changes neither Plan 0008 nor the
  existing generator.
- **Evidence:** Runs `20260830T225920216640Z-capture-6bc46645` and
  `20260830T230308952280Z-capture-stress-e4fc6e97`; report 0008.
- **Reconsider when:** A disjoint fixed-membership replication either reproduces
  capture-engaged structures for both roles without universal dominance or shows
  that the boundary is consistently a B overcorrection.

## D-017 — 2026-08-31 — Reject unrestricted capture after the fresh boundary fails

- **Decision:** Close Plan 0009 as `NOT_SUPPORTED_VECTOR_BOUNDARY`, reject
  unrestricted capture as the next discovery substrate, and enter a
  place-versus-move family reassessment. Do not build a capture-aware generator,
  extend either capture experiment, or stack another rule on schema v3.
- **Reason:** The fresh outcome-blind sample completed without censoring, but
  treatment exact A/B was 3/29 at both three and four vectors. The B-win increase
  was zero, only one of eight cells improved, and all 64 treatment depth-5 profiles
  were 30–0 role-dominant. Candidate-shaped interaction was empty.
- **Alternatives:** Reclassify the result as broad overcorrection; call the two
  vector halves a dominance cliff; tune capture by quota or direction; generate
  toward the six exact A cases; run Plan 0008's 56 unselected cases.
- **Reversibility:** High for a separately versioned future hypothesis. Schema v3
  and its immutable evidence remain available, but they are not an authorized
  discovery substrate under current evidence.
- **Evidence:** Runs `20260831T012026857459Z-capture-boundary-exact-e1b0f6a7` and
  `20260831T012251133134Z-capture-boundary-depth5-cbf2ccc3`; report 0009; independent
  post-outcome audit with no P0–P3 finding.
- **Reconsider when:** A new outcome-blind experiment justified independently of
  these outcomes demonstrates non-dominant capture play, not merely a different
  across-definition role mix.

## D-018 — 2026-08-31 — Test two runners before adding another action primitive

- **Decision:** The next family-viability experiment will preserve schema v1 and
  add one identical B runner at the other corner of B's opposite starting edge.
  Use fresh corner-start source orbits, fixed outcome-blind membership, and change
  no action, goal, terminal rule, agent, gate, or board parameter.
- **Reason:** The engine and DSL already express multiple identical movers. The
  setup change adds alternate routes and spatial interference without deleting or
  relocating A seeds and without teaching PUSH, REMOVE, SWAP, JUMP, or a capture
  exception. Its 3×3 state space has the nonbinding bound
  `15 × C(9,2) × 2^7 = 69,120`, retaining exact ground truth under the existing
  100,000-state execution cap.
- **Alternatives:** Retire the family immediately; move to 4×4 without exact
  ground truth; add PUSH, adjacent REMOVE, SWAP, or JUMP; limit capture by quota or
  direction; change generator weights or agents.
- **Reversibility:** High. The treatment is an ordinary schema-v1 definition and
  existing one-runner evidence remains unchanged. A negative result can close this
  setup branch without a DSL migration.
- **Evidence:** Plans 0006–0009 isolate one-runner containment, failed stalemate
  relabeling, unrestricted-capture overstrength, and the nonreplicating vector
  boundary. An outcome-free planning census found 477 fresh, paired-valid,
  treatment-unique pairs with at least 19 in each proposed stratum.
- **Reconsider when:** The public census cannot reproduce those floors, D4
  equivariance or the natural-termination/state proof fails, or the treatment
  requires a new semantic exception.

## D-019 — 2026-08-31 — Reject two-runner setup and calibrate 4×4 before retirement

- **Decision:** Close Plan 0010 as `NOT_SUPPORTED_TWO_RUNNER_SETUP`. Do not build a
  two-runner generator, add another runner, extend the frozen sample, relax its
  candidate threshold, or stack capture or stalemate semantics on the setup.
  Before retiring the narrow place-versus-move family or adding a new action
  primitive, run one bounded 4×4 evaluator-calibration plan whose membership is
  outcome-blind and whose claims are limited to evaluator reliability.
- **Reason:** The second runner was mechanically active in exact and sampled
  traces, but exact value changed in only 1/64 pairs. All 46 complete, engaged
  strong-frontier cases were 30–0 role-dominant, leaving candidate shape empty.
  A 4×4 lane remains within the founding search universe and can test whether the
  current strong evaluator has useful discrimination outside the exactly solved
  3×3 domain, but loss of general exact ground truth prevents treating it directly
  as a family-viability experiment.
- **Alternatives:** Retire the family immediately; add PUSH, REMOVE, SWAP, or JUMP;
  build a two-runner generator; add a third runner; combine prior rejected
  treatments; continue random 3×3 generation.
- **Reversibility:** High. Plan 0010 and all earlier artifacts remain immutable;
  the calibration lane changes neither the DSL nor generator and may terminate
  before a production corpus if it cannot define trustworthy fixed-cost evidence.
- **Evidence:** Exact run
  `20260831T042721207815Z-two-runner-exact-3b7757ad`, depth run
  `20260831T043600138223Z-two-runner-depth5-2353bfb8`, report 0010, and independent
  post-outcome audits with no P0–P3 finding.
- **Reconsider when:** A bounded pre-outcome design cannot obtain exact anchors or
  meaningful independent-agent agreement at 4×4, or its projected cost would
  displace a simpler family pivot; then retire the family without running the
  calibration experiment.

## D-020 — 2026-08-31 — Supersede the unrun 4×4 calibration and establish broad-family feasibility first

- **Decision:** Close Plan 0011 as `SUPERSEDED_PRE_OUTCOME`, preserving its three
  reviewed pure slices and 367-test checkpoint without inferring an evaluator
  result. Make Plan 0012 the sole active plan: establish a bounded semantic
  `FamilySignature`, define strict occupancy schema v4, validate replay telemetry,
  and run an outcome-free feasibility census for six provisional 3×3 cells beyond
  `PLACE` versus `MOVE`. Freeze no final registry or gameplay atlas until the new
  semantics and finite domains are known; gameplay requires a later plan.
- **Reason:** Plans 0006–0010 repeatedly varied terminals, capture permission,
  mobility bands, runner count, and board parameters around one topology, yet
  produced no non-dominant candidate-shaped evidence. Plan 0011 could calibrate an
  evaluator only within that lane. The broader family question now reduces more
  decision uncertainty, and no Plan-0011 production membership, reservation, or
  outcome was spent.
- **Alternatives:** Complete the Plan-0011 one-shot 4×4 calibration; continue
  tuning the place-versus-move family; adopt a Builder–Assembler or another
  `PLACE`-centered proposal; introduce an arbitrary rule AST or many interacting
  mechanics at once; begin evolutionary search before identifying a viable
  family.
- **Reversibility:** High. Plan 0011's roots, selector, schedules, thresholds,
  seeds, caps, implementation, and tests remain preserved at `96fa5b7`, and its
  unspent calibration can be resumed under a new decision if a family-independent
  question justifies it. Schema-v1/v2/v3 bytes, behavior, fixtures, and historical
  evidence remain frozen.
- **Evidence:** Plans 0007–0010 and their immutable runs; the Plan-0011 pure
  census, exact, and depth checkpoints; all 367 dependency-free tests passing at
  `96fa5b7`; and the absence of every Plan-0011 production manifest, exact label,
  sampled profile, run, reservation, attempt, failure, lock, and outcome artifact.
- **Reconsider when:** The family signature cannot remain finite and callback-free,
  schema-v4 isolation cannot preserve prior bytes and behavior, the synthetic
  benchmark cannot distinguish its declared counterexamples, or no provisional
  cell admits a finite nontrivial setup domain before outcomes.

## D-021 — 2026-08-31 — Separate family identity from search identity and define v4 before telemetry

- **Decision:** Keep stable family IDs outside the name-free semantic signature;
  put setup and parameter domains in a later versioned search envelope; and add a
  full definition-derivation witness only after a schema-v4 compiler exists. Treat
  the six documented cells as provisional until an outcome-free feasibility
  census. Define schema-v4 cross-role goal precedence and implement its actions
  before freezing the full telemetry benchmark. Plan 0012 ends before gameplay.
- **Reason:** The first draft conflated a ludeme family with one generator domain,
  required a v4 derivation before v4 existed, and scheduled synthetic v4 traces
  before their actions existed. `PUSH` and `SWAP` can also satisfy the opponent's
  state goal, while the old actor-only terminal rule was defined but unsuitable
  for those state-goal families. Equal case counts would provide only nominal
  exposure, not equal solving difficulty.
- **Alternatives:** Put IDs and all generator domains in one family hash; freeze
  the six-cell registry and 144-case quota immediately; build a claim-only
  derivation record before a compiler; retain actor-only goals for v4; or treat a
  hand-authored benchmark as threshold calibration.
- **Reversibility:** High before any v4 definition, registry root, corpus, or
  outcome exists. Later evidence artifacts will pin all applicable identities and
  versions independently.
- **Evidence:** Independent pre-implementation reviews of the Plan-0012 draft and
  the initial family/telemetry scaffolds; existing engine terminal ordering; and
  the absence of any Plan-0012 production artifact or gameplay call.
- **Reconsider when:** A concrete derivation cannot be reconstructed across the
  separated layers, cross-role terminal semantics create unavoidable complexity,
  or the outcome-free census shows that a different identity boundary is needed.

## D-022 — 2026-08-31 — Freeze schema-v4 terminal order and add PUSH first

- **Decision:** Freeze schema v4's initial order as first-player goal, second-player
  goal, then first-player immobility; freeze its post-action order as actor goal,
  opponent goal, ply cap, then next-player immobility. Implement `PUSH` as the
  first atomic v4 action, with ordinary empty-cell relocation plus a one-piece,
  one-cell conditional displacement. At this checkpoint v4 requires at least one
  PUSH role; broaden that admission only through later compatible action slices.
- **Reason:** PUSH is the smallest proposed action that can directly grant an
  opponent's reach or connection goal and therefore exercises the new terminal
  contract end to end. A strict incremental checkpoint isolates parser, identity,
  prose, D4, simplicity, action, transition, and replay changes before adding a
  second new primitive.
- **Alternatives:** Add all v4 actions at once; retain actor-only goal checks; let
  the ply cap or immobility override an opponent goal; encode the pushed landing
  cell in a larger recorded action; or permit old-only actions under v4 before a
  new action is present.
- **Reversibility:** High for the remaining unimplemented vocabulary. Existing
  valid v4 PUSH definitions and their bytes are fixed, while a later slice can
  compatibly admit another v4-only action. Schemas v1–v3 remain byte- and
  behavior-identical.
- **Evidence:** Canonical/hash/prose goldens for schemas v1–v4; direct-construction
  and forged-object guards; an exhaustive 59,049-assignment local PUSH legality
  check; legal and illegal transitions; initial, simultaneous, opponent-goal,
  horizon, and immobility precedence tests; D4 and simplicity integration tests;
  and no Plan-0012 solver, agent, or gameplay experiment.
- **Reconsider when:** A later atomic action cannot obey the same state-goal
  ordering, PUSH cannot retain one-step bounded semantics, or an independent
  backward-compatibility review finds prior-schema drift.

## D-023 — 2026-08-31 — Add SWAP as the second schema-v4 atomic action

- **Decision:** Add `SWAP` as ordinary adjacent relocation into an empty cell or
  exchange with one adjacent opponent while preserving both owners and piece
  kinds. Reject friendly, ranged, multi-piece, and undeclared-vector swaps. Broaden
  v4 admission only from at least one `PUSH` role to at least one `PUSH` or `SWAP`
  role; preserve the terminal contract and all existing PUSH and schema-v1/v2/v3
  identities and behavior.
- **Reason:** Exchange is a distinct provisional interaction primitive that needs
  no landing cell, removal, callback, or larger recorded action. Adding it alone
  isolates its parser, identity, D4, simplicity, legality, transition, and replay
  effects before HOP or any ownership-changing action exists.
- **Alternatives:** Add all remaining v4 primitives together; make swapping
  compulsory instead of retaining ordinary movement; permit friendly or ranged
  swaps; record the target or an effect descriptor in the action; or admit
  old-only definitions under v4.
- **Reversibility:** High for the remaining vocabulary. Existing valid PUSH and
  SWAP definitions and their bytes are fixed; later compatible slices can broaden
  v4 admission without changing them.
- **Evidence:** Fixed SWAP DSL hash
  `c8dba41bb2e97e5fcc5dd119a415da2ee74b68e196f38c70d2aada292de73ba2`
  and D4 hash
  `aae4af10c105a9e498277a0df32024f3bdbd4baf91ef95368ba2d9985030c4b0`;
  exhaustive 59,049-assignment local legality agreement; zero schema-v1/v2/v3
  differences over 3,600 states and 7,804 transitions; zero PUSH differences over
  1,200 states and 835 transitions; zero SWAP D4 differences over 2,368 cases;
  focused regressions passing 99/99; and no Plan-0012 solver, agent, gameplay
  experiment, or outcome.
- **Reconsider when:** HOP or a later atomic action cannot remain compatible with
  the PUSH-or-SWAP admission boundary, exchange requires hidden effect state, or
  an independent backward-compatibility review finds prior-schema or PUSH drift.

## D-024 — 2026-09-01 — Add HOP with the final landing as its recorded destination

- **Decision:** Add `HOP` as ordinary adjacent relocation into an empty cell or a
  jump over exactly one adjacent occupied piece to the empty in-bounds cell one
  more step along the same declared vector. The jumped piece may be friendly or
  opposing and retains owner, kind, and position. Record the actor's final landing
  as `to`; derive the intermediate cell from the definition and state. Reject an
  empty intermediate, occupied or off-board landing, undeclared direction,
  longer move, and chain. Broaden v4 admission only to at least one `PUSH`,
  `SWAP`, or `HOP` role.
- **Reason:** Occupancy-dependent evasion is distinct from displacement and
  exchange, but needs no new action field or state effect beyond actor relocation.
  A final-landing `to` keeps replay complete and unambiguous while the one-step
  DSL vector remains the authoritative direction.
- **Alternatives:** Record the jumped cell rather than the landing; add an `over`
  or `landing` field; allow only opposing intermediates; require every move to be
  a hop; permit chains or direction changes; or add HOP together with the
  ownership-changing actions.
- **Reversibility:** High for the remaining vocabulary. Existing valid PUSH,
  SWAP, and HOP definitions and their bytes are fixed; later compatible slices
  can broaden v4 admission without changing them.
- **Evidence:** Fixed HOP DSL hash
  `4ad5598c0b5a15cb24fa9b79747634c7a8ea87fa909f40cb23ad2181528015ce`
  and D4 hash
  `94d8d41c58a35f6882846ebefe0fb7a19ab2787238819e83e61773fc54266b95`;
  exhaustive agreement over 59,049 local occupancies and 110,808 expected legal
  actions, split into 87,480 ordinary moves, 11,664 friendly hops, and 11,664
  opposing hops; all 36 ordered v4 action pairs; focused regressions passing
  117/117; the complete suite passing 443/443; independent reviews with no
  remaining P0–P3 finding; and no Plan-0012 solver, agent, gameplay experiment,
  or outcome.
- **Reconsider when:** A later compiler cannot reconstruct the intermediate cell
  from retained evidence, HOP requires hidden chain state, or an independent
  compatibility review finds drift in a prior schema, PUSH, or SWAP.

## D-025 — 2026-09-01 — Add CONVERT as a vector-bearing non-movement action

- **Decision:** Add `CONVERT` with one matching owned actor that remains
  unchanged and one adjacent opponent target, of any kind, that remains in its
  cell but changes to the actor's owner and the action's declared piece kind.
  A same-kind opponent is legal because ownership still changes. Record only
  `kind/from/to`; reject empty or friendly targets, missing or wrong-kind actors,
  undeclared, ranged, or off-board targets, actor movement, and multiple targets.
  Broaden v4 admission only to at least one `PUSH`, `SWAP`, `HOP`, or `CONVERT`
  role. Treat CONVERT as vector-bearing for canonicalization, D4, and numeric
  accounting but not as movement for mobility or asymmetry analysis.
- **Reason:** Ownership transfer is a mechanically distinct interaction in two
  provisional portfolio cells, yet the fixed adjacency and single target keep it
  reconstructable without a target-kind field, callback, phase, or compound
  action. Separating vector-bearing from movement avoids falsely granting
  relocation semantics to a stationary actor.
- **Alternatives:** Move the actor into the target cell; convert only a declared
  target kind; allow empty-cell creation or friendly recoloring; record the
  converted kind or full effect; treat CONVERT as MOVE-based; or add conversion
  together with adjacent capture and elimination.
- **Reversibility:** High for the remaining vocabulary. Existing valid PUSH,
  SWAP, HOP, and CONVERT definitions and their bytes are fixed; later compatible
  slices can broaden v4 admission without changing them.
- **Evidence:** Fixed CONVERT DSL hash
  `9233c363533156baa3553832d277810658256b65ddac28490af19b15e5478429`
  and D4 hash
  `64f7f012a33713f90276d2cd2ecfdc5bef8c5966295632c575a64c8dcbbc1f0f`;
  all 49 ordered v4 action pairs; exhaustive agreement over 59,049 local
  occupancies, 87,480 legal actions, and the fixed 0-through-8 histogram; zero
  D4 differences over 472,392 legality cases and 699,840 transitions; zero
  HOP-checkpoint differences over 7,200 states and 19,301 legal transitions;
  focused regressions passing 138/138; the complete suite passing 464/464 in
  333.681 seconds; three independent reviews with no P0–P3 finding; and no
  Plan-0012 solver, agent, gameplay experiment, or outcome.
- **Reconsider when:** A later compiler cannot reconstruct conversion from
  `kind/from/to`, feasibility shows that stationary conversion needs a bounded
  target-kind restriction, or an independent compatibility review finds drift
  in a prior schema, PUSH, SWAP, or HOP.

## D-026 — 2026-09-01 — Reject the CAPTURE_STEP alias and reuse MOVE_CAPTURE

- **Decision:** Do not add the proposed `CAPTURE_STEP` action to the executable
  DSL. Its draft contract—one declared step to empty or optional entry into an
  adjacent opponent cell with that one target removed—is exactly the existing
  `MOVE_CAPTURE`, already accepted by schema v4. Use `MOVE_CAPTURE` in both
  provisional removal cells and proceed directly to `ELIMINATE`. Retain the
  family-signature-v1 `CAPTURE_STEP` proposal token only so the reviewed identity
  grammar remains readable; exclude it from the current provisional portfolio
  and future executable compiler/final registry. Require those future builders
  to pass the signature or registry through the explicit nonretired-action
  allow-list validator before emission; DSL compilability and schema admission
  remain separate checks.
- **Reason:** A second action kind would change only the recorded spelling while
  duplicating legal actions, transitions, D4 action, static reachability, and
  terminal behavior. It would manufacture separate family/definition/D4 hashes,
  an asymmetry dimension, a simplicity concept, and census orbits for the same
  game graph, contradicting name-free mechanical identity. Reuse is the smallest
  compatible correction and leaves the capture cells novel at the complete
  ordered action/goal topology rather than at one relabeled primitive.
- **Alternatives:** Implement the alias and normalize it across every identity
  and evaluator; remove or reinterpret the historical family-v1 token; define a
  genuinely distinct mandatory-capture action now; use stationary removal; or
  delete both removal cells. Mandatory capture remains a bounded future proposal,
  but introducing it here would change the active hypothesis rather than repair
  the duplicate.
- **Reversibility:** High. No CAPTURE_STEP DSL definition, engine action, corpus,
  registry, search envelope, run, or outcome was created. Existing
  `MOVE_CAPTURE`, family-v1 hashes, and all schema identities remain unchanged.
- **Evidence:** Direct contract comparison; an independent all-occupancy
  `MOVE_CAPTURE` oracle over 59,049 3×3 states yielding 87,480 ordinary moves and
  87,480 captures; D4 equivalence over 472,392 legality cases and 1,399,680
  transitions; stable legacy parse/hash reconstruction plus fail-closed
  `validate_nonretired_family_signature` and registry tests for both roles; three
  independent pre-implementation reviews identifying the same alias; six
  provisional signatures remaining distinct after replacing both uses with
  `MOVE_CAPTURE`; the complete dependency-free suite passing 472/472 tests in
  350.375 seconds; and no solver, agent, gameplay experiment, or outcome.
- **Reconsider when:** A later portfolio explicitly proposes and versions a
  different capture rule such as globally mandatory capture, or a compiler finds
  a mechanical distinction that is absent from the current action, transition,
  and terminal contracts.

## D-027 — 2026-09-01 — Add ELIMINATE as an opponent-kind absence goal

- **Decision:** Add schema-v4 `ELIMINATE(piece)` with exactly `kind` and `piece`.
  It is true when the opponent owns no piece of the declared target kind. Keep
  the target owner derived from the role, store no edge/counter/history, and let
  zero initial targets satisfy the goal under the fixed v4 terminal priority.
  Broaden v4 admission to require either a PUSH/SWAP/HOP/CONVERT action or an
  ELIMINATE goal. Leave the goal unchanged under D4. Treat an unsatisfied goal as
  statically reachable only for MOVE_CAPTURE/CONVERT with a matching initial
  owned action actor. Make goal-progress-v1 agents fail closed instead of adding
  an uncalibrated heuristic.
- **Reason:** The capture and conversion portfolio cells require an attrition
  objective, but target absence is already fully derivable from board ownership
  and kind. The two-field goal stays finite, replayable, and independent of how
  removal or conversion occurred. Generator feasibility—not hidden DSL state—is
  the correct place to reject trivial zero-target setups.
- **Alternatives:** Store a target count or owner; require at least one initial
  target in the DSL; score each capture; declare victory only when the acting
  role removes the last target; infer elimination from the role's action kind;
  transform a fictitious target edge under D4; or add an immediate agent
  heuristic before calibration.
- **Reversibility:** High before any compiler, search envelope, feasibility
  census, atlas, or outcome exists. The new goal and its canonical identities are
  now immutable within schema v4; later setup gates and telemetry remain
  separately versioned.
- **Evidence:** Fixed parser/prose hash
  `6c1aa7c031eaf54772f128bfdfd6dc0305a3e3b18c9b9f0898875c03f51f94c4`,
  asymmetric fixture DSL/D4 hashes
  `a3a1761e1a04e62f95d69e0190d7368936842fdaf40a123f02a0f5696ec8f0a2`
  and `3a104109d52a633fb2b698fdfffa7f7189f373ad357d5796e7accba923013030`;
  all 441 ordered action/goal combinations with 405 admitted and 36 rejected;
  39,366 exhaustive predicate checks with the fixed 18,660/511/511/1 truth
  distribution; zero D4 differences over 314,928 checks; targeted transition and
  terminal precedence tests; 104 legacy canonical comparisons and 52 legacy
  engine comparisons over 236 actions/transitions; focused regressions passing
  157/157; the complete dependency-free suite passing 495/495 in 340.804
  seconds; three independent reviews closing one P3 implicit-CONNECT branch and
  finding no remaining P0–P3 issue; and no Plan-0012 gameplay or outcome.
- **Reconsider when:** Outcome-free feasibility cannot supply nontrivial target
  setups for the removal cells, a future state kernel cannot derive target
  absence from board state alone, or calibrated evidence justifies a separately
  versioned elimination-aware heuristic.

## D-028 — 2026-09-01 — Freeze exact one-ply replay telemetry and its synthetic benchmark

- **Decision:** Add replay-telemetry-v1 for schema-v4 definitions and complete
  retained traces. Freeze its action, goal, terminal, effect-mode,
  actor-relative outcome, and direct-effect vocabularies; enumerate every legal
  one-ply alternative exactly; and retain branching/forced, state-effect,
  successor-position, effect-signature, immediate-outcome, next-player exact
  legal-set, repetition, terminal, work, and digest evidence as separate
  dimensions. Treat CONVERT as standalone and only capture, push, swap, and hop
  as conditional special forms. Add no scalar agency score, routing threshold,
  agent, solver, selector, or gameplay evaluator.
- **Reason:** Numerous legal actions can reconverge immediately, equal next-action
  counts can hide different legal sets, occupancy dependency need not alter an
  opponent, and both roles realizing an effect does not by itself prove causal
  reciprocity. Exact one-ply reconstruction exposes those distinctions without
  importing agent policy or production gameplay outcomes into Plan-0012
  feasibility.
- **Alternatives:** Count legal moves only; collapse effects, successor states,
  and terminal alternatives into one interaction score; use sampled or depth-2
  counterfactuals; accept incomplete prefixes; infer telemetry from agent logs;
  or calibrate an atlas threshold from hand-authored fixtures.
- **Reversibility:** High through a new telemetry and benchmark version. Version
  1's vocabularies, work limits, canonical fields, evidence digests, seven
  fixtures, and ordered root remain immutable; later measurements can coexist
  without changing schema-v4 rules or prior telemetry evidence.
- **Evidence:** Strict reconstruction accepts only a schema-v4 definition and a
  complete canonical trace, with limits of 1,000 actions, 200 legal actions per
  decision, 200,000 successor evaluations, 40,000,000 next-action observations,
  1,000,000 stored JSON nodes, and stored depth 32. Exact-type, vocabulary,
  horizon, completeness, trailing-action, mutation, cycle, and canonical-byte
  checks fail closed. The seven frozen fixtures cover zero/one/two-plus and
  forced choices, CONVERT reconvergence, separate PUSH next-legal and terminal
  sensitivity, actor-relative win/draw/loss, B-only MOVE_CAPTURE/ELIMINATE,
  both-role SWAP repetition, and HOP dependency without direct effect. All seven
  pass eight-way D4 metric invariance; the SWAP cycle passes role-swap
  metamorphism. Their ordered benchmark root is
  `6789f97e7f0948df9fa66f75933c061a08e029ce49e9d9da33ae57a7b4a59a33`.
  No production Plan-0012 gameplay or outcome was created.
- **Reconsider when:** A new DSL action or goal falls outside the frozen
  vocabulary, the feasibility census proves these work limits insufficient, an
  exact metric is not D4/role consistent, or human calibration later justifies a
  separately versioned operational threshold.

## D-029 — 2026-09-01 — Fix a provisional finite domain before the feasibility census

- **Decision:** Define a versioned provisional 3×3 domain with balanced disjoint
  two-versus-two and three-versus-three setups; independent ordered
  `ORTHOGONAL_4`/`KING_8` profiles for A and B; both first players; an 18-ply
  structural horizon; and the family-specific D4 quotient of goal relations.
  Enumerate all 214,368 inputs deterministically. Compile each through the
  nonretired family boundary into strict schema v4 and retain a reconstructable
  witness binding domain, case, family, exact definition, D4 identity, and an
  action-specific structural state/work proof. Do not call this provisional
  artifact a final registry, search envelope, or atlas.
- **Reason:** The six heterogeneous cells need an inspectable common input supply
  before initial-state feasibility can determine their actual support. Separating
  the pure compiler and proof from the next census makes domain assumptions,
  identity drift, and combinatorial work auditable without using play or outcomes
  to choose membership.
- **Alternatives:** Start with one hand-selected setup per family; reuse the old
  place-versus-move generator; include only one direction profile; collapse
  first-player or goal orientation; permit unbalanced piece counts immediately;
  derive cases adaptively from census results; or freeze the six cells as a final
  registry before checking support.
- **Reversibility:** High through a new provisional domain/compiler version. The
  current root is immutable evidence for this census input, but a deficient cell
  or setup range can be removed or replaced before a later final registry and
  search-envelope version. No gameplay or outcome depends on it.
- **Evidence:** Exact setup counts 756 and 1,680; 11 family/frame occurrences;
  four ordered vector-profile pairs; two first players; 214,368 unique case
  hashes; ordered input root
  `e3011f74256fe39881eda3636533ec4352f7b4d2c4386e12d775ccc031b6d2e8`;
  descriptor hash
  `3456b5873dadfd177639b4c0d062bad6717d328a7ebee88a71f4294f9a5b0bc5`;
  fixed representative input/definition/D4/witness goldens; exact six-family
  reverse projection; action-specific two/three-piece state bounds
  14,364/31,920, 26,334/67,032, 19,836/67,032, and 40,603/181,051; focused tests
  passing 19/19; the complete suite passing 553/553 in 347.078 seconds; and
  independent semantic/boundary review with no remaining P0–P3 finding after two
  test-coverage repairs.
- **Reconsider when:** The outcome-free census finds insufficient or incomparable
  support, a goal-frame quotient is incomplete, an action can reach a state
  outside its proved owner/count class, or later work needs a separately
  justified board, setup, vector, first-player, or horizon domain.

## D-030 — 2026-09-01 — Retain all six families and advance only their 3+3 common-support core

- **Decision:** Treat all six provisional Plan-0012 family cells as structurally
  supported and recommend a separate development-atlas plan. Do not freeze or
  play an atlas in Plan 0012. The later search envelope should use the common 3+3
  setup core, retain every family-specific goal-frame representative, all four
  ordered vector-profile pairs, and both first players, and exclude the 32
  unsupported 2+2 fixed-connection strata explicitly. Match total nominal
  exposure per family with an outcome-free D4 selector and leave a disjoint
  unused orbit reserve. Freeze historical exclusion, D4 orientation, evaluator,
  work-cap, censoring, and inspection contracts before gameplay.
- **Reason:** Every family has nonempty eligible support, so no cell warrants
  outcome-free retirement. The common 3+3 core is the only setup grid shared by
  all six families without relying on CONVERT's ability to increase material.
  It supports a compact equal-family pilot while avoiding silent backfill from
  structurally easier cells. The minimum common stratum has 12 eligible D4
  orbits, so a later selector can take only a bounded subset and preserve unused
  cases.
- **Alternatives:** Remove either fixed-connection family; retain family-specific
  2+2 cells and compare unmatched setup mixtures; select equal cases per stratum
  and give families with more goal frames more total exposure; consume all 12
  orbits in the limiting stratum; add pieces or new rules to repair unsupported
  cells; or start gameplay before membership and evaluator protocols are frozen.
- **Reversibility:** High until the later atlas manifest is frozen. Plan 0012
  creates no final registry, search envelope, selected definition, gameplay run,
  or outcome. A new outcome-free envelope version may change quotas or omit a
  family if independent design review finds a defect before play.
- **Evidence:** 214,368 exact inputs and 102,336 D4 orbits; 71,384/24,208 eligible;
  all six family populations; 144 nonempty supported strata; family-specific
  eligible D4 minima/maxima of 12–131, 194–202, 138–201, 164–208, 89–227, and
  402–405; exact identification of the 32 unsupported 2+2 strata; complete gate-
  reason and structural descriptor distributions; 1,714,944 invariant transform
  checks; 391 authoritative identity checks spanning all strata; evidence digest
  `ade64ebaaf9892848e03c2312786a6ef3825f3c82f4311e16a9c810711d035d2`;
  and independent reviews with no remaining P0–P3 finding.
- **Reconsider when:** The atlas selector cannot preserve equal family exposure
  and an unused reserve, historical exclusion removes the limiting common
  support, a family-neutral evaluator cannot be specified, or later development
  evidence justifies a separately versioned within-family expansion or
  matched-ablation study.

## D-031 — 2026-09-01 — Select the atlas as matched first-player setup pairs

- **Decision:** Treat first player as a paired experimental treatment. Select
  one first-player-neutral setup geometry, then bind its A-first and B-first
  definitions together. Use 44 paired strata and quotas of 2, 3, or 6 pairs per
  stratum to give each family 24 development pairs/48 definitions. Bind the next
  equally sized, disjoint block as an unevaluated `confirmation_candidate_block`,
  not as a consumed one-shot reserve. Rank by mechanical family signature,
  neutral stratum, and paired mechanical identity; exclude display names and the
  historical root from rank. Authenticate history through a cutoff-fixed source
  adapter that emits only a definition-identity projection, and give the pure
  selector access only to that projection. Exclude an entire pair if either
  member collides. Defer eligible 2+2 cases outside the common core without
  labeling them unsupported.
- **Reason:** Independent A-first and B-first selection would confound starting
  tempo with different geometries. Pairing preserves within-setup comparison,
  equal family exposure, and a clear unit for D4-scheduled sampled evidence.
  Separating the history adapter from the selector prevents outcome-bearing
  records from influencing membership, while a rank independent of the history
  root makes exclusions skip cases rather than reorder the remaining supply.
- **Alternatives:** Select the two first-player strata independently; evaluate
  all 576 development and candidate-block definitions as unrelated cases; rank
  with registry IDs or outcome-derived fields; let the selector parse historical
  result records directly; sum the two member orbit multiplicities; silently
  backfill a deficient stratum; or consume the future block during development.
- **Reversibility:** High until a development manifest is frozen. Pair quotas,
  projection schema, and rank domain may change only under a new outcome-free
  selector version. Once gameplay begins, selected membership and the candidate
  block remain immutable for that version.
- **Evidence:** The 3+3 census collapses to 44 paired strata with 8,854 eligible
  paired D4 identities and 27,952 exact setup pairs before history. Family paired
  supply is 728, 1,584, 1,576, 832, 906, and 3,228; the limiting stratum has 12
  pairs, enough for two development pairs, two future-candidate pairs, and eight
  untouched pairs before history. First-player toggling is bijective and
  commutes with every D4 transform because the initial placement, goals, action
  vectors, gates, and structural bounds are first-player independent.
- **Reconsider when:** Authenticated history leaves fewer than twice the quota in
  any paired stratum, first-player partners fail to share D4 geometry or
  structural evidence, the selector cannot be kept outcome-inaccessible, or a
  later plan preregisters and consumes the candidate block for confirmation.

## D-032 — 2026-09-01 — Freeze the six-family selection before evaluator calibration

- **Decision:** Freeze Plan 0013's final ordered six-family registry, 3+3
  common-support envelope, exhaustive first-player-paired universe, fixed-cutoff
  historical identity projection, and deterministic 144-development plus
  144-candidate pair partition at commit `5bce4c0`. Explicitly reconstruct and
  defer every eligible 2+2 case. Admit production selection only through the two
  reviewed frozen projection roots; retain generic collision construction only
  as a review helper. Do not create an atlas manifest or evaluate a selected
  definition until a separate family-neutral evaluator benchmark is frozen.
- **Reason:** Cross-family evaluation is interpretable only if membership cannot
  react to outcomes or evaluator behavior. Exact A-first/B-first correspondence,
  all D4 orientation carriers, and pair-versus-definition counts must be evidence,
  not naming conventions or inferred multiplicities. Reconstructing the 2+2 band
  prevents the common 3+3 choice from silently erasing valid lower-density
  support, while a fixed production projection boundary prevents outcome-bearing
  history from choosing membership.
- **Alternatives:** Let the selector read raw experiment records; accept any
  self-signed identity projection; select A-first and B-first orbits separately;
  retain only the canonical representative's exact hash; omit 2+2 from the
  reconstruction; rank after historical exclusion; backfill a short stratum;
  consume the candidate block now; or run exact/play before evaluator
  compatibility is established.
- **Reversibility:** The implementation is reversible through a new atlas domain
  and selector version before gameplay, but these roots and partitions are
  immutable evidence for Plan 0013. Once selected-game outcomes exist, changing
  membership, history cutoff, rank, pair policy, or quotas would require a new
  development version and cannot repair this one.
- **Evidence:** The parent census reconciles as 33,264 deferred 2+2 and 73,920
  active 3+3 exact setup pairs. The active band contains 27,952 eligible exact
  pairs and 8,854 paired D4 identities in 44 strata. All 66 cutoff blobs match
  commit `6910b6c` byte-for-byte; the identity projection contains 2,243
  occurrences, 1,172 exact definitions, and 1,168 D4 identities. Collision is
  zero, leaving 144 development, 144 candidate, and 8,566 untouched pairs. The
  registry/envelope/universe/history/collision/selection roots are
  `535e9936…98dc5`, `eb875a7d…f6ead5`, `1167ac8d…cab15`,
  `6e99ceca…ab08d`, `b6b7f14e…fab354`, and `de65bf68…67830`; canonical
  selection SHA-256 is `b681c32b…68b5`. Independent final audit found no P0–P2
  defect, and the complete suite passed 604/604 in 975.642 seconds. No selected
  game was solved or played.
- **Reconsider when:** A reconstruction defect invalidates a frozen root; the
  family-neutral benchmark cannot support one common algorithm; or a new plan
  deliberately defines a different bounded portfolio before using any of this
  plan's outcomes. Difficulty, dominance, censoring, or taste after evaluation
  are not grounds to replace members within this version.

## D-033 — 2026-09-01 — Freeze a terminal-only common ladder before atlas outcomes

- **Decision:** Freeze `terminal_only_minimax-v1` and a five-fixture synthetic
  conformance benchmark at commit `d34c383`. Authorize only
  `random-v1-weak` and `terminal_only_minimax-v1-depth1` for the initial atlas
  ladder, with all eight D4 orientations, seeds `0..7`, distinct controlled-role
  instances, one reset when supported, reuse across the ordered seed sequence,
  and a 3,456-node cumulative cap per terminal-only role slot. Retain depth 2 only
  as a diagnostic benchmark probe. Retain all eight orientation slots because
  seeded coordinate-ordered tie selection is not itself D4-equivariant, even
  though exact scalar values are invariant and per-action values transform
  covariantly. Prove fixture/atlas separation before every evaluator call and
  access no selected definition in this slice.
- **Reason:** Existing goal-progress agents reject ELIMINATE and are not
  calibrated across REACH, CONNECT, and ELIMINATE. A zero-valued nonterminal
  cutoff provides a deliberately weak common baseline whose only semantic
  knowledge is the engine's terminal outcome. Freezing its min/max, cache, RNG,
  node, lifecycle, and failure behavior before outcomes prevents family-specific
  tuning and makes later weakness visible rather than silently unequal.
- **Alternatives:** Remove the ELIMINATE guard; compare families with different
  heuristics; keep random only; authorize depth 2 or stronger search immediately;
  construct agents afresh per game rather than per role slot; treat synthetic
  outcomes as game-quality evidence; or benchmark directly on selected atlas
  members. Each alternative either changes evaluator semantics, weakens matched
  exposure, or leaks production outcomes before protocol freeze.
- **Reversibility:** A later richer heuristic or strength requires a new
  versioned benchmark and pre-outcome protocol. The `d34c383` benchmark roots
  remain immutable calculation evidence and cannot be retuned after atlas
  outcomes. Adding strength does not authorize replacing membership or spending
  the candidate block.
- **Evidence:** Four fixtures rebind to Plan-0012 exact/D4/byte identities and
  its synthetic projection; the sole new SWAP/CONNECT fixture is exact- and
  D4-disjoint from that parent and structurally disjoint from both atlas blocks.
  Forty D4 exact/search slots, 320 replayed random games, 320 replayed
  terminal-only games, and 80 role slots cover all five active actions, all three
  goals, A/B/draw, terminal priority, cutoff, root and recursive B minimization,
  cache, tie, and budget behavior. Benchmark root is `340e928d…15da0` and
  canonical SHA-256 is `5097d4d5…a3ffc`. Two independent audits found no
  remaining P0–P2 defect; 635/635 tests passed in 979.572 seconds. Production
  definition access and production outcome counts are both zero.
- **Reconsider when:** A reconstruction defect invalidates a root, selected-game
  execution exposes a predeclared evaluator integrity failure, or a new
  outcome-free benchmark justifies a separately versioned common agent. Poor
  results, dominance, runtime inconvenience, or taste are not grounds to change
  this ladder within the current atlas version.

## D-034 — 2026-09-01 — Freeze the six-stage atlas protocol before the manifest

- **Decision:** Freeze Plan 0013's complete outcome-free evaluation protocol at
  commit `28e6a03`. The fixed order is immutable manifest, exact evidence,
  random sampled play, terminal-only depth-1 sampled play, replay telemetry, and
  assessment/inspection. Freeze all 288 exact slots, 2,304 D4 principal-
  variation replays, 36,864 sampled games, 36,864 telemetry slots, 18,432
  matched-start blocks, seeds, orientations, work ceilings, censoring, exact
  labels, weak-sampled gates, descriptive family-signal rule, and deterministic
  inspection metrics before any selected outcome. Authorize no stronger route.
  Require every concrete stage entrypoint and its recursive production-code
  closure to be blob-frozen before manifest reservation. Outcome-capable stages
  reconstruct schedules only from the frozen protocol and never receive the
  full selection or candidate definitions. Bind immutable plan copies, typed
  artifact identities, all-prior-stage predicates, and terminal `BLOCKED`,
  `FAILED`, `ORPHANED`, or `COMPLETED` recovery without retry or replacement.
- **Reason:** Broad family coverage is only informative if membership, workload,
  labels, thresholds, inspection, executable code, and crash semantics cannot
  react to a result. Separating exact role and move-order labels from deliberately
  weak sampled evidence makes evaluator limitations visible. Separating
  descriptive telemetry from gates prevents synthetic metrics from becoming an
  uncalibrated definition of fun. A typed one-shot evidence chain makes every
  missing or failed stage publicly distinguishable from an unfavorable game.
- **Alternatives:** Run all stages through one mutable command; choose stronger
  agents or additional cases after observing weak results; materialize the
  candidate block inside an outcome runner; treat live documentation as the run
  contract; silently resume or replace failed slots; tune fairness or inspection
  thresholds after outcomes; or create the manifest before all executable
  closures exist. Each would permit outcome-informed adaptation or weaken
  reconstruction and failure accounting.
- **Reversibility:** Before any manifest or selected outcome, a materially
  different design may be introduced only as a new reviewed protocol version.
  After manifest reservation, this version's membership, coordinates, caps,
  evidence identities, executable closure, and terminal recovery are immutable;
  failures remain failures and do not authorize replacement. The disjoint
  candidate block remains unallocated.
- **Evidence:** Exact/orientation/profile/role/game/matched/telemetry schedule
  roots are `de198bc1…a1a7`, `931e48a2…84e`, `c2624a0d…26a`,
  `4d3e945b…2b48`, `da59e67a…0f18`, `112babd7…c3ea`, and
  `be0a229a…2867`. Protocol root is `d933c779…7fd3`; its 2,216,054 canonical
  bytes have SHA-256 `ed20be0b…980d`. The total exact ceilings are 19,722,000
  states and 592,781,760 state-action candidates; the sampled depth-1 ceiling is
  15,925,248 nodes. Three independent audits found no remaining P0–P2 defect;
  25/25 focused tests passed in 349.975 seconds and the complete suite passed
  660/660 in 1075.505 seconds. No selected definition, gameplay outcome, or
  candidate allocation was produced.
- **Reconsider when:** A reconstruction defect invalidates a frozen root or a
  selected-game execution exposes a predeclared integrity failure. Poor game
  results, dominance, runtime inconvenience, incomplete stages, or taste are not
  grounds to alter or rerun this protocol version.

## D-035 — 2026-09-01 — Supersede the atlas execution envelope before any manifest

- **Decision:** Supersede only D-034's V1 execution-evidence envelope with V2 at
  commit `0697800`, before any production evidence directory, manifest
  reservation, selected-definition evaluation, or outcome exists. Preserve
  D-034's six-stage order and every scientific schedule, coordinate, seed, cap,
  label, threshold, candidate-shape rule, family-signal rule, and inspection
  rule unchanged. Require a candidate-neutral bootstrap to publish and
  authenticate the protocol, immutable plan, and all six recursive production
  closures before manifest reservation. Freeze six separate noninjectable
  `run`/`recover` entrypoints for manifest, exact, random, terminal-only depth 1,
  telemetry, and assessment. Require immutable full-slot journals and ledgers,
  fixed-path recursive parent authentication, contradiction-sidecar checks,
  externally referenced body reauthentication, frozen completion gates, and
  deterministic recovery that never invokes a scientific callback.
- **Reason:** Implementing the concrete edges exposed pre-outcome provenance
  defects that an outcome-free protocol value alone could not safely defer: the
  V1 manifest could reserve before all executable closures were durably rooted;
  recovery and descendants needed a candidate-neutral source of protocol, plan,
  and closure truth; self-consistent alternate ancestors or residual artifacts
  needed fixed-path rejection; and a completed assessment needed reconstruction
  from authenticated parent evidence. Correcting these before reservation is a
  protocol repair, not an outcome-informed scientific adaptation.
- **Alternatives:** Keep the V1 envelope and rely on live Git or caller-supplied
  schedules during recovery; publish closures only after manifest selection;
  trust embedded parent seals without comparing their fixed stage paths; allow
  mutable partial ledgers or callback-based recovery; silently ignore residual
  journals or completion artifacts; or start evaluation and repair provenance
  afterward. Each would weaken one-shot reconstruction or allow evidence to be
  selected, reinterpreted, or lost after a crash.
- **Reversibility:** The V1 envelope remains historical evidence of the initial
  preregistration design, but it is not executable for Plan 0013 and must not be
  restored. V2 is still pre-outcome and may be superseded only by another
  explicitly reviewed, outcome-free version before its manifest reservation.
  Once reservation occurs, its bootstrap, closures, coordinates, failure states,
  and recovery semantics are immutable. The confirmation candidate block remains
  unallocated.
- **Evidence:** All original schedule roots remain
  `de198bc1…a1a7`, `931e48a2…84e`, `c2624a0d…26a`, `4d3e945b…2b48`,
  `da59e67a…0f18`, `112babd7…c3ea`, and `be0a229a…2867`. The V2 protocol
  root is `8126c33f…f04c`; its 2,220,598 canonical bytes have SHA-256
  `b732f174…9229`. Independent architecture and provenance reviews found no
  remaining P0–P2 defect after cache-race, sidecar, alternate-parent, residual-
  artifact, fixed-schedule, completion, and recovery probes. Focused runs passed
  25/25 protocol tests in 337.099 seconds and 109/109 stage/evidence tests in
  21.400 seconds; the complete dependency-free suite passed 769/769 in
  1,085.011 seconds. No production evidence directory or gameplay outcome was
  created.
- **Reconsider when:** A reconstruction defect invalidates the V2 root or a
  selected-game execution exposes a predeclared integrity failure. Unfavorable
  results, runtime, dominance, weak-agent behavior, or taste are not grounds to
  change this envelope or its scientific protocol.

## D-036 — 2026-09-01 — Freeze the six-family development manifest once

- **Decision:** Accept the single completed Plan-0013 outcome-free development
  manifest produced from clean source HEAD `5e6a865`. Freeze exactly 144 matched
  first-player pairs, 288 definitions, and 2,304 D4 orientation definitions,
  with 24 pairs/48 definitions/384 orientations in each of the six families.
  Export and evaluate no member of the separately frozen confirmation candidate
  block. Keep HEAD and source tree unchanged until all six V2 stages have
  terminal seals; leave the live immutable store and documentation changes
  uncommitted during that chain, and exclude regenerable `.locks/*.lock` files
  only at the final evidence commit.
- **Reason:** The manifest publicly reconstructs the preregistered development
  block exactly, while the candidate block remains disjoint and inaccessible.
  The V2 closure contract intentionally requires every later stage to reseal
  against the same HEAD/tree captured before manifest reservation. Committing
  even correct evidence or documentation mid-chain would change HEAD and make
  exact and later stages fail closed, so a delayed evidence commit is part of
  preserving provenance rather than mutable experimentation.
- **Alternatives:** Commit the manifest immediately and invalidate all later
  closure reseals; weaken the HEAD requirement; regenerate closures after seeing
  membership; copy candidate definitions into the manifest; evaluate a subset;
  or delete and retry the one-shot reservation. Each would violate the frozen
  execution or membership contract.
- **Reversibility:** None within this V2 development chain. The completed
  manifest, bootstrap, reservation, attempt, completion, and terminal seal are
  immutable. A reconstruction defect may terminate this chain but cannot
  authorize replacement members or a retry. A future separately versioned,
  pre-outcome portfolio remains possible only outside this evidence identity.
- **Evidence:** Bootstrap root is `96c7e239…ea22`; manifest root is
  `ffbb2256…f7c3`; the 2,681,806-byte canonical manifest has SHA-256
  `d3eb19a3…ee89`; terminal seal is `5ee92d2b…e46`; protocol root remains
  `8126c33f…f04c`; source tree is `17468fd2…fad`. The fixed selection and all
  288 definition/2,304 orientation hashes reconstruct exactly. Pair, exact, and
  D4 intersection with the 144-pair candidate block are all zero. Public recovery
  returned `VERIFIED_NO_OP`; gameplay outcome and candidate export counts are
  zero. Three independent read-only audits found no P0–P3 defect, and the focused
  evidence/data/manifest suite passed 72/72 in 21.409 seconds.
- **Reconsider when:** Only a byte, identity, schedule, closure, or lifecycle
  reconstruction defect is demonstrated. Outcome quality, runtime, dominance,
  weak-agent behavior, or taste cannot change this manifest.

## D-037 — 2026-09-02 — Accept the complete atlas exact evidence

- **Decision:** Accept the one-shot Plan-0013 exact stage as `COMPLETED` and
  authorize the already frozen random stage. Retain all 288 exact results and
  all 2,304 D4 principal-variation replays without replacement. Apply the frozen
  pair truth table exactly: 51 first-player-dominant pairs pass the exact entrance
  gate; A-role-dominant, B-role-dominant, and horizon-affected pairs do not.
  Treat this as routing evidence only, not as a fair-game or quality claim.
- **Reason:** Every slot completed within its structural cap, every D4 PV replayed
  to the claimed terminal, and no invalidity, proof contradiction, or censor
  occurred. The paired A-first/B-first design separates move-order dominance from
  role dominance before the deliberately weak sampled gates are applied.
- **Alternatives:** Select individual DSL definitions by win rate; treat draws as
  fair without distinguishing horizon; admit role-dominant pairs; tune caps or
  exact labels after seeing results; skip random; or replace difficult cases.
  Each violates the preregistered unit, truth table, stage order, or one-shot
  contract.
- **Reversibility:** None within this V2 chain. The exact journals, ledger,
  catalog, completed body, and terminal seal are immutable. A later protocol may
  define a different portfolio or interpretation only as new evidence; it cannot
  alter these labels or refill this development block.
- **Evidence:** Exact terminal identity is `6c575e50…a6c45`; summary root is
  `da72fa33…1cc5`; ledger SHA-256 is `9724f7ec…9836`; the 2,592-record
  catalog root is `bceb6e87…920e`. Exact/PV status is 288/288 `COMPLETE` and
  2,304/2,304 `VALID`. Search used 2,538,786 of 19,722,000 aggregate states,
  maximum 29,610. Raw A/B/draw is 98/179/11; terminal reasons are GOAL 246,
  `NO_LEGAL_ACTION` 31, and `PLY_LIMIT` 11. Pair labels are 51 first-player,
  23 A-role, 62 B-role, zero second-player, and eight horizon affected, spanning
  31/44 strata at the exact gate. Public recovery returned `VERIFIED_NO_OP`;
  three independent audits found no P0–P3 defect; focused tests passed 49/49.
- **Reconsider when:** Only a demonstrated byte, replay, schedule, cap, closure,
  lifecycle, or label-reconstruction defect. Dominance, family imbalance,
  runtime, weak-sampled results, or taste cannot alter this exact stage.

## D-038 — 2026-09-02 — Accept the complete atlas random evidence

- **Decision:** Accept the one-shot Plan-0013 random stage as `COMPLETED` and
  authorize the already frozen terminal-only depth-1 stage. Retain all 18,432
  random games and their complete traces without replacement. Apply the frozen
  integer weak-balance rule exactly: 26/144 pairs pass random alone, and 16/144
  pairs across 12 strata pass both exact and random. Treat the 16 as routing
  evidence for the next weak strength only, not as fair games or quality claims.
- **Reason:** Every scheduled random game completed, the fixed eight-seed RNG
  stream and all 105,440 selected actions replay exactly, and no invalidity,
  proof contradiction, censor, schedule drift, or candidate-block access
  occurred. Random play reduces the exact entrance set without changing the
  preregistered pair unit or observing the future depth-1 result.
- **Alternatives:** Tune the minority-share threshold after seeing outcomes;
  discard horizon-heavy pairs ad hoc; select definitions instead of matched
  A-first/B-first pairs; promote the 16 immediately; rerun seeds; or skip the
  depth-1 stage. Each violates the fixed gate, evidence unit, or one-shot stage
  order.
- **Reversibility:** None within this V2 chain. The random journals, ledger,
  catalog, completed body, and terminal seal are immutable. A later protocol may
  study other agents or thresholds as new evidence but cannot change these
  labels, seeds, or members.
- **Evidence:** Random terminal identity is `bafc4a52…e9b6`; summary root is
  `5e268d12…34da7e`; ledger SHA-256 is `88e00f44…cf0f`; catalog root is
  `dbb28915…cdf`. Status is 18,432/18,432 `COMPLETE`; A/B/draw is
  7,142/9,470/1,820; GOAL/`NO_LEGAL_ACTION`/`PLY_LIMIT` is
  15,700/912/1,820; total play is 105,440 plies. Random labels are 26 weak-
  balance, 105 role-imbalance, and 13 excessive-horizon. Exact/random
  intersection is 16 pairs: push-hop 9, convert-push 5, push-swap 2, all exact
  first-player-dominant. Public recovery returned `VERIFIED_NO_OP`; three
  independent audits found no P0–P3 defect; focused tests passed 47/47.
- **Reconsider when:** Only a demonstrated byte, replay, seed, schedule, closure,
  lifecycle, RNG, or aggregate-reconstruction defect. Unfavorable family balance,
  runtime, later depth-1 disagreement, or taste cannot alter this random stage.

## D-039 — 2026-09-02 — Accept the complete atlas depth-1 evidence

- **Decision:** Accept the one-shot Plan-0013 terminal-only depth-1 stage as
  `COMPLETED` and authorize the already frozen telemetry stage. Retain all
  18,432 complete games and cumulative role-slot node ledgers without
  replacement. Apply the frozen three-way gate exactly: 14/144 pairs across 10
  strata pass exact, random, and depth-1. Do not promote these paired signals to
  single-game fairness, strategy, or enjoyment claims.
- **Reason:** Every scheduled game completed under the fixed 3,456-node
  per-role-slot cumulative cap; total use was only 279,242 nodes and the maximum
  role-slot use was 497. Every depth-1 action value, tie choice, trace, outcome,
  and node-ledger transition independently reconstructs. The gate was applied
  without censor substitution, cap change, rerun, or access to the candidate
  block.
- **Alternatives:** Treat depth-1 A/B equality as single-game fairness; promote
  random-only pairs; relax the two-stratum family rule for push-swap; strengthen
  or retune the agent after seeing results; rerun ties; or skip telemetry. Each
  violates the preregistered evidence unit, gate, or stage order.
- **Reversibility:** None within this V2 chain. The depth-1 journals, ledgers,
  catalog, completed body, and terminal seal are immutable. Other agents or
  thresholds require a separately versioned future protocol and cannot rewrite
  this stage.
- **Evidence:** Depth-1 terminal identity is `f5d1e937…be226`; summary root is
  `4e2e53cf…a105`; ledger SHA-256 is `33f65a16…680f`; catalog root is
  `77e1fa7c…21fe`. Status is 18,432/18,432 `COMPLETE`; A/B/draw is
  6,380/11,806/246; GOAL/`NO_LEGAL_ACTION`/`PLY_LIMIT` is
  16,802/1,384/246; play is 56,788 plies and 279,242 expanded nodes. Depth-1
  weak balance is 48/144. The three-way intersection is push-hop 9 pairs/6
  strata, convert-push 3/3, and push-swap 2/1. All 14 are exact first-player-
  dominant; each depth-1 pair is A/B = 64/64 solely because the first player
  wins all 128 constituent games. Public recovery returned `VERIFIED_NO_OP`;
  three independent audits found no P0–P3 defect; focused tests passed 47/47.
- **Reconsider when:** Only a demonstrated byte, trace, minimax, node-ledger,
  schedule, closure, lifecycle, or aggregate-reconstruction defect. Weak-agent
  limitations, later telemetry, family outcome, or taste cannot alter this stage.

## D-040 — 2026-09-02 — Accept the complete atlas replay telemetry

- **Decision:** Accept the one-shot Plan-0013 replay-telemetry stage as
  `COMPLETED` and authorize the already frozen final assessment stage. Retain
  all 36,864 telemetry records without replacement. Use telemetry only for the
  preregistered descriptive report and deterministic inspection selection;
  never use it to change pair or family gates.
- **Reason:** Every complete random and depth-1 trace was admitted exactly once,
  replayed under its manifest DSL, and validated. No sampled trace was missing,
  censored, invalid, or silently excluded, and every telemetry field, parent
  root, work cap, and digest independently reconstructs.
- **Alternatives:** Turn interaction telemetry into a post-outcome promotion
  score; omit uninteresting or long traces; average D4/seed slots as independent
  observations; replace records after inspection; or select the candidate block.
  Each violates the frozen non-gate, denominator, or development-only contract.
- **Reversibility:** None within this V2 chain. The telemetry journals, ledger,
  catalog, completed body, and terminal seal are immutable. New telemetry
  semantics require a future protocol and cannot rewrite these records.
- **Evidence:** Telemetry terminal identity is `2869fc55…f670`; summary root is
  `a69a8cc1…97a7`; ledger SHA-256 is `429ef172…a6a3`; catalog root is
  `6a91ae0c…d8d7a`. Status is 36,864/36,864 `VALIDATED`, with all four exception
  counts zero, and trace plies reconstruct as 162,228 = 105,440 + 56,788.
  Descriptive A/B decisions are 79,634/82,594; forced decisions 3,957/1,104;
  opponent-dependent actions 38,894/28,330; reciprocal-dependency games 10,850;
  repeated-configuration games 1,261. Public recovery returned
  `VERIFIED_NO_OP`; independent full replay and chain audits found no P0–P3
  defect; focused tests passed 53/53.
- **Reconsider when:** Only a demonstrated byte, trace, field derivation, digest,
  schedule, closure, lifecycle, work-cap, or aggregate-reconstruction defect.
  Diagnostic values, later family status, or taste cannot alter this stage.

## D-041 — 2026-09-02 — Close the failed V2 assessment without a gameplay conclusion

- **Decision:** Accept the single Plan-0013 V2 assessment attempt only as a
  terminal `FAILED` lifecycle. Preserve its reservation, attempt, failure body,
  production closure, and terminal seal exactly. Do not rerun, delete, replace,
  or supersede that assessment inside Plan 0013, and do not assign a formal pair
  report, family status, inspection selection, negative atlas result, or
  confirmation allocation. Close Plan 0013 without a formal scientific
  conclusion and move any report-only repair to a separately versioned plan and
  evidence identity.
- **Reason:** The one-shot stage failed before emitting any completed assessment
  body. Its trusted entrypoint constructed telemetry admissible slot IDs as
  tuples while the strict ledger reconciler correctly requires exact lists,
  producing `TypeError: admissible slots must be an exact array`. Read-only
  continuation then exposed a second assessment-side interpretation defect:
  zero-legal-action terminal observations belong to `legal_observation_count`
  and bin `0`, not to `decision_count`. The evidence layer correctly sealed the
  first exception with no partial evidence. The five parent stages remain
  authenticated and unchanged; failure of their reporting join is neither
  evidence for nor against game quality.
- **Alternatives:** Rerun the same V2 stage after editing code; delete its attempt
  or failure; hand-author or formally adopt the raw 14-pair diagnostic; label the
  six-family core unsupported; alter thresholds or inspection rules after seeing
  outcomes; allocate the candidate block; or discard the five completed parents.
  Each would violate the one-shot lifecycle, invent a nonexistent formal report,
  or introduce post-outcome discretion.
- **Reversibility:** None within the V2 chain. A future plan may create a new,
  explicitly post-outcome report attestation that binds the five completed parent
  terminals and this failure seal and changes only the two demonstrated
  mechanical integration defects. It may not rewrite V2 or change gameplay,
  schedules, labels, thresholds, family rules, inspection rules, or candidate
  allocation.
- **Evidence:** Assessment terminal identity is
  `812b8c4bfc9ffbb2fefa750361ebd33d998e9504ea9032b83b95049dc4f8e889`;
  reservation is
  `91138600dcc40b649e527161ab1d4d49c87e6600928823cf8857c8a17f5f2a6d`;
  attempt is
  `bffac6f25d063e09839f35e2b09c72c3d3853178029113e8f1b7dcef95219c96`;
  production closure is
  `f7792895c5ad0085f841cc7dce64d0f631df6d5ed8abdd3961ed08334df5b2e4`;
  and failure-body SHA-256 is
  `9db7d724cd0d692c0a4347ebfb47579fd758dcb86c0011107ae2e5d98b69385d`.
  The sealed failure is `builtins.TypeError`, message `admissible slots must be
  an exact array`, with no partial-evidence root and no completed assessment,
  report, or inspection artifact. Public recovery returned `VERIFIED_NO_OP`.
  Independent audits found P1=2 in assessment, no defect in the parent evidence
  or failure chain, and showed that the corrected telemetry identities pass all
  36,864 records; all and only 2,296 `NO_LEGAL_ACTION` games contain the extra
  zero-action observation. The raw parent summaries expose 14 three-way
  diagnostic pairs across 10 strata, all exact first-player-dominant; this is
  not a formal V2 assessment. The confirmation candidate block remains unused.
  The unchanged dependency-free suite passed 769/769 in 1,073.706 seconds,
  confirming that its synthetic and mocked assessment coverage did not exercise
  either production integration defect.
- **Reconsider when:** A byte-level defect is demonstrated in a completed parent
  or in the sealed failure chain, or the proposed repair cannot remain a purely
  mechanical reconstruction of the already frozen rules. In that case abandon
  the repair and retain Plan 0013 permanently without a formal conclusion; do
  not rerun V2.

## D-042 — 2026-09-02 — Accept the separate post-failure assessment attestation

- **Decision:** Accept Plan 0014 as `COMPLETED` report-only evidence. Preserve the
  original Plan-0013 V2 assessment as `FAILED`; do not relabel, rerun, replace, or
  complete it. Treat the reconstructed inner report and inspection selection as
  the unchanged calculation of the preregistered rules, wrapped by an explicit
  post-failure attestation. Allocate no confirmation candidate.
- **Reason:** The separately versioned stage changed exactly two mechanical
  integration points and zero scientific rules, bound all five completed parents
  and the old failure, ran once from an audited source closure, and publicly
  recovered as a verified no-op. Full reconstruction yields 14 frontier pairs,
  all exactly first-player-dominant. The two positive family-count statuses are
  therefore family-level routing signals, not fair standalone games.
- **Alternatives:** Rerun V2; adopt the raw diagnostic without a new lifecycle;
  call matched two-game balance single-game fairness; allocate the held-out block;
  reinterpret the two family counts as confirmation; or discard the failed
  lifecycle. Each would violate the preserved history or epistemic boundary.
- **Reversibility:** None inside Plans 0013–0014. Their evidence stores and
  terminal seals are immutable. A future plan may use only the documented
  conclusion as historical context and must create fresh, pre-outcome evidence.
- **Evidence:** Production source/tree is `3fa9f6b…3f992` /
  `f491a361…6a50`, closure `975541c3…57d7`, protocol root
  `b412e0af…5d38d`, bootstrap `94d7016f…a860`, reservation
  `8f16dbc6…80f2`, attempt `bb392260…133c`, completed root
  `aafdee21…699f`, and terminal `9272adcd…b5ae`. Inner report is
  `2a873b0b…5484d`, inspection root `279b0459…86b6`, and outer attestation
  `9ca2d719…5290`. The final 874-test suite and both real boundaries passed;
  public recovery returned `VERIFIED_NO_OP`; three pre-run and three post-run
  audits each found P0=P1=P2=P3=0. Candidate access and every new game,
  telemetry, outcome, or solver count are zero.
- **Reconsider when:** Only a demonstrated byte, source-chain, lifecycle,
  reconstruction, or repair-boundary defect. Game taste or a desire to rescue a
  family cannot rewrite this attestation.

## D-043 — 2026-09-02 — Replace hand-selected families with a closed blind universe

- **Decision:** Begin Plan 0015 as an outcome-free, transition-free exhaustive
  census of the current isotropic occupancy-v4 typed-role grammar. Canonicalize
  mechanics under both D4 and complete role swap, remove self-isomorphic setup-
  only asymmetry, exclude the full role-swap closure of all six Plan-0013
  semantic regions, and partition only after the universe and history projection
  are fixed. Put terminal-blind dynamic probing in a separate Plan 0016.
- **Reason:** The six-family atlas was broader than the original
  place-versus-move lane but remained a hand-picked sample and produced no fair
  standalone candidate. Independent derivations show that the existing DSL
  supports 109 fresh role-neutral semantic classes and 1,518 asymmetric profiled
  skeletons before setup feasibility. Closing this existing space reduces more
  uncertainty than tuning the failed six cells or adding an arbitrary primitive.
- **Alternatives:** Continue Plan-0013 families; enumerate ordered A/B signatures
  without role-swap quotient; open the unused candidate block; rank by a weighted
  complexity/interaction proxy; combine grammar changes with a BFS; or add
  `REMOVE_ADJACENT` immediately. These invite duplicate games, leakage,
  Goodhart selection, or confounded evidence.
- **Reversibility:** High before production partition evidence. The grammar and
  census are new versioned artifacts and do not alter old DSL bytes or results.
  Once development/reserve/untouched identities are sealed, their membership is
  immutable within Plan 0015.
- **Evidence:** Closed arithmetic target is 16 coherent role atoms, 220 admitted
  ordered signatures, 115 role-swap classes, 109 fresh classes, 14 ordered goal
  frames, three D4-invariant vector profiles, 3,300 ordered profiled skeletons,
  66 self-isomorphic exclusions, 198 old-region ordered exclusions, and 1,518
  fresh canonical skeletons. The 15-resource-pair 3×3 master lattice has 6,798
  labeled setups per skeleton and 5,111,055 factorized D4 setup carriers. Two
  independent derivations and one adversarial scope review agree on these values;
  implementation evidence does not yet exist.
- **Reconsider when:** The independent implementation cannot close the grammar,
  inverse witnesses, work bound, history projection, or breadth floor. In that
  case terminate with the registered failure or negative breadth label; do not
  rescue a subset or add a primitive inside the same plan.

## D-044 — 2026-09-03 — Seal the typed grammar in a capability-minimal sibling package

- **Decision:** Accept Plan-0015 slice 1 as a complete outcome-free grammar
  checkpoint in the standalone `parity_forge_universe` package. Preserve the
  frozen `parity_forge/__init__.py` byte for byte, expose no engine or gameplay
  capability through the new package, and require every public enumeration and
  identity boundary to revalidate the sealed finite universe before use.
- **Reason:** The legacy package initializer eagerly imports the engine, so a
  submodule under that package cannot satisfy the slice's production-capability
  boundary even when its own imports are pure. A sibling package makes the
  absence of transition, terminal, outcome, solver, agent, telemetry, selection,
  candidate, and evidence-production capability inspectable while leaving all
  frozen history unchanged. Finite enumeration also permits stronger closure:
  the original Enum singleton identities, semantic predicates, spatial algebra,
  hash domains, old-six firewall, arithmetic, endpoints, and roots can all be
  derived from code literals or checked against immutable anchors.
- **Alternatives:** Modify or lazily load the frozen initializer; import the new
  module by bypassing package initialization; place semantic truth in mutable
  module tables; rely only on counts or mutually consistent registries; or wait
  to validate closure inside the compiler. These either change frozen behavior,
  hide a capability dependency, or allow a coherent mutation to redefine the
  purported universe.
- **Reversibility:** High before setup identities or partition membership are
  frozen. Slice 2 may add a separate compiler bridge, but it must not weaken or
  duplicate the sealed grammar authority. The slice-1 descriptor and public
  identities remain fixed within Plan 0015.
- **Evidence:** The implementation closes 16/256/36/220/115/109 semantic counts,
  49/14/10 goal-frame counts, three vector profiles, and
  3,300/66/198/99/1,518 skeleton counts with exact inverse witnesses and fixed
  stabilizer histograms. Descriptor root is
  `05826dc2da02890f3f562ee2d6febda523c58837affb757b5dff6d62c074e6ab`;
  final package/source/test blobs are `6a7aba9e…5bd3`, `55cc8f7c…71f7`, and
  `49376caf…c91b`. Independent final review reports P0=P1=P2=P3=0, including
  same-payload exact-type singleton, coherent permutation, whole-class
  replacement, alias-registry, and mutable-authority checks.
- **Reconsider when:** A byte-level mismatch, a semantic alias, an incomplete
  inverse, a mutable authority path, or a forbidden production capability is
  demonstrated. In that case reopen slice 1 and invalidate downstream compiler
  or census work; do not patch the meaning through a later artifact.

## D-045 — 2026-09-03 — Bridge the pure universe through canonical schema-v4 wire values

- **Decision:** Implement Plan-0015 slice 2 as a strict compiler from typed
  setup members to exact canonical schema-v4 JSON and an inverse projection from
  only that compiler image. Do not import or return the legacy `GameDefinition`
  type in the production closure. Prove equality with the authoritative DSL
  parser, canonical serializer, definition hash, and D4 transform in tests.
- **Reason:** Normal import of `parity_forge.dsl` necessarily executes the frozen
  `parity_forge` initializer and loads `engine`, so directly returning a
  `GameDefinition` cannot coexist with the plan's capability-minimal production
  boundary. Canonical JSON is already the authoritative machine-readable DSL
  wire value. A narrow image parser can reconstruct every skeleton, setup, and
  first-player field and then require exact recompilation without acquiring any
  transition, terminal, outcome, solver, agent, telemetry, selection, candidate,
  evidence, filesystem, network, or import-bypass capability.
- **Transform contract:** The master domain is 1,518 canonical fresh skeletons
  by 6,798 setups by two first players. Compilation also accepts the fresh
  ordered/oriented D4-plus-role-swap transport closure without silently
  canonicalizing it. D4 transforms skeleton and coordinates only; owner swap
  exchanges setup A/B positions only; first-player toggle changes only the first
  label; complete role swap exchanges programs, targets, profiles, setup owners,
  first player, and role-local `a`/`b` piece identifiers together. Exact wire
  comparisons recompute the target member's non-mechanical `pf15-<hash>` name.
- **Alternatives:** Change or lazily load the frozen initializer; use importlib
  to bypass package initialization; allow engine capability in the compiler;
  duplicate all legacy DSL dataclasses; return a mutable dictionary; restrict
  input to canonical representatives and weaken transform commutation; or give
  every definition one constant display name. These either alter history, hide
  dependencies, weaken inverse evidence, or reduce inspectability.
- **Reversibility:** High until the setup census or partition is frozen. Wire
  version 1 can be abandoned before downstream evidence, but its exact input
  domain and transform semantics may not be reinterpreted after use. The 6,798
  setup enumerator and factorized master traversal remain slice-3 work rather
  than production capability added here.
- **Evidence:** Three independent read-only investigations reproduced the exact
  6,798 setup domain and count-pair supplies, the 10,319,364/20,638,728 master
  products, the 5,111,055 Burnside carrier count, and the 11,652-skeleton
  transport closure. All found the same legacy-import capability conflict and
  the same canonical-wire resolution. The implementation/test blobs are
  `95bb7581…251a` and `d796545f…3113`; the corrected 35-test boundary passes in
  857.518 seconds. Factorwise exhaustive proof covers 3,036 canonical
  skeleton/first-player members, 13,596 setup/first-player members, all 54,384
  setup D4 images, every compiler mapping, and exact inverse projection. A first
  review found dynamic instance-method shadowing despite a 33-test pass; the
  repaired all-nested preflight and class-method anchors reject 358 independent
  review paths. Two final reviews report P0=P1=P2=P3=0. The resulting complete
  dependency-free suite passes 956/956 in 3,085.160 seconds with the same two
  intended opt-in skips.
- **Reconsider when:** The pure compiler cannot reproduce authoritative
  canonical bytes and hashes for every factor, cannot invert its complete image,
  cannot close the declared transform algebra, or requires a forbidden runtime
  dependency. In that case stop slice 2; do not relax the capability boundary or
  defer a lossy inverse to the census.

## D-046 — 2026-09-03 — Use pair-aware support and resource-aware tempo proofs

- **Decision:** Fix Slice 3 as two pure boundaries: a one-carrier
  `initial_structure` authority followed by a one-shard `static_census`
  factorizer. Derive exact initial goals, legal/dependency counts, and contact
  from board sets without constructing a state or action. Use pair-aware
  monotone support for spatial impossibility, a separate lineage support for
  every initial ELIMINATE target, and a resource-aware 55-state count lattice
  that preserves A-first and B-first schedules independently through ply 18.
  Record every ordinary rejection as a structured code/role/tempo fact; treat
  compiler, closure, invariance, asymmetry, and work defects as fatal.
- **Reason:** Schema v4 checks both goals after every action. Opponent PUSH and
  SWAP can therefore relocate a role's pieces into its goal even when that
  role's own vector graph cannot do so; role-local optimistic reachability is
  not a sound rejection gate. The count relation likewise needs actor, empty,
  opponent, and capacity resources but must still ignore geometry and strategic
  choices. Separate first-player layers prevent an even 18-ply horizon from
  hiding tempo impossibility. Exact stabilizer factoring preserves every labeled
  setup with a weight while avoiding a five-million-record global set or sort.
- **Fixed proof boundary:** `PLACE` needs an empty cell; MOVE/PUSH/HOP need an
  actor and an empty cell; SWAP needs an actor plus an empty or opponent piece;
  MOVE_CAPTURE has separate empty-preserve and opponent-reduction branches; and
  CONVERT requires both owners. Necessary goal counts are 1 for REACH, 3 for a
  3x3 opposite-edge CONNECT, and zero opponents for ELIMINATE. Candidate-loop
  work is named separately from legal-action emission and occupancy lookup. D4
  leaves scalar facts fixed; complete role swap exchanges role and first-player
  labels before comparison. Owner-only swap is neither invariance nor quotient.
- **Orbit contract:** Dispatch uses the exact stabilizer member tuple, not its
  size. The five signatures `{I}`, `{I,FLR}`, `{I,FTB}`, axis-Klein, and D4 have
  141/810/165/396/6 skeletons and 6,798/3,511/3,511/1,827/970 setup orbits per
  skeleton. Canonical setup bytes select representatives. Global weight bins
  are 1,184,850/3,294,033/627,732/4,440 for weights 1/2/4/8, reconstructing
  5,111,055 carriers, 10,319,364 labeled setups, and 20,638,728 paired members.
- **Alternatives:** Reuse the old role-local feasibility relaxation; treat both
  players as having nine interchangeable turns; allow a non-PLACE full-board
  stutter; use stabilizer size or owner swap as the quotient; materialize and
  sort every carrier; collapse reasons into suffixed strings or a score; or
  import the engine in production. These respectively permit false rejection,
  erase tempo, retain impossible paths, misfactor identities, exceed the memory
  contract, hide overlapping evidence, or violate the capability boundary.
- **Reversibility:** High before the static census is sealed. Kernel or table
  version 1 may be rejected by tests or audit, but no formula may change after a
  census root or partition depends on it. A changed action semantic requires a
  new universe/table version rather than silent relaxation.
- **Evidence:** Independent design paths agree on the exact legal/goal formulas,
  strong support proof, tight count relation, work ceilings, Burnside values,
  and role/D4 covariance. Exhaustive read-only differentials covered 373,977
  action/profile/occupancy states and 137,781 goal/occupancy states. Tight versus
  loose count comparison covered all 1,470 action/count/tempo schedules: 192
  layer tables and 336 memberships differ, but all present-envelope goal
  reachability booleans and first witnesses agree. The tight transition table
  contains 610 directed count edges versus 684 in the looser relation; exact
  maxima remain 115,194 states and 2,070,432 candidate iterations per schedule.
  Implementation and production census evidence do not yet exist.
- **Reconsider when:** A real one-step effect escapes the support or count
  relation, an initial formula differs from the authoritative DSL, a complete
  role-swap covariance fails, or exact subgroup/weight arithmetic does not
  reconstruct both labeled populations. Stop before census publication; do not
  weaken the failed proof only for selected rows.

## D-047 — 2026-09-03 — Seal the one-carrier initial-structure boundary

- **Decision:** Accept the pure Plan-0015 `initial_structure` v1 authority as the
  fixed one-carrier input to the remaining factorized static census. Preserve
  its ordinary fully rederived result path and its output-only prepared snapshot
  bridge as separate trust boundaries. The bridge returns fresh canonical
  result bytes plus their result hash, but no parser accepts that pair as
  authority; public parsing, serialization, hashing, and validation continue to
  rederive the complete result from the embedded strict carrier.
- **Reason:** A 5,111,055-carrier stream cannot afford repeated construction and
  public revalidation of an already derived result, while a fast path that keeps
  reading caller-owned carriers or prepared values after validation is subject
  to valid-to-valid mutation races. Detaching a canonical carrier payload and a
  copied, fully checked prepared token gives each row one coherent input
  snapshot without weakening the public boundary.
- **Fixed evidence:** The completed implementation/test blobs are
  `c7d806aa38c3a8152ae6289f64e3cba0765a7ac1` and
  `18ff527411db6fc1669c68358f8435425ed7287b`. The sealed count table contains 55
  states, 610 directed edges, 1,470 entries, and 22,428 layer memberships at
  root
  `de2e65f28be1f60aff4712c23c8681ea7945324886a2954a0f8d8cbfa905d226`;
  exact maxima are 115,194 state weight and 2,070,432 action/scan work per
  schedule. The focused 30-test boundary passes in 9.618 seconds, all 33 tests
  in the dedicated file pass within the 989/989 complete suite in 4,357.623
  seconds with two intended skips, and independent semantic and hostile-
  boundary audits report P0=P1=P2=P3=0.
- **Scope:** This freezes one-carrier formulas and identities only. The exact
  setup-orbit table, 1,518 streamed shards, weighted reason combinations,
  aggregate roots, and production census evidence do not yet exist. It creates
  no dynamic reachability, fairness, strategy, replay-value, or fun evidence.
- **Reconsider when:** A later static-census implementation cannot consume the
  output-only snapshot without changing its bytes, any public boundary accepts
  cached output without full rederivation, or an independent oracle finds a
  carrier, D4, complete-role-swap, count, work, or mutation mismatch. In that
  case version the kernel rather than silently changing this sealed boundary.

## D-048 — 2026-09-03 — Seal the factorized static-census implementation before production

- **Decision:** Accept `static_census` v1 as the pure factorization and
  aggregation implementation over the sealed 1,518 fresh skeletons and 6,798
  labeled setups. Freeze source/test blobs
  `fd5fb486ea33fac840b2951ff0a3680a3c221058` and
  `93aa6d428b5378f06027438c04d6a38f9ad25bae`, with raw SHA-256
  `f7205f8113b37d28bd003884438fb88bb19eb2a608fb12263c979faa2670d460`
  and `510a28556955008be2f61336323b38351872137fe9795a01ae2a23c2e68bec83`;
  freeze setup-table root
  `f1bc82d1cfbaac9933e097aba2f4118737e19f7a190f06bc9f0a83add17c2e23`,
  and skeleton-authority root
  `53221ffdbd42e4c86e9c54eadb6e0659bf71ff350dcdf0944b062ce56c3e1488`.
  Do not run production until a separately reviewed source closure,
  reconstruction protocol, and immutable one-shot lifecycle bind these bytes.
- **Reason:** Exact stabilizer factoring reduces 10,319,364 labeled rows to
  5,111,055 weighted carriers without changing their total mass. A single
  process can stream that domain, but an estimated multi-hour run needs an
  authenticated terminal artifact and recoverable one-shot edge before its
  result can be evidence. An in-process checkpoint is useful for diagnostics
  but must not become a resumable or caller-supplied authority.
- **Fixed arithmetic:** D4 fixed setup counts are
  6,798/2/62/2/224/224/224/224. The five stabilizer signatures contain
  141/810/165/396/6 skeletons and yield 6,798/3,511/3,511/1,827/970 setup
  orbits. Global weight bins are
  1,184,850/3,294,033/627,732/4,440 for weights 1/2/4/8. The independent
  ordered derivation is `(11,085,600 - 215,508 - 647,982) / 2 = 5,111,055`;
  weighted setup and paired-member masses are 10,319,364 and 20,638,728.
- **Execution contract:** `build_static_census_v1` is the production calculation
  path: it prepares once, derives exactly 1,518 shards, and performs one linear
  carrier pass while retaining only fixed tables, compact summaries, and the
  current row/shard. Repeated `advance_static_census_checkpoint_v1` calls
  revalidate a growing prefix and are intentionally quadratic diagnostic calls,
  not the production runner. No path imports gameplay, outcomes, history,
  selection, candidate, filesystem, network, or dynamic-import capability.
- **Evidence:** Independent setup/Burnside oracles, all 1,518 stabilizers, five
  real stabilizer shards, the D4 970-representative versus 6,798-raw comparison,
  reason/contact covariance, hostile snapshot/shard/table/report boundaries,
  and synthetic complete aggregation pass in the dedicated 36-test file in
  601.045 seconds. The complete dependency-free suite passes 1,025/1,025 in
  4,908.329 seconds with two intended skips. Two independent final reviews of
  the exact blobs report P0=P1=P2=P3=0.
- **Scope:** This seals executable calculation mechanics and exact upper-domain
  arithmetic only. No production stream, eligibility total, rejection
  combination, production shard/report root, historical exclusion, blind
  partition, dynamic reachability, fairness, strategy, replay value, or fun
  evidence exists.
- **Reconsider when:** The evidence edge cannot bind this exact transitive
  closure, public reconstruction cannot recover every aggregate from compact
  immutable artifacts, or a production estimate cannot fit an explicitly
  authorized resource envelope. Version or reject the edge; do not silently
  change the sealed calculation or treat a partial checkpoint as a result.

## D-049 — 2026-09-03 — Pre-register a non-resumable one-shot static-census edge

- **Decision:** Run the sealed factorized census only through one new
  `plan0015-factorized-static-census-stage-v1` edge. After a durable reservation
  and attempt it calls `build_static_census_v1()` once with no arguments. Its
  public surface is only fixed `run|recover --repository`; it accepts no
  callback, table, shard, report, clock, checkpoint, rank, history, or outcome.
  Recovery never calls the builder or resumes a checkpoint.
- **Artifact contract:** Preserve the exact canonical report bytes separately
  as `static-census-report.json` under a 256 MiB limit. Its whole-file SHA-256
  and embedded domain-separated `report_digest` are distinct. A small completed
  artifact binds that body reference plus summary anchors re-extracted from the
  report. Bootstrap, reservation, attempt, report, exactly one lifecycle body,
  and terminal are immutable ordered artifacts; locks and pending publications
  are operational and identity-excluded.
- **Crash contract:** Bootstrap alone may continue after source resealing.
  Reservation or attempt without a complete report becomes permanently
  `ORPHANED`. A valid post-attempt report without completion recovers by adding
  only completion and terminal; an unsealed body recovers by adding only its
  terminal. No state after reservation is recalculated. Once report or
  completion exists, a later exception cannot replace it with failure.
- **Source contract:** Keep the five Slice-3 production blobs byte-identical.
  The implementation source must be a merge-free descendant of this
  preregistration checkpoint, change exactly `.gitignore`, the four named
  evidence-edge modules and four matching tests, and retain this active plan
  byte-for-byte. The recursive production closure is those five sealed modules
  plus the pure reconstructor, protocol, evidence store, and stage; every file
  is bound by path, Git blob, SHA-256, and byte count. Reseal current HEAD/tree,
  closure files, and plan before publication, after calculation, and before
  terminal return.
- **Reconstruction boundary:** Public recovery validates bounded canonical
  bytes, both embedded authorities, all 1,518 ordered shard summaries, every
  shard commitment and report-level aggregate/root, the actual report body
  digest, and the whole-file reference without traversing 5,111,055 carriers.
  This proves immutable compact-report reconstruction, not an independent
  leaf-semantic rerun. A later read-only leaf audit cannot replace, resume, or
  extend the authorized attempt.
- **Filesystem boundary:** Use descriptor-relative no-follow, nonblocking opens;
  exact regular-file type, mode, link, size, and stable metadata checks; bounded
  reads; pending-file `fsync`; no-replace hard-link publication; directory
  `fsync`; and a nonblocking exclusive stage lock. Reject symlinks, FIFOs,
  sockets, devices, external hard links, path swaps, unknown catalog entries,
  and conflicting pending/public bytes.
- **Scope:** This decision authorizes implementation and review only. It does
  not authorize the production run and contains no census result, eligible
  carrier, history projection, partition, transition, outcome, candidate,
  fairness, strategy, replay-value, or fun evidence.

## D-050 — 2026-09-05 — Keep complete history identity outside the legacy import closure

- **Decision:** Implement the Plan-0015 history projection in
  `research/parity_forge_history`, with a standard-library-only wire adapter and
  literal source pins. Require all 66 authenticated legacy blobs and all seven
  authenticated canonical fixture wires before interpretation. Return only the
  detached exact/D4/role-neutral/schema/source-carrier projection.
- **Reason:** Importing a legacy DSL module also imports its package initializer
  and engine. That violates the outcome-capability boundary even if no game is
  run. Reusing only literal pins and differentially testing a small strict wire
  adapter preserves the frozen legacy implementation without importing it in
  production.
- **Identity contract:** Preserve exact and historical D4 identities unchanged.
  For the new role-neutral identity, globally alpha-normalize piece labels in
  every D4/complete-role-swap image before taking the canonical minimum. Preserve
  cross-owner label equality and opponent references; owner-local renaming is
  insufficient. The corrected projection root is
  `00973dcc6447697fae4639442bfe2fa93a5d0ff7c62f279688fa38dac1e2e3c9`.
- **Alternatives:** Import the old package; fabricate fixture rows from hash
  constants when raw sources are omitted; rename only owner-local piece labels;
  or change frozen source packages. Each weakens a required boundary.
- **Evidence:** All 33 focused tests pass, including complete 1,179-definition
  differential identity checks, mandatory-source failures, detached fixed-root
  validation, and fresh-process import checks. Independent final review found
  no remaining P0–P3 defect. Full regression acceptance is recorded separately
  in the current project state.
- **Reversibility:** New research-only code and versioned identities; no frozen
  source or experiment is changed. Reconsider only if the source inventory,
  identity semantics, or capability closure is disproven, never to improve
  selection yield.

## D-051 — 2026-09-05 — Close the failed breadth floor before unnecessary partition work

- **Decision:** Conclude Plan 0015 scientifically as `BREADTH_FLOOR_NOT_MET`.
  Keep its static stage `COMPLETED` and partition `NOT_STARTED`. After the
  pending implementation regression completes, archive the plan without
  assigning development, reserve, or untouched membership.
- **Reason:** Public reconstruction and two independent grouping methods show
  that nine of the 109 semantic classes have zero eligible carriers. Historical
  exclusion can only reduce these sets, so the registered requirement that all
  109 have a supported stratum cannot hold. Ranking cannot change this proof.
- **Execution deviation:** The negative criterion was preregistered, but an
  early-stop procedure before partition was not. Omitting that calculation is
  an explicitly recorded closeout decision after the necessary-condition proof.
  The partition definition-of-done item is not marked performed. This decision
  creates no replacement run, terminal seal, or relaxed success criterion.
- **Alternatives:** Implement a multi-million-carrier partition despite a known
  negative result; lower the breadth floor; select only the remaining 100
  classes; or add a primitive inside Plan 0015. None is needed to establish the
  registered conclusion, and the latter three would change the experiment.
- **Evidence:** See
  [the authenticated negative report](../experiments/reports/0015-static-breadth-floor-negative.md).
  The 51 empty skeletons account for 131,022 rejected carriers; all 3,036 stratum
  totals reconcile with their resource-count rows. No game result was read or
  computed for this analysis.
- **Scope:** The other 100 semantic classes have static supply. This is not a
  proof that they lack fair or enjoyable games. The immediate next step is to
  distinguish universal class support, complete supported/rejected accounting,
  and game quality in a general next-study protocol. A removal action or its
  proposed 48-spec support audit is deferred: material transitions matching a
  capture branch do not prove spatial aliasing, but the present evidence also
  does not establish a need for a new primitive. Do not count the known 100 as
  successful candidate games or use a new study to relabel this negative result.
- **Reversibility:** Interpretive closeout adds no member allocation and leaves
  every source artifact immutable. Reconsider the conclusion only if its fixed
  source or count reconstruction is invalidated; new hypotheses need new plans.

## D-052 — 2026-09-05 — Put a small single-game diagnostic before large allocation

- **Decision:** Design the next bounded study around detecting known false
  fairness signals, before activating the complete-accounting partition option.
  Preserve fixed-first-player, ordered-policy observations and all outcome/censor
  denominators. Keep exact value and match-level aggregates separate. This is
  an interim measurement question aligned with founding-directive sections 1
  and 8, not a choice of human mastery level or forced-win tolerance.
- **Reason:** The [strategic review](reviews/2026-09-05-astra-strategic-review.md)
  supports general complete accounting but notes that all-strata allocation
  permits 4,502 development carriers / 9,004 separate games. Available supply
  does not justify this evaluation cost. A small diagnostic asks directly whether
  the measurement can preserve obvious failure modes and nontrivial controls.
- **Scope:** The [TABLE/TRACE draft](designs/single-game-diagnostic-contract.md)
  describes eight synthetic calculation distinctions, not DSL games or fairness
  evidence. Exact fixtures, outputs, integration work, and deterministic budgets
  must be frozen and reviewed before implementation. A real DSL/engine vertical
  slice is necessary before candidate evaluation; it can be part of the same
  small study rather than another generic framework. No arbitrary pilot size,
  new evaluator run, candidate access, or selection is authorized here.
- **Retained work:** The coverage draft's explicit hash contract, independently
  reviewed all-n allocation/prefix proof, and 5,272-pattern synthetic check
  remain useful design components. The six-path static-exposure audit does not
  extend the fixed history cutoff, cover unrecorded runtime activity, or close
  every source-fixture exposure question.
- **Boundary:** Plan 0015 remains in closeout while its full regression runs.
  Its negative result and unexecuted partition are unchanged. Activate only one
  subsequently reviewed plan; do not automatically activate the broad partition
  draft, retune prior evaluation policies, or require a human taste decision
  that is unnecessary for synthetic diagnostic conformance.

## D-053 — 2026-09-05 — Integrate calibration into a bounded real-game pilot

- **Decision:** In response to the user's request to accelerate discovery,
  archive Plan 0015 at accepted checkpoint `1fe53927c` and register Plan 0016.
  Combine existing tiny DSL integration checks and the actual pilot summaries;
  do not build a standalone TABLE framework or full-universe partition first.
- **Budget:** Six unordered goal pairs × two contact strata × two slots explain
  the 24-carrier ceiling. Deterministic 64-attempt sampling has no backfill.
  Five policy pairs, two first players, eight orientations, and two seeds give
  at most 3,840 games and 30,720,000 charged search nodes. Fixed first players
  remain separate; the permissive further-diagnosis flag is not fairness.
- **Authority:** Frozen DSL, compiler, predicates, engine, and agent versions
  stay unchanged. Source is small scripts and focused tests, with immutable
  manifest/records rather than a new generic lifecycle. After focused tests and
  review, unchanged committed exploratory code may run alongside the full suite;
  results remain provisional until full acceptance. All failed/censored/empty
  slots remain visible. No candidate block, new primitive, or production exact
  solve is involved.
- **Evidence boundary:** This is prospectively specified gameplay on a
  static-informed convenience sample, not a confirmation or complete novelty
  census. Legacy named regions remain excluded; prior results are not retuned.
  Independent plan review found no unresolved P0–P2 and clarified iteration and
  decision-start accounting before implementation.

## D-054 — 2026-09-05 08:37 UTC — One provisional exact diagnostic alongside regression

- **Decision:** Preserve Plan 0016's registered document byte-identically in the
  completed folder as EXECUTION_COMPLETE / ACCEPTANCE_PENDING, and register
  Plan 0017 as the sole active plan. The fixed pilot and its replay have ended;
  no new pilot games are allowed. One capped exact call may proceed while the
  already-running full regression continues. Formal acceptance of both studies
  remains gated on its actual `Ran ... / OK`, not intermediate passing lines.
- **Procedural change, before the new result:** This explicitly supersedes the
  Plan-0016 pre-execution note's no-plan-move/no-commit waiting restriction and
  the prospective Plan-0017 draft's fully serialized acceptance gate. It does
  not alter the former pilot's sampling, schedule, budgets, raw triage, records,
  or outcome criteria. Its original document remains retrievable at `eb9e53fcc`
  and in the byte-identical archive; the parent manifest/source pin is unchanged.
- **Reason and evidence:** User asks for continued fast discovery. Pilot
  membership is already fixed, played, and replayed; this is an openly
  outcome-informed diagnostic, not untouched confirmation. Only carrier 7,
  B-first, base orientation remains unresolved after three direct short-win
  proofs. Constant A1/B3 bounds the unchanged solver at 9,576 cache misses.
  `git diff 1fe53927c eb9e53fcc -- src research` is empty: the actual solver and
  engine passed the previous 1,177-test acceptance. The newer 42 focused tests
  and independent record-helper review passed; the new full suite is still
  running. No source/test byte changes or fresh full-suite launch is needed.
- **Independent review:** A source-level bound/API review and a separate
  process-risk review found no technical dependency requiring a serial wait.
  Keep the explicit one-call cap, different output, source pins, committed plan,
  and provisional status. Existing CLI `solve` is unsuitable because it lacks
  a cap and uses DSL-v1 interpretation text; use the unchanged public solver
  directly without fixing or invoking that historical wrapper.
- **Risk and containment:** The pending suite may still expose an integration
  defect, and the exact process briefly competes for CPU. A failure requires
  impact assessment, not silent rewriting/retry or automatic acceptance. Seeing
  the diagnostic result is irreversible exposure and is recorded as such;
  the source, old artifacts, and new failure/attempt records remain preserved.
  This is not authority for new mechanics, another member, another exact call,
  paid resources, external publication, or a fairness/enjoyment claim.

## D-055 — 2026-09-05 — User requires games with no possible draw

- **Authority:** The user explicitly says: 「引き分けが存在しないゲームを作る必要があることを覚えておいて。」
  This resolves the preceding product clarification and is a mandatory ongoing
  requirement, not a proposal or a request to equalize A/B match-win counts.
- **Contract:** Every legal play from an admitted initial state ends after
  finitely many moves with exactly one A/B winner. No legal draw, winnerless
  terminal or infinite continuation is allowed. This precedes fairness and
  simplicity admission; it is not satisfied by zero sampled draws or decisive
  optimal play alone. An incomplete proof/search is UNKNOWN, not qualification.
- **Immediate consequence:** Plan-0017 carrier 7 / B-first is ineligible as
  currently defined: the preserved legal 18-ply DRAW witness suffices. Cancel
  its proposed draw-preserving cycle follow-up as a discovery next step. No
  currently established candidate satisfies all product requirements.
- **Preservation and scope:** Keep every prior DSL, fixture, result and source
  pin unchanged. This adoption records the user's clarified requirement and
  current disposition; it does not rewrite old experiment claims. No new rules,
  tiebreak assignment, solver run, or code change is performed in this recording
  task. A later rule/generator/evaluator change needs its own reviewed version.
- **Fairness consistency:** A finite deterministic perfect-information game
  without draws has a forced winner at perfect play. Do not combine this hard
  condition with an automatic rejection of every exact A_WIN/B_WIN, which would
  exclude the entire target class. Continue to test comparable finite-skill
  fairness, obvious short forced strategies, asymmetry and simplicity separately.
- **Durability:** Record the condition in AGENTS, charter, evaluator contract,
  current state, backlog and active plan so future sessions do not reopen the
  resolved question or silently continue draw-based discovery.

## D-056 — 2026-09-05 — Accept prior studies and start with a structural no-draw proof

- **Accepted checkpoint:** The existing suite completed 1,219 tests in
  5,123.653 seconds, `OK (skipped=2)`, exit 0. Independent audit confirmed no
  FAIL/ERROR, code drift or saved-artifact drift. Close Plans16/17 in a separate
  report; keep provisional raw labels and the byte-identical Plan16 archive.
- **Next scope:** Under the user's continuation instruction, register Plan18:
  CONVERT versus MOVE_CAPTURE, eight nonexcluded ordered goal pairs, two
  outcome-blind setup slots each. No placement role or new primitive. Existing
  DSL/compiler/static gates/engine/agents remain frozen. Opponent count strictly
  decreases on converter turns, proving all-legal finite decisive termination.
- **Known limitation before selection:** Current compiler m≤3 bounds every
  game by six plies. The pilot may be too shallow; do not conceal this or claim
  deep human fairness. At most2,560 fixed games and32 fixed base exact calls
  test the smallest existing-code counterplay region, without replenishment.
- **History/calibration:** Exclude prior46 Plan16 definitions through global-
  alpha-role identity and the whole old-six semantic firewall. New executed
  cap18 calibration uses the excluded E/E region, with separation tests.
- **Proportional engineering:** A narrow certificate is sufficient; no generic
  reachable-DAG checker, new grammar census, TABLE framework or primitive is
  required. Focused tests/review precede one committed-source exploratory run
  and one parallel full regression. Formal acceptance still requires both.
  Exact PV gets one external replay; inspection must not replay it again.

## D-057 — 2026-09-05 — Token-bounded discovery and practical solving resistance

- **Authority:** User wants model tokens spent on system development and design
  ideas, with bounded programmatic verification. They clarify that a game easily
  completely read by AI lacks the desired complexity, and endorse evaluating
  search methods plus the short calibration/design/playtest sequence.
- **Decision:** Preserve simple rules and mandatory no-draw D-055; add practical
  solving resistance as a product screen. The mathematical existence of a forced
  winner is not the issue. A cheap correct exact solution can disqualify a game
  for complexity without proving it unfair. Simple-but-hard is a hypothesis
  about playable games, not proof of fun or sufficient fairness evidence.
- **Operational boundary:** The next study must define "solved", reference
  solvers and finite budgets before outcomes. Budget exhaustion is UNKNOWN,
  not a hardness certificate. Do not create hardness by solver weakness, bugs,
  irrelevant branching or arbitrary ever-larger budgets. Maintain separate
  termination proofs, short-strategy diagnostics and human judgment.
- **Token architecture:** Reuse Python generation/engine/agents/capped solver/
  persistence. No per-game LLM call is needed in the inspected pilot path.
  Legacy run-batch/strong-batch already exist, but use the DSL1 generator and
  old draw-oriented gates; they are not a current D-055/D-057 discovery path.
  Prefer reusing/adapting existing parts with a thin bounded entry point over a
  new platform or bespoke runner per idea. Model interventions/outer rounds need
  finite limits, compact reports and stop conditions. Actual token quota
  measurement/enforcement is not yet built; no usage cap was changed here.
- **Method assessment:** Compare a proposed search method against a frozen
  baseline with equal resource accounting and separate evaluator/agent changes.
  Count useful, nonduplicate evidence, not merely timeouts or self-raised scores.
- **Evidence and preservation:** Plan18's24 base conditions were already solved
  in850 total states; they do not demonstrate the newly emphasized complexity.
  Source inspection confirms reusable LLM-free execution components, while the
  current runner/certificate are study-specific. All old definitions/results
  remain unchanged. The running full regression is not restarted or modified.
- **Reversibility / next step:** This is a documented product/operating refinement,
  not new production execution or paid-resource authority. Finish acceptance of
  Plan18, then register the smallest bounded calibration/adapter work consistent
  with the accepted two-to-three-stage proposal. Revisit operational thresholds
  through disclosed calibration, never by silently relabeling past results.

## D-058 — 2026-09-05 — Split new methods from immediate game discovery

- **Authority:** User assigns new-method development to another task and asks
  this task to improve existing methods toward a playable game as soon as practical.
- **Decision:** Supersede unexecuted Plan19 in this task. Do not build its generic
  workflow or search-method comparator here. No other task is created or sent
  work without a concrete user request. Reuse current APIs for Plan20's bounded
  directional capture/push pilot, retaining D-055/D-057 and simple/deep priorities.
- **Rationale:** Existing parser/engine support4×4/5×5 and directional vectors;
  the3×3 compiler was an experiment restriction. A weighted-distance proof
  guarantees natural decisive termination without new mechanics. Two independent
  source-only reviews verified feasibility and highlighted the pusher's exposure
  to immediate recapture. Outcome claims remain untested before registration.
- **Scope:** Six fixed B-first setups,120 fixed games and6 capped
  exact calls; no retries or budget expansion. Four new experiment/test files
  only, no frozen source edits or platform work. Separate reviewed registration
  precedes all production play; one full regression gates acceptance.
  The initial12-definition draft was narrowed before its first registration:
  independent source-only reasoning proved every A-first counterpart trivially
  won by one advancing A and immediate recapture of each pusher. No production
  outcome was used for this exclusion; B-first is not proved good or difficult.
- **Reversibility:** Preserve Plan19 as superseded context and all old studies.
  A poor result closes this fixed batch; it does not authorize reopening it,
  spending paid resources or weakening the no-draw/complexity requirements.

## D-059 — 2026-09-06 — End coordinate tuning and stage a SWAP/PUSH question

- **Authority:** The user asks this task to continue with existing methods until
  rules merit human attention, while preserving mandatory no-draw games and not
  spending model tokens inside the game loop.
- **Evidence:** Plan24–26 held the runner/hunter rules fixed and moved only two B
  start rows. All base games were decisive, but each plan missed a prospective
  human gate. Public trace review found three-runner relay sacrifices and strong
  T3/T4 terminal-horizon reversals; fresh seeds also prevent causal attribution
  of cross-plan win-count changes. More coordinate tuning would target an agent
  boundary rather than a new game structure.
- **Decision:** Retire that coordinate-only lineage without generalizing to all
  runner/hunter games. Stage one structurally different existing-DSL candidate:
  A right/down SWAP versus B up/left PUSH, both with REACH_EDGE goals. Candidate
  definition was fixed before bounded analysis. A decreasing integer potential
  proves decisive termination by54<cap55. Independent checks agree that neither
  role forces a win within its first7 turns; two representative pure B shadow
  policies have explicit counterlines. These limited negatives do not establish
  longer-strategy absence, fairness, difficulty or fun.
- **Scope:** Plan27 remains an unregistered draft until Plan26's registered full
  regression and closeout pass. Reuse the existing exact/base/final cascade with
  fresh seeds and no per-game LLM. Add only candidate-specific telemetry/gates
  showing actual SWAP/PUSH contact and T4 horizontal use; do not change the shared
  adapter, agents, DSL, solver or generic framework. No production game, exact
  solve or replay occurs under this decision.
- **Reversibility:** A proof defect, simple universal strategy, easy exact result
  or fixed gate miss closes the new wire without retry, backfill or threshold
  change. All Plan24–26 records and the unregistered exposure remain preserved.

## D-060 — 2026-09-07 — Close interrupted Plan28 and stage fixed-four preselection

- **Authority:** The user asks what comes next and how Plan numbering works,
  while the standing instruction is to continue existing-method research until
  a game merits human attention. D-055 no-draw and D-057 bounded local
  verification remain mandatory.
- **Plan28 evidence:** Its registered pilot is immutable `NO_FLAG`. The only
  registered full regression was still running at22:50:38, with1:06:32 elapsed
  and1,103 log lines; the host rebooted at22:55:35. No final `Ran`, `OK` or exit
  survived. The preregistered operational-failure and no-retry rules therefore
  require `TECHNICAL_ACCEPTANCE_FAILED / FULL_REGRESSION_INTERRUPTED_BY_HOST_REBOOT`.
  This is not an assertion-test failure and does not invalidate the saved pilot.
- **Numbering:** Plan numbers identify chronological research work units, not
  game versions, success counts or retry numbers. A number remains attached to
  its record after pass, rejection or technical failure. A later Plan may depend
  on accepted evidence but may not rewrite or refill a prior Plan.
- **Next scope:** Activate Plan29 in design stage. Freeze four structurally
  different5x5 definitions and a fixed rank, then use existing no-draw proofs,
  short AND/OR, separate T2/T2 and T3/T3 cells, capped exact/state-prefix checks
  and a deeper short-force screen. Select at most one unchanged survivor for a
  separate fresh-seed Plan30. No per-game model, generic method platform,
  replacement cell, outcome-based reranking or human-quality claim.
- **Evidence boundary:** Pre-Plan source computations whose complete definitions,
  checker and raw records are absent from the repository are development exposure
  only, not Plan29 selection evidence. Every production definition, limit and
  order must be registered before the one execution; UNKNOWN remains incomplete
  evidence. Technical acceptance again requires an actual successful full-suite
  summary and exit, independently audited.

## D-061 — 2026-09-07 — Fail Plan29 early and make Plan30 admission-first

- **Evidence:** One attempted materialization produced four canonical DSL
  definitions. Public `is_plan0013_semantic_region` checks in both role orders
  returned false, false, true, false by rank. CELL-3 PUSH/REACH_EDGE versus
  HOP/REACH_EDGE is in the protected old-six closure. The attempted CELL-4 also
  used HOP/CONNECT_EDGES instead of the contracted HOP/REACH_EDGE slot. Root and
  an independent review reproduced the public result and identified the drift
  without protected member access.
- **Decision for Plan29:** Its active contract required all four slots to pass
  that exclusion and prohibited a replacement slot. Close it in design stage as
  `OLD_SIX_OVERLAP / CELL4_SLOT_DRIFT / NOT_REGISTERED /
  PRODUCTION_COUNT_ZERO / NO_SELECTION`.
  Preserve the exact rejected proposal. Do not create a runner/test or execute
  any registered production game, exact solve, replay, selection AND/OR/BFS or
  full regression for Plan29.
- **Plan numbering consequence:** This is why the next research unit is Plan0030
  rather than an edited Plan0029. The old number preserves the failed question;
  it does not mean a game version or consume a retry allowance.
- **Plan30 repair:** Make static drafting an explicit bounded pre-freeze phase.
  Keep the unchanged HOP/CONNECT versus SWAP/CONNECT draft at rank1 and fix three
  new action/goal slots outside the old-six signature. Each open slot gets at most
  two source-only drafts and no selection computation. Only after all four pass
  public exclusion, D-055, legal goal/effect prefixes and resource proofs is the
  cohort frozen and registered.
- **Production boundary:** The later fixed cascade has at most56 attempts:
  16 short queries,32 T2/T3 games, four exact calls and four BFS prefixes. Add
  only one Plan-specific script/test and reuse accepted adapters. No per-game
  model, post-freeze substitution, backfill, outcome-based reranking, cap change
  or human-quality claim. A survivor moves unchanged to a separate Plan0031 only
  after Plan0030 technical acceptance also passes.

## D-062 — 2026-09-07 — Freeze the four-cell Plan30 cohort after static admission

- **Evidence:** Four exact canonical definitions passed primary and independent
  D-055/goal/effect lanes. Public old-six membership was false in both role
  orders for all four. An independent read-only comparison found no role-neutral
  action/goal collision within the cohort, Plans20–28 or Plan29 ranks2–4; only
  CELL-1's explicitly exempt unchanged Plan29 copy matched. CELL-2..4 passed on
  draft1, so their draft2 slots were never generated or inspected.
- **Bounded design accounting:** The22 primary/audit prefix replays consumed280
  transitions. No game, exact solve, selection AND/OR or reachable-state prefix
  was executed. The attempted-definition transition ceiling was1,376; the
  before-drafting Plan ceiling was48,272 under schema4's `max_plies<=1000`.
- **Decision:** Freeze the exact rank, four hashes,48 unique seeds, T2/T2 then
  T3/T3 policy order, five-stage cascade, thresholds and resource limits in
  `experiments/proposals/plan0030-four-structure-preselection-v0.json`. Do not
  replace, tune or backfill a cell after this point.
- **Next gate:** Implement only the Plan-specific script/test, review them
  independently, then register once from production count zero. Static admission
  proves decisive finite termination and bounded executability only; it is not
  fairness, difficulty, fun or human-play eligibility evidence.

## D-063 — 2026-09-08 — Close Plan30 and freeze one low-branching Plan31 candidate

- **Plan30 evidence:** The one registered production invocation ended exit0 with
  five short queries: four `UNKNOWN_CENSORED` at100,000 misses and one COMPLETE
  false at95,704;51 later slots were gate-closed and no game, exact, replay or
  BFS ran. Saved-only and closeout audits matched193 source pins,16 direct pins,
  114 publication hashes and all116 isolated/main files. The sole full regression
  passed1,403 tests in5,398.474s, `OK (skipped=2)`, exit0. Therefore Plan30 is
  technically `ACCEPTED` while its scientific result remains `NO_SELECTION /
  HUMAN_REVIEW_FALSE`; never rerun or supplement it.
- **Lesson and numbering:** Admission allowed `b=15`, whose untransposed depth7/8
  bounds are183,063,615 and2,745,954,240, far above the fixed100,000 cap. The
  four censors therefore exposed a protocol/resource mismatch before candidate
  comparison and are not quality evidence. Plan numbers denote chronological
  frozen research questions, not versions, retries, survivors or successes.
  D-061's conditional survivor branch did not open, but the next independent
  research unit still takes the unused number Plan0031; definition/protocol
  suffixes `v0`/`v1` remain separate.
- **Plan31 design decision:** Fix two existing-DSL structures, at most two
  data-only drafts each and no replacement/backfill. Require D-055, public
  history exclusion, live explicit goals/effects and all-reachable `b<=6` before
  production. A complete source proof of a simple universal strategy immediately
  rejects a draft and gate-closes remaining static replays. Of three attempted
  definitions, CELL-1 HOP/CONNECT versus MOVE_CAPTURE/ELIMINATE passed both
  static lanes at`b=5`; CELL-2 draft1/draft2 were rejected by universal A wins
  atply5/9. The fourth slot was never generated. Design-stage game, exact, solver,
  selection and BFS calls are0.
- **Frozen production question:** Carry only unchanged CELL-1 into exactly11
  slots: complete A7/B8 terminal-only queries at97,655/488,280 nodes; one exact
  probe at100,000 states; if and only if exact is UNKNOWN, four T3/T3 plus four
  T4/T4 games. Both roles must win, both roles must have explicit GOAL endings,
  and actual HOP plus actual capture must be witnessed from matching saved
  pre-action/action records. Short censor, draw, PLY_LIMIT, winnerless output or
  evidence drift is technical failure. Exact COMPLETE decisive is an easy-solve
  rejection; exact UNKNOWN is neutral unresolved evidence and only permits the
  diagnostic to continue.
- **Claim and execution boundary:** Static admission and later bounded policy
  mixtures do not prove fairness, general hardness, fun or replayability. Human
  rule-review eligibility requires all registered production gates, saved-only
  audit and one successful full regression. Implement only one Plan-specific
  runner/test using accepted adapters; no `src/`, DSL, agent or generic-platform
  change and no per-game model. Registration must occur once from production
  count zero before the only production invocation.

## D-064 — 2026-09-08 — Broaden discovery and plan a bounded improvement loop

- **User authority:** The user explicitly removes small boards and extreme rule
  simplicity as hard conditions, fixes mechanically asymmetric abstract games,
  and requests a thorough plan for system self-improvement and deeper human/AI
  division. An optional clarification received the explicit answer
  「引き分け禁止は維持したい」. D-055 remains mandatory for every legal play.
- **Product scope:** Mechanical asymmetry, deterministic perfect-information
  two-player play and finite single-winner termination remain fixed. Board size,
  rule count and extreme simplicity are design choices. Balance, practical
  solving resistance, depth and replayability remain objectives; no absolute
  AI-hardness or exact50/50 proof is required before exploratory personal play.
  Existing trivial-strategy proofs remain defects and UNKNOWN is never a
  quality certificate. This supersedes conflicting historical scope wording
  only for future work, not frozen tests/definitions/studies.
- **Diagnosis:** Plan24's final6/8 versus7/8 gate, Plan27's identical paired
  T3/T4 winner sequences and different thresholds, and Plan30's four short-query
  censors are distinct from the actual universal-win proofs in Plans21/23/31.
  No human replay-preference evidence exists. Treating all NO_FLAG/UNKNOWN
  records as bad-game labels would corrupt method improvement.
- **Current action:** Pause Plan31 before registration at production count zero.
  Preserve its statically admitted candidate without promotion or scientific
  rejection. A pre-registration metadata correction left its design-record pin
  inconsistent; freeze acceptance is incomplete. No runner, production game,
  solver call or regression is started by this strategic-planning checkpoint.
- **Proposed next approach:** Small representation/calibration work followed by
  at most three exploratory episodes, each at most12 new definitions from
  contrasting rule skeletons and at most2 personal trial candidates. Separate
  game development, evaluator/agent improvement and collaboration feedback.
  Compare one changed component against the old version at equal declared
  budget with fresh confirmation examples; failed or inconclusive improvement
  is not automatically adopted. Avoid per-candidate code and per-game LLM calls.
- **Human division:** The assistant owns routine implementation, proofs,
  diagnostics, bounded allocation and evidence. The user supplies taste and
  purpose through concrete examples, plus resources/permission decisions when
  needed. Personal playtesting is informative development, not a compulsory
  learning-curve study or a fairness/depth certificate.
- **Authority boundary:** The earlier D-058 separate-task limitation does not
  bar the newly requested method planning in this task. This decision records a
  plan, not implementation or experiment activation. Plan0032 is prospective
  only; no automatic continuation from a heartbeat. All old raw results,
  no-retry commitments, protected history regions and full-suite obligations
  for code changes remain unchanged.
- **Record:** See
  [the Japanese strategy, budgets and stopping criteria](reviews/2026-09-08-discovery-reset-and-human-ai-loop-ja.md).

## D-065 — 2026-09-08 — Start the approved bounded finite-space implementation

- **Authority:** The user replied 「それで続けて」 to D-064's strategy and
  bounded roadmap. Start implementation/calibration and the bounded next
  exploratory batch, not the superseded Plan31 protocol.
- **Scope:** Plan0032 is the sole active plan. Add only three isolated core,
  search and batch modules and their three test files. Historical Python,
  fixtures, definitions and raw outcomes remain unchanged. Stage0 has at most
  four active work hours/three work sessions and one separate full regression;
  do not silently expand its six-file/2,000-line scope.
- **Mechanics:** Two chosen implementation skeletons are asymmetric shape
  placement and unequal movement abilities with permanent origin closure.
  Each new definition explicitly says that an immobile player-to-move loses.
  Empty open capacity strictly decreases on every move, proving all-legal
  finite decisive termination for this closed grammar. No rule-level move
  limit, draw, arbitrary tiebreak or change to an old winner rule is introduced.
- **Evidence:** The first expression and fault-calibration examples do not
  establish game quality. A stage1 manifest must freeze at most8 definitions,
  source hashes, seeds, policy/proof budgets and schedule before discovery.
  Ordinary programs perform games/checks without per-game model calls.
- **Preservation:** Archive Plan31 as SUPERSEDED_BEFORE_REGISTRATION with its
  production count zero and metadata audit incomplete. This is not a scientific
  rejection of its unplayed CELL-1. Keep all prior no-retry commitments and the
  protected Plan13/14 boundary. No changes to the unrelated Site or dialogue.

## D-066 — 2026-09-08 — Accept Plan32 and end at a limited human handoff

- **Evidence:** The only full regression completed1,437 tests/5,386.118s/
  OK(skipped=2)/actual exit0. Independent saved-only acceptance matched190
  source pins,9 manifest pins,34 new tests and permanent log/receipt copies.
  Episode1 completed64 decisive games without game censor/draw/fallback;
 15 short queries completed false and1 stayed UNKNOWN. No rerun or extra game.
- **Decision:** Offer at most two optional unscored rules: TILE7/B-first first,
  TILE9/A-first as comparison. Both are exact registered wires with derived
  paper/terminal instructions and static handoff auditPASS. The new handoff
  readiness record is separate from immutable raw human flags and quality labels.
- **Limits:** No fairness, practical-depth, fun or human-UX certificate exists.
  The limited strategy review is not absence of optimal winning strategies;
 3-ply negatives are known calibration and policy-sensitive small samples are
  not balance proofs. Human trials0, requested time at most20 minutes.
- **Stop:** The autonomous unit is complete, with Plan32 retained as the active
  optional-feedback record. Both workers are finished and the existing same-task
  heartbeat was deleted through the app. Do not fill the pause with episode2,
  new infrastructure or automatic human/website work. Further direction can
  restart a bounded new unit; maximum3 episodes is not a duty to run them all.
- **Preservation:** Old studies/protected membership/raw results and unrelated
  work remain unchanged. See experiments/reports/0032-acceptance-and-handoff-ja.md.

## D-067 — 2026-09-08 — Verify the six cut-and-choose originals before engine work

- **Authority:** User requested ideas from the existing task
  `cut and chooseアブストラクト`. Read it without mutation and preserve its
  complete six-original source. This is a new bounded source-audit unit, not
  a request to remove D-055/D-064, rerun Plan32 or silently add rule repairs.
- **Evidence:** One exposed static diagnostic confirmed 分水嶺's explicit DRAW,
  欠片's24/24 component and total tie for either first proposer, and 国境's0:0
  on one equal-count setup allowed by its incomplete specification. Independent
  source/saved-command/output/witness audit PASS. These are possibility proofs,
  not samples, frequencies, optimal results or judgments of fun.
- **Decision:** Prioritize unchanged 架ける者、断つ者:16 vertices, all24 edges,
  fixed proposer/cutter and chooser/builder. Every legal play has a unique
  winner by12 rounds. A separately independently checked proof excludes all
  pre-fixed12-pair Cutter strategies; adaptive forced winner remains UNKNOWN.
  The other5 alternate shared roles. Do not treat phase differences alone as
  sufficient mechanical asymmetry or add a winner to score ties.
- **Alternatives:** Implement all six, repair the draw rules, or force-fit them
  to TILE/TRAIL. Rejected for this unit: all would change the original question
  and spend source/test effort before admission. Existing TILE/TRAIL lacks the
  proposal/selection controller and edge-connection state; no faithful adapter
  is presently implemented. A next unit should address only the24-edge rule.
- **Limits/reversibility:** Source and diagnostic documentation only, no code,
  new games, solver, enumeration, full regression or human trial.190 accepted
  Python pins remain identical. No extra campaign episode or scheduler.
  Revised rules may be proposed later as separate descendants with explicit
  provenance; never rewrite this original-source verdict. Strategy discoveries
  can change its unresolved status, not its preserved evidence.
- **Records:** Plan32 is archived as accepted with its optional TILE handoff
  preserved. Plan33 remains the sole current result/next-action record; see
  experiments/reports/0033-cut-and-choose-audit-ja.md.

## D-068 — 2026-09-08 — Implement one faithful adaptive cut-and-choose diagnostic

- **Authority:** 「どんどん進めて」 resumes the next small unit after D-067.
  Preserve all six original ideas and focus only on the unchanged16-vertex24-edge
  fixed-role graph. This is not authority for draw repair or a six-game framework.
- **Implementation:** Six isolated new core/search/proof-check/runner/test files,
  maximum1,800 lines and one4-hour development unit excluding machine regression
  wait. No dependencies, old-code edits, edge reduction or symmetry shortcut.
  A needs both responses to one offer; B needs a winning response to every offer.
  An independent checker reconstructs graph terminality and exact legal children.
- **Validation:** Four hand-solved nonterminal graphs plus separate rule-fault
  fixtures; no original play/solve in tests. Core owner focused ceiling2; main
  integrated ceiling3. Freeze after source review and run one mandatory full
  regression, recording actual exit; pending tests are not accepted evidence.
- **Prospective diagnostic:** One original initial-state adaptive query, registered
  from count0, with300,000 uncached round states,6,000,000 choice transitions,
  1,000,000 peak retained proof arcs,16 MiB total output and1,800 process-CPU seconds
  including extraction/checking/serialization. Charge temporary proof replies too.
  First exhausted limit UNKNOWN; external interruption failure/incomplete.
  No retries or outcome-guided extra capacity. A decisive result requires checked
  proof and technical acceptance, not a fairness/depth/fun assertion.
- **Alternatives and reversibility:** A broad DSL expansion, six original engines,
  self-play tournament or UI would spend effort before resolving the current
  strategy uncertainty. The new namespace is removable without changing prior
  definitions/results. Keep Plan32's optional TILE handoff and campaign budget;
  this one-rule diagnostic is not episode2 or a budget reset.
- **Next:** Review/freeze, one full regression and one pinned query, then accept
  saved results. No paid resource, publication, human study or automatic scheduler
  is created by this decision. Plan34 holds exact implementation and exit bounds.
- **Execution checkpoint:** The prospective/source/saved-result independent
  audits passed. One original query completed actual exit0 with UNKNOWN /
  PROOF_ARC_LIMIT,57,071 states/1,000,009 transitions/peak1m arcs/CPU6.545418s.
  Full suite remains pending. In response to the user's continuous-work intent,
  a same-task30-minute follow-up was subsequently created through the app to
  finish actual suite acceptance/failure, quiet while unchanged and self-deleting
  at completion. It authorizes no extra query, budget, source edit or research unit.

## D-069 — 2026-09-08 — Accept Plan34 technical evidence; preserve UNKNOWN

- **Evidence:** The one frozen full regression completed1,475 tests/5,385.538s/
  OK(skipped2)/actual exit0; all38 new tests are ok. Session completion, shell exit
  and final log agree. Independent saved-only audit PASS for current202 pins,
  old190 pins, six manifest pins, original chat/wire, registration and query
  result/receipt/log. Preserve permanent logs/exits and the new exit receipt.
- **Decision:** Accept the six-file implementation and this recorded execution
  technically. Close the bounded Plan34 unit without altering its original
  UNKNOWN/PROOF_ARC_LIMIT result. Keep it as the sole current result/next-action
  record until a separately scoped unit exists. No further computation is pending.
- **Limits:** The first exhausted resource was peak proof-arc retention, not a
  proved complexity property. No forced winner, fairness, practical-depth, fun
  or human-readiness certificate. No query retry, extra budget, policy games,
  repaired original rules, source/test changes or protected candidate access.
- **Follow-up:** Final closeout-record audit PASS, including all five permanent
  evidence copies and the new receipt/report. The app confirmed deletion of the
  same-task `parity-forge` heartbeat at2026-09-08T01:17:33Z. Its only purpose was
  this actual acceptance/failure; task and experiment evidence remain preserved.
  Do not launch a subsequent research unit or replacement scheduler. Existing
  TILE handoff and all old sources/fixtures/raw experiments remain preserved.
- **Future hypothesis only:** Separating cached values from evidence construction
  may merit a new bounded architecture experiment; not implemented, verified or
  authorized for automatic execution by this completion decision.

## D-070 — 2026-09-09 — Test a symbolic cut-potential proof method

- **Authority:** New user 「続けて」 after Plan34 acceptance. This is a separately
  scoped continuation, not an old-query retry or timer-authorized research.
- **Hypothesis:** An exact strict cut-potential B certificate can avoid expanding
  some winning subtrees and their retained evidence. Do not merely enlarge memory.
  Keep original24-edge definition, both roles, all offers and lexical DFS order.
- **Analytic basis:** For every inclusion-minimal original LR cut not hit by B,
  weight2^(-unresolved members). Each offer's two choice outcomes have average
  potential no greater than current potential. B can keep a value<1 below1;
  A victory would require a completed cut contributing1. Finite unique termination
  then forces B. Independently reviewed; no original calculation in this gate.
- **Rejected shortcut:** Two edge-disjoint spanning trees do not in general stay
  available after arbitrary offer/choice/delete. The two-K4 articulation example
  exposes that local invariant's failure, not a forced-winner result for this game.
  Literature on different Shannon/Picker-Chooser goals cannot substitute for proof.
- **Implementation:** Four isolated Python files, <=1,400 lines; preserve all
  accepted source and runs. Independently reconstruct cuts/minimality in checker;
  exact integer comparison, Phi=1 rejected; unchanged branch proof quantifiers.
- **Bounds and exit:** Same four known synthetic controls; source/focused review,
  one full regression; one freshly registered initial-game query with unchanged
  300k nodes/6m transitions/1m retained arcs/16MiB/1,800CPU-seconds ceilings.
  No additional candidates, tuning, query retry or extra capacity after result.
  COMPLETE requires checked proof; exhausted search UNKNOWN, never game DRAW.
  Record actual exits and interpretation without a fairness/depth/fun certificate.
- **Execution checkpoint:** Four files974 lines frozen,28 focused tests/OK/exit0;
  independent math/source/prospective/saved-result audits PASS. One query finished
  UNKNOWN/PROOF_ARC_LIMIT with229343nodes,1301149transitions,68218aggregate leaves,
  95cuts,peak1m arcs,CPU19.913648s. This method alone did not achieve resolution.
  Full regression45358 remains pending;206 pins/old202 preserved. The app created
  a finite same-task30-minute `parity-forge-plan35` follow-up for actual regression
  acceptance/failure only, quiet while unchanged and self-deleting afterward.
  It does not authorize another experiment, source edit, retry or budget increase.

## D-071 — 2026-09-10 — Accept Plan35 technical evidence; retain inconclusive result

- **Evidence:** One frozen full regression completed1,503 tests/5,374.197s/
  OK(skipped2)/actual exit0. All28 new tests ok; actual session response, shell
  marker and final log agree. Independent saved-only audit PASS for206 current
  pins,202 prior accepted pins, manifest7 pins, sourcechat/wire, registration,
  raw result/receipt and logs. Five permanent copies and new receipt/report
  passed final independent byte/hash/claim audit. No rerun or source/test edit.
- **Decision:** Technically accept the four-file cut-potential implementation
  and recorded execution. Close this bounded unit; keep Plan35 as sole current
  result/next-action record until a separately scoped unit exists. Preserve
  prospective and earlier pending checkpoints as history, not current status.
- **Scientific result:** UNKNOWN/PROOF_ARC_LIMIT remains unchanged. Aggregate
  68,218 potential leaves are not retained individual proofs or an initial B-win
  certificate. This shortcut did not resolve the original under the unchanged
  ceilings. More visited states and higher CPU do not establish efficiency;
  one query does not establish general effectiveness or game quality.
- **Boundaries:** No forced-winner/fairness/depth/fun/human-readiness claim,
  silent rule change, retry, budget increase, more boards, games, UI or protected
  candidate access. Prior Plan34 UNKNOWN, old sources/fixtures/runs and optional
  TILE handoff remain unchanged. Both Plan35 workers are finished.
- **Follow-up:** After final record audit PASS, the app confirmed deletion of
  `parity-forge-plan35` at2026-09-09T15:53:16Z. Only the completed follow-up was
  deleted; task and evidence remain. OpenAI Docs informed closure. No new research
  unit or replacement scheduler is launched by this completion.

## D-072 — 2026-09-10 — Continue through an actual private playable handoff

- **New authority:** User explicitly requests scheduled, energetic continuation
  until they can play. This supersedes old completion's no-next-unit boundary
  only by a separately scoped new Plan36, not by reopening closed experiments.
- **Decision:** Deliver the unchanged TILE7/B-first I/L trial, optional9/A, using
  the existing unpublished owner-private Site. Full exact winner resolution is
  not a gate for an honestly unvalidated short trial. Independent readiness review
  supports that limited handoff; it does not certify fairness, depth or fun.
- **Implementation:** Japanese touch/keyboard board, bounded local AI as either
  role and same-device2-player, shapes/preview/confirm, no-move-loses, reset, limits.
  No draw/pass repair, per-move model call or game upload. Online friends later.
  Source review found a cancellation boundary; synchronous cancellation plus
  current-state guard fixed it and passed follow-up review.
- **Evidence:**12 final Site tests PASS incl6 functional traces/107 transitions
  matching Python and actual worker bundle VM. Typecheck/build/actual exit0.
  Independent saved-only90Site/206Python pin and6copy auditPASS. Not new quality
  samples. Site commit9f5dcc8e0de21235f6bea191133ee1b456d35ab3 pushed and version1
  saved by actual root tools; independent audit did not separately query remote.
  Full regression78275/PID60198 running, not accepted or deployed yet.
- **Continuation:** Same-thread30-minute `parity-forge` ACTIVE, quiet on unchanged
  state. Advance through full acceptance, verified private deployment and actual
  URL/rules/limits handoff; do not stop at an intermediate test/plan boundary.
  Follow-up ends at usable delivery, user stop or documented outside-authority
  blocker. No infinite same-failure loop, paid upgrade, extra candidate search,
  public sharing, protected membership access or fabricated human feedback.

## D-073 — 2026-09-10 — Accept and deliver the private I/L trial

- **Decision:** Plan36 is COMPLETE / TECHNICALLY_ACCEPTED /
  PRIVATE_TRIAL_DELIVERED. The user can try AI as either side or shared-device
  two-player play at https://catch-and-jump.realnuun.chatgpt.site . The mandatory
  no-draw/mechanical-asymmetry conditions and both registered DSLs are unchanged.
- **Evidence:** One full regression1,503 tests/5,289.039s/OK(skipped2)/actual exit0;
  actual session78275, shell marker and log agree. Site12 tests/build/typecheck
  succeeded;6 complete functional traces/107 transitions are implementation
  checks, not fairness samples. Final independent saved-only audit PASS for8
  copies, receipt, current90Site/206Python pins, prior Python pins, DSLs and Site
  provenance. Frozen Site HEAD9f5dcc8e0de21235f6bea191133ee1b456d35ab3 is clean.
- **Deployment:** Root freshly verified owner-only access before deploying the
  same saved version1. Native status succeeded at2026-09-09T18:31:28.279853+00:00;
  exact response/URL retained in0036-private-deployment-receipt.json. Saved-version
  NOT_STARTED receipt remains historical. Independent review did not itself
  query the remote. No audience expansion, extra version or source edit.
- **Limits:** Clearly unvalidated human trial, not fairness/depth/fun/UX certified.
  Background Sites handoff returned exact URL without opening the user's browser;
  no browser/visual QA or actual human trial claimed. Online friends unimplemented.
  Local bounded AI makes no per-move model call or game upload. Old UNKNOWN and
  raw eligibility labels stay unchanged; no further solver or policy games.
- **Closure:** Japanese URL/rules/limits handed off. Following OpenAI Docs, the
  app confirmed deletion of `parity-forge` at2026-09-09T18:31:58Z; task/source/
  evidence remain. Dev server8279 stopped after hosting, actualexit0. No pending
  calculation, replacement scheduler or automatic next research unit. Keep the
  completed Plan36 as sole current record until a separately scoped next unit.

## D-074 — 2026-09-10 — Make game URLs login-free by default

- **Authority:** User explicitly requests「これからもURLはログインなしで遊べるURLにして」.
  Apply to the current trial and future playable game URLs. This supersedes the
  initial private-only game delivery boundary, not private research confidentiality.
- **Action:** Use the existing Site's native access control, custom to public;
  access revision2 at2026-09-09T19:25:40.762494+00:00, then native read-back confirms
  public. Keep version1, source and https://catch-and-jump.realnuun.chatgpt.site .
  No code, credentials, rules, build, deployment or administrative permissions change.
- **Verification:** Fresh Node fetch without cookies/authorization returns200 for
  the Japanese game page, its page JavaScript and stylesheet, no login redirect.
  Independent limited source review finds no app auth gate, game persistence or
  private-user-data read path; unused D1 scaffold does not certify remote DB empty.
  This is not a browser interaction test or new fairness/quality evidence.
- **Standing preference:** Deliver playable game links with anonymous access,
  no account requirement; verify unauthenticated access. Record in AGENTS.md.
  Do not publish private research/secrets or unrelated Sites, remove admin auth,
  recruit testers, restart experiments or create schedules under this preference.
- **Evidence:** experiments/reports/0036-public-access-receipt.json. Initial private
  deployment/acceptance records remain historical. No regression rerun is needed
  because accepted source and game code have not changed.

## D-075 — 2026-09-10 — Add login-free online friend rooms

- **Authority:** New explicit「友達とオンライン対戦できるようにして」plus D-074
  login-free delivery. Separate Plan37 extends the accepted trial, not research.
- **Scope:** Existing public Site, exact TILE7/B and9/A, AI/local modes retained.
  Anonymous room/invite/claim, D1-authoritative seats and move history, replay
  and legal/turn checks with atomic version updates. No accounts/lobby/chat/ranking.
  Strong random invite/seat capabilities separated and hashed in DB; no credentials
  in query/logs, seat credentials stored only device-locally for reconnect.
- **Boundaries:**24-hour validity,500 live-room cap, expired cleanup20 per creation.
  Physical deletion is gradual, not exactly at expiry. Expiry/disconnection is
  interruption, never a new winner/draw. New room for rematch; no opponent reset.
  Online persistence disclosed in UI; local/AI remains no-upload/no-model-per-move.
- **Evidence:** Final independent source review PASS after2 client lifetime/
  pending-claim repairs.28 final Site tests/typecheck/build actualexit0;
  local2-client HTTP2rooms42moves PASS. These are implementation checks, not game
  quality samples or browser/human UX evidence. Mandatory full regression80276/
  PID80326 still running once on unchanged206Python pins; do not claim accepted yet.
- **Publication preparation:** Sitecommit7642e98a4fafa30821ac4c2dbf5f9dd6d9e98f6e,
  103pins,19files786 additions25deletions, pushed actualexit0, saved version2 with
  bounded new D1 migration. Native DB overview found0user tables/no omissions.
  No deployment yet; preserve current working public1 until full acceptance.
- **Follow-through:** Per continued-delivery preference, OpenAI Docs informed
  same-task30-minute `parity-forge` tracking this one suite and publication only.
  Quiet on unchanged waits. After actual fullsuccess, deploy saved2 with Sites,
  verify terminal deployment and2own-room production flow without browser QA,
  deliver JapaneseURL/how-to, delete tracker and stop localdev52627. No source
  edits after freeze, old queries, new candidates, budget expansion, purchases,
  protected evidence access, outside tester recruitment or next research unit.

## D-076 — 2026-09-10 — Publish the validated online trial separately from research regression

- **Authority:** User explicitly requests「オンラインで公開して」after the saved-only
  checkpoint. Publish the existing public Site's frozen, tested version2 now.
- **Release boundary:** Final28 Site tests/build/typecheck, independent source/
  saved-evidence audit and local two-client HTTP flow passed. Python206 source
  files are unchanged from accepted Plan36. The one mandatory new full regression
  remains running; the earlier pass is not a substitute for its actual result.
  This supersedes D-075's ordering of publication after full research regression,
  not the requirement to finish and report that regression. Plan37 remains open.
- **Execution:** Fresh native Site read confirms owner/public/revision2. Deploy
  exact saved version2, verify actual succeeded and one bounded hosted two-room
  flow plus anonymous page. Do not change source, rules, audience or research.
- **Follow-through:** After publication, restrict the existing finite tracker to
  the remaining regression receipt/audit and final acceptance only. No redeploy,
  repeated hosted traces, new experiments or replacement tracker. Preserve the
  saved-only checkpoint and its NOT_STARTED receipt as historical evidence.

## D-077 — 2026-09-10 — Rules-and-code-only public analysis repository

- **Authority:** User requests a new GitHub repository for another person to
  analyze the game, explicitly excluding everything except rules and code, and
  confirms public visibility. Connected account is aaagamesnuun.
- **Boundary:** Export to an independent directory/repository, not this research
  repository's history. Include exact live game engine and both DSL JSON files,
  a derived rules/API README, runnable example and standalone test code only.
  No research reports, experiments, conversation, internal instructions, room
  data, credentials, hosting configuration or deployment identifiers. No license
  or external invitation is inferred. Source games and running regression unchanged.
- **Progress:** Local six-file preparation; creation currently needs browser
  GitHub login. No remote repo/upload has been made at this checkpoint. Existing
  finite automation remains regression-only and must not perform GitHub writes
  or mark the entire plan complete while this requested handoff remains pending.
- **Completed:** User logged in; root created public aaagamesnuun/catch-and-jump-analysis
  and uploaded exactly6 files via GitHub connector. Main581d9acebf5e6d8377953dc62b9847a68b3eefdc,
  two new commits, no original history. Exact3 engine/DSL copies, new8tests/example
  actualexit0. Remote tree6files/untruncated and anonymous raw6byte comparisonsPASS;
  GitHub UI confirms public/files/README. Local-only receipt0037-github-code-only-handoff.json
  is not uploaded. Pending full research regression remains separate.

## D-078 — 2026-09-10 — Accept Plan37 and close the finite regression follow-up

- **Evidence:** The single full regression80276/PID80326 completed1,503 tests/
  5,387.722s/OK(skipped2)/actualexit0. Actual session chunk1928bc, shell marker and
  log agree; PID absent.21:36:38Z is a completed-evidence observation, not end time.
  Independent final saved-only auditPASS:12 copies,206Python/103Site pins,
  frozen SiteHEAD/clean and saved/deployed/GitHub receipts all agree.
- **Decision:** Plan37 COMPLETE / TECHNICALLY_ACCEPTED / PUBLIC_ONLINE_DELIVERED.
  Public online Site and rules/code-only GitHub handoff were already complete;
  the deferred full regression now satisfies the final acceptance requirement.
  Preserve historical RUNNING/NOT_STARTED checkpoint receipts, immutable sources,
  experiments and outcomes. No new source, test run, policy game or remote query.
- **Closure:** Save0037-full-suite-exit-receipt.json and0037-acceptance-ja.md;
  delete only the completed `parity-forge` follow-up through the app using OpenAI
  Docs. Record actual deletion confirmation. Do not create a replacement timer,
  new research unit, expanded budget, redeploy, GitHub update or automatic trial.
- **Limits:** Technical acceptance is not fairness/depth/fun/human-UX validation.
  No-draw and mechanical-asymmetry requirements and exact game DSLs remain intact.
- **Actual closure:** At2026-09-09T21:41:04Z the app confirmed
  automationId=parity-forge/mode=delete/deleteStatus=deleted. Only this finite
  tracker was removed; task/source/evidence/public Site/GitHub are preserved.

## D-079 — 2026-09-10 — Resume bounded game discovery on an hourly heartbeat

- **Authority:** User requests continued game-idea exploration by recurring
  execution. This starts Plan38 and supersedes D-078's no-next-unit restriction
  for new research only; Plan37 remains accepted and archived without reruns.
- **Initial experiment:** Four new7x7 definitions: T4/L4 and O4/I4 with each role
  starting. Geometry (including tile area/orientations) is the changed component;
  existing policies, seeds, evaluator/search/proof budgets and source pins remain.
  Independent prospective auditPASS/validator actualexit0. Manifest SHA256
  77a30650c8c84dea5390d0f4eb3279923534798ebaf9524d45916d5bdf93f751.
  No gameplay or short-win query yet. All placements consume4empty cells, so every
  legal play ends within12placements; no-move loses, no draw/tiebreak modification.
- **Bounded loop:** Same-task hourly heartbeat, one bounded unit per activation;
  local programs conduct matches without model calls per move. Episode2 max32games,
  CPU14,400s/16MiB. Episode3 conditional on review and prospective registration,
  at most another32games/14,400s/16MiB, one changed component. At the campaign ceiling
  require explicit evidence/next-plan review, never bypass preserved episode claims.
- **Claims/cost:** Separate first-player and role effects and policy pairings.
  Mixed-agent50/50, limited short-win FALSE/UNKNOWN and software tests cannot certify
  fairness, depth or fun. Do not rerun unchanged full regressions for data-only
  experiments or repeat uninformative screens. Notify meaningful findings/candidates,
  completed block review, failures or required user choices, not unchanged ticks.
- **Scope:** Preserve source, previous results, public Site and code-only GitHub;
  no publication, private-research upload, old query retries, protected evidence,
  paid resources or automatic human trial. Record actual scheduler installation
  separately; preparing this plan alone does not mean the schedule exists.
- **Installed:** App native create returned automationId=parity-forge/status=ACTIVE;
  name「Parity Forge 新ゲーム探索」, hourly same-task heartbeat; subsequent native view
  succeeded, confirmation observed2026-09-09T22:02:53Z. This new research continuation
  is distinct from the deleted Plan37 regression tracker. No gameplay yet; next
  activation performs the audited episode2 preflight and one-time launch.

## D-080 — 2026-09-10 — Ban placement-exhaustion loss in future games

- **Authority:** User explicitly says「『最後に置けなかったほうが負け』というルール、
  面白くないから今後禁止にしてほしい。」Treat this as a hard product exclusion,
  not a low score that another search budget, tile shape or board size can repair.
- **Scope:** Exclude inability-to-place-causes-loss and equivalent last-placement-
  wins definitions from future discovery/improvement/recommendation. Placement
  actions themselves are not banned. Do not sidestep feedback by relabeling the
  same exhaustion mechanic as movement or silently reversing winners. Distinct
  capture/connection/arrival objectives need their own explicit all-play finite,
  unique-winner review; mechanical asymmetry and no-draw remain mandatory.
- **Immediate consequence:** Close/archive Plan38 as SUPERSEDED_BY_PRODUCT_EXCLUSION.
  Its32-game episode2 remains technically accepted; raw dispositions/false claim
  flags and all receipts stay unchanged. Cancel proposed stronger-search episode3
  before registration; unused32game capacity is not carried to a substitute run.
  Independent bounded source review confirms finite_space only supports
  NO_LEGAL_ACTION_LOSES; no old TILE/TRAIL continuation is a compliant default.
- **Continuation:** Plan39's first unit is at most3 distinct objective-based
  sketches plus one independent design review, no matches/proof-search/engine
  change. Select at most1 for a separately preregistered bounded next unit. Update
  existing hourly same-task heartbeat, preserving ID/frequency/target/notification
  preference; no duplicate timer or broader resource authority.
- **Preservation:** User preference is not empirical proof of unfairness or a
  retroactive change to game semantics. Keep old engines/DSLs/tests/experiments and
  the public Site/code-only GitHub intact. Withdrawal or replacement publication
  is not requested. No rerun of finished99989 or unchanged full regression.
- **Applied:** Native update confirmed `parity-forge` ACTIVE, observed
  2026-09-10T00:21:00Z. Saved name/hourly recurrence/same target/original creation
  timestamp preserved, no notification override. Prompt enforces D-080 and Plan39;
  OpenAI Docs informed updating the existing same-task continuation, not a new timer.

## D-081 — 2026-09-10 — Select one connection-objective draft after bounded review

- **Evidence:** Plan39 produced2fixed sketches and used its one independent
  design review, with0games/search/engine changes. Draft SHA256
  3f7d7cf470dfe8ba4aec462423ddd9e3410631c07dd59d422f5e2f9cc1b7ffdc.
  「架橋と転色」passes structural asymmetry/D-080/finite unique-termination review;
  Hex coloring theorem plus strict empty-cell decrease, not a last-placement rule.
  「突破と迎撃」fails by the explicit row2 guard-wall/oscillation B strategy.
- **Decision:** Select only the connection draft for the next registration;
  do not repair the rejected draft or generate another sketch. No fairness,
  depth, fun, novelty or human-ready claim. Standard Hex strategic results are
  not transferred. Detailed reasoning/source:0039-objective-design-review-ja.md.
- **Next ceilings:**≤6newPython files,3integrated focused invocations, one required
  postfreeze full regression; one diagnostic≤16games/14,400CPU seconds/16MiB,
  perdecision32,768transitions/depth3/pergame3m, zero initial exact queries.
  Same9x9 rule/resources with initial A/B separately registered. DSL/evaluator/
  schedule/source pins are pending; no implementation or run before registration.
  Preserve all old engines/runs/claims and public Site/GitHub; no timer change.

## D-082 — 2026-09-10 — Accept the bounded connection baseline registration

- **Evidence:** Prospective Plan40 registration and implementation contract
  independently audited PASS. Exact hashes and static acceptance are recorded in
  `experiments/reports/0040-registration-ja.md`. Old206 pins and Plan38 results
  unchanged; new6source files and fixed claim/output absent. No code/test/game/
  proof-search execution in the registration-only activation.
- **Decision:** Complete/archive Plan39 and activate Plan40 as
  REGISTERED_NOT_IMPLEMENTED. Keep the selected9x9/A3/B2 connection rules; only
  initialA/B changes across two conditions, eight games each. Freeze evaluator,
  deterministic policies, schedule, full-root tie semantics and cost accounting.
  Preserve all D-081 ceilings. Registration is not an executable source manifest.
- **Sequence:** Six-file implementation, focused acceptance, independent source
  review/freeze, old206 pin verification and one mandatory full regression with
  actual exit. Only then seal unchanged registration plus source hashes separately
  and execute the single16game cohort; preserve failures/UNKNOWN without retries.
  Saved-only information review ends the finite unit. No quality/public promotion.
- **Efficiency:** Preserve entire former state/backlog in dated byte-identical
  checkpoints and keep routine startup records concise. This reduces redundant
  recurring context, without deleting experiment evidence or reopening old tasks.
  Hourly same-task continuation remains unchanged; latest Plan40 next unit replaces
  its historical Plan39 starting step. No UI/Site/GitHub or resource expansion.

## D-083 — 2026-09-10 — Freeze the connection implementation and start one full regression

- **Evidence:** Six isolated new Python files implement the registered core,
  deterministic baseline agents, sealed runner and independent prefix replay.
  Focused1 passed48tests; review found inherited CPU hard limits could interrupt
  below the cooperative deadline. Rejecting low hard limits before claim plus
  a mock fixture fixes this without changing rules, policies or registered caps.
  Focused2 passed49tests/0.129s/actualexit0. Final independent source/hash auditPASS,
  old206 pins and frozen registration/contract intact. Six hashes are preserved
  in `experiments/reports/0040-source-freeze.json` and its pin file.
- **Decision:** Freeze all six files and start the one mandatory full regression,
  not the scientific cohort. Session54037/shell13614/Python13615 observed running
  at2026-09-10T08:22:57Z. Preserve its launch receipt and exclusive log/exit files.
  The next activation follows the same worker; no extra suite or source change.
  An actual exit/summary/source recheck is necessary for a separate acceptance.
- **Boundary:** Ledger focused2/3, full1/1, claims0/1, scientificgames0/16,
  exactqueries0. No executable manifest yet; no quality or human-ready claims.
  Existing hourly continuation unchanged. Public Site/GitHub, historical source/
  results, D-055/D-080 and all earlier no-retry restrictions remain intact.

## D-084 — 2026-09-10 — Accept Plan40's completed full regression

- **Evidence:** The single full regression54037 completed1552tests/5382.233s/
  OK(skipped2)/actualexit0, tool completion chunkc9f5f0. Log and exit file agree;
  shell13614/Python13615 absent.10:27:48Z is a saved-evidence observation, not a
  claimed process end time. Old206/new6 pins and frozen inputs are unchanged.
  Independent saved-evidence auditPASS and runner validate_acceptance actualexit0.
  Completion receipt SHA256
  6140a5aa9da14c5048ef8adb7003690272e74562e3d45ebad0a0d2e5f78bd78f.
- **Decision:** Plan40 implementation/technical acceptance unit is complete;
  the plan remains ACTIVE / TECHNICALLY_ACCEPTED_DIAGNOSTIC_PENDING. Preserve the
  historical launch/freeze receipts, source pins and logs. Do not re-poll/restart
  the completed worker, consume unused focused capacity or change frozen code.
  Next activation may seal and launch the exact single preregistered cohort.
- **Boundary:** This saved-only activation added no tests, policies, games, exact
  queries, executable manifest or claim. All fairness/depth/fun/human flags stay
  false. Budgets remain focused2/3, full1/1, claims0/1, games0/16. No automation,
  Site/GitHub, public-research upload, resource expansion or old-evidence changes.

## D-085 — 2026-09-10 — Seal and launch the one registered connection diagnostic

- **Evidence:** Read-only preflight PASS, seal CLI actualexit0, independent sealed
  input auditPASS. Manifest SHA256
  bc7a10e72a9f19ea8e95807ddeb76e02a06aa2f745b0cdf54a9415987e4c420a
  binds unchanged preregistration, six frozen sources and actual full-regression
  receipt6140a5aa9da14c5048ef8adb7003690272e74562e3d45ebad0a0d2e5f78bd78f.
  Fixed16games, policies/seeds/first-role conditions/limits and paths unchanged.
- **Action:** Launch the sole worker session29306/shell29458/Python29459 once.
  At2026-09-10T11:43:48Z the process is live, claim1/1 confirmed, saved registration
  byte-matches the seal. No saved game records/final runtime/failure at that initial
  observation. Preserve `0040-diagnostic-launch-receipt.json` as RUNNING history.
- **Continuation:** Follow this same worker once per wake; never reseal, duplicate,
  tune, retry or change sources while running. CPU14,400s/16MiB, decision32,768
  transitions/depth3/game3m remain fixed. Preserve UNKNOWN/partial/failure, obtain
  actual exit separately and perform only the registered saved-result review.
- **Boundary:** This activation adds no code, tests, exact queries, public/remote
  changes or timer edits. Old206/new6 sources, historical outcomes and public
  game/GitHub remain intact. Claim1/1 is consumed; all quality/human flags false.

## D-086 — 2026-09-10 — Prepare a separate system/context handoff for teammates

- **User request:** Share Parity Forge itself on GitHub, including intent,
  philosophy and trial-and-error, so members and their Codex agents can understand
  and work with the system. This differs from the earlier code/rules-only game
  repository and explicitly authorizes selected research-context sharing.
- **Scope:** Fresh-history snapshot of source/tests/research scripts, selected
  static fixtures, proposals and human-readable documentation/reports. Add
  Japanese onboarding, a code map, evidence boundaries and a copyable first task.
  Preserve raw experiments, protected Plan13/14 evidence, original Git history,
  credentials, host receipts, running-worker outputs and Site state locally.
  Record source/export hashes and any document-only redaction. Do not silently
  call the portable subset a complete independently reproducible research archive.
- **Collaboration:** A cloned state/plan is a checkpoint, not authority to duplicate
  a worker, schedule or one-shot claim. The owner allocates task scope and new
  experimental IDs. Unchanged-code synthetic portability tests do not consume or
  re-open the frozen Plan40 scientific/acceptance ledger.
- **Access checkpoint:** Private repository proposed by default pending user
  visibility choice. GitHub owner authentication succeeded, but new-repository
  creation returned403 for insufficient permission. The user was asked to create
  an empty separate repository and provide its URL. No system upload or repository
  creation completed at this checkpoint; no access invitations or license chosen.
- **Preservation:** No frozen Python, DSL/input, raw result, source-history commit,
  current diagnostic worker, automation, existing Site or six-file game repository
  is changed by this documentation/export task.
