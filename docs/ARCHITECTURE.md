> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Architecture

## Data flow

```text
bounded FamilySignature + name-separated registry records
  -> schema-v4 parser, engine semantics, and pure compiler
  -> provisional search envelope + reconstructable definition derivation
  -> outcome-free census and work proofs
  -> frozen registry + common-support envelope
  -> authenticated definition-identity history projection
  -> first-player-paired D4 universe
  -> disjoint development/candidate selection
  -> synthetic evaluator conformance + common agent ladder
  -> frozen evaluation protocols
  -> outcome-free immutable development manifest
  -> versioned JSON definition
  -> schema parser and validator
  -> canonical serializer + content hash
  -> deterministic engine
  -> cheap static diagnostics
  -> replay-derived agency and interaction telemetry
  -> progressively stronger agents/evaluators
  -> repeatable immutable development record
  -> fresh one-shot confirmation, if preregistered signal exists
  -> curated candidates and later human evidence
```

## Boundaries

- `dsl.py` owns typed, immutable definitions, parsing, validation, canonical JSON,
  and hashing. It never executes user-supplied code.
- `engine.py` owns immutable states, canonical actions, legal-action enumeration,
  transitions, terminal detection, and replay.
- `analysis.py` owns static diagnostic passes. It may reject cheaply but may not
  change game semantics.
- `simplicity.py` owns separate structural, description, and operational metrics.
- `generator.py` proposes definitions but never judges them; `landscape.py` owns
  outcome-blind exhaustive census and deterministic stratified selection.
- `symmetry.py` owns supplemental D4 orbit identity without changing DSL hashes.
  Its public `transform_position` is the single coordinate-level D4 authority
  shared by definition transformation and high-volume census reconstruction.
- `four_by_four_calibration.py` owns Plan 0011's pure exhaustive 4×4/max-8 census,
  authenticated closed-history projection, definition-only gates and strata,
  deterministic selector, manifest reconstruction, and structural state proof. It
  has no solver, sampled-play, filesystem, Git, reservation, or clock edge.
- `four_by_four_evaluation.py` owns Plan 0011's pure fixed exact schedule,
  manifest-bound slot and PV reconstruction, label coverage, exact summaries,
  timing-free evidence seal, and complete inspection. Its public executor fixes
  the exact solver and state cap; filesystem, Git, reservations, locks, and
  one-shot failure persistence belong to a later experiment boundary.
- `four_by_four_depth.py` owns Plan 0011's pure fixed depth-5 schedule and public
  raw-result reconstruction. Its public executor fixes the agent, depth, seeds,
  per-definition cumulative node cap, and fresh-agent lifecycle; it retains every
  completed trace and node delta or the next censored prefix, then rebuilds
  transfer confusion, exact-draw errors, breakdowns, assessment, timing-free seal,
  and complete inspection. It has no filesystem, Git, reservation, lock, or
  one-shot artifact capability.
- The three Plan-0011 pure modules above are preserved, dormant audit
  infrastructure after `SUPERSEDED_PRE_OUTCOME`. No production Plan-0011
  membership, evaluation, reservation, or outcome exists, and no one-shot edge is
  an active architectural dependency.
- Plan 0012 reserves `family.py` for the finite, callback-free ludeme-level
  `FamilySignature`, name-separated records, ordered registry artifacts, and
  canonical family identity. Setup and parameter domains belong to a separately
  versioned search envelope. A provisional reconstruction witness is added after
  schema v4 and its pure compiler exist so feasibility can inspect definitions;
  the final envelope and registry are frozen only after that census. None replaces
  the authoritative `GameDefinition`, exact DSL hash, or D4 hash.
- `feasibility.py` owns Plan 0012's provisional 3×3 setup/domain descriptor,
  deterministic 214,368-input enumeration, six-cell schema-v4 compiler,
  reverse family projection, exact and D4 identities, reconstructable derivation
  witness, and action-specific structural state/work bounds. It depends only on
  DSL, family identity, and symmetry; it cannot apply actions, inspect gameplay,
  call an agent or solver, or compute an outcome. The module does not freeze a
  final family registry, search envelope, census result, or atlas.
- `feasibility_census.py` owns Plan 0012's outcome-free initial-position census.
  It compiles all 214,368 provisional inputs, measures both roles' initial goals
  and legal actions, applies the versioned connection-material and symmetric
  mobility gate, records absolute density/action/state/work distributions, and
  counts exact and D4 populations globally, by family, and by stratum. It binds
  the ordered case-to-orbit relation, complete rejection-reason combinations,
  sorted orbit witnesses, and every retained aggregate to canonical roots. The
  optimized identity path reuses public D4 position transformation and is
  checked against the authoritative one-case compiler/hash path on a fixed
  391-case schedule spanning all 176 strata; all 1,714,944 transformed initial
  measurements are verified. It never applies an action, constructs a terminal
  result, calls an agent or solver, or selects a gameplay atlas.
- `atlas_projection.py` is the capability boundary between outcome-bearing source
  records and Plan 0013 selection. It accepts only closed exact/D4 identity
  carriers with authenticated source metadata, validates strict detached JSON,
  and emits canonical identity-only projections. It cannot read artifacts,
  definitions, results, traces, agents, or outcomes.
- `atlas_history.py` owns the cutoff-fixed Plan 0013 source adapter. It
  authenticates the exact 66 JSON blobs at commit `6910b6c`, scans every nested
  value without consulting result status, and projects only definition exact/D4
  identities plus source counts and attestations. The seven Plan-0012 synthetic
  telemetry definitions cross a separate projection root. Ambient discovery,
  filesystem access, solver/play, and selection remain outside this module; raw
  bytes must be supplied explicitly by the experiment edge.
- `atlas.py` owns the pure Plan 0013 registry, common 3+3 envelope, exhaustive
  first-player-paired universe, 2+2 deferral proof, history collision classes,
  and deterministic development/candidate partition. Pair identity binds the
  name-free family signature, neutral mechanics, ordered A/B D4 identities,
  exact A/B setup correspondence, all eight representative orientation hashes,
  multiplicity, and structural proof. Ranking cannot depend on display names or
  history. Production APIs accept only the reviewed frozen projection roots;
  generic collision construction is review-only. The module imports no solver,
  sampled agent, play, replay telemetry, experiment, or outcome layer and cannot
  create gameplay evidence.
- `terminal_search.py` owns `terminal_only_minimax-v1`, a family-neutral
  full-width search separate from the historical goal-progress minimax. It uses
  A-relative terminal utility `+1/0/-1`, exact zero at every nonterminal cutoff,
  A=max/B=min, canonical legal actions, a per-selection transposition cache, and
  seeded tie-breaking only when more than one best action remains. Root states
  are uncharged; successor cache misses consume one cumulative per-slot node.
  Schema-v4 definitions, states, actions, RNG, identity, depth `1..64`, and
  budget fields are exact-typed and fail before RNG or node work when invalid.
- `atlas_agent_benchmark.py` owns the frozen Plan-0013 synthetic evaluator
  boundary. It reuses four Plan-0012 telemetry definitions by direct exact/D4/
  byte identity and projection-root checks, adds one disjoint SWAP/CONNECT
  fixture, and proves D4-invariant separation from the selected atlas before any
  solve, search, or play. Forty D4 exact/search slots plus 320 random and 320
  terminal-only complete-game lifecycle probes cover all five active action
  kinds, all three goals, terminal priority, A/B/draw, cutoff, B minimization,
  cache, tie, and cumulative per-role budgets. The production ladder contains
  only `random-v1-weak` and `terminal_only_minimax-v1-depth1`; depth 2 is a
  conformance diagnostic. Exact scalar values are D4-invariant and per-action
  values transform covariantly, but seeded coordinate-ordered tie selection is
  not itself D4-equivariant, so production retains all eight orientation slots.
  The module imports atlas identity/count roots but no selected definition, and
  records zero production definition access/outcomes.
- `agency.py` owns pure replay-telemetry-v1 reconstructed from an authoritative
  schema-v4 definition and one retained complete action trace. It snapshots and
  reparses the definition, freezes action, goal, terminal, effect-mode, outcome,
  and direct-effect vocabularies, evaluates every legal one-ply alternative
  exactly, and reports role-separated branching, forced play, realized effects,
  immediate outcome sensitivity, exact next-player legal-action-set sensitivity,
  immediate reconvergence, repetition, terminal, and work evidence. These
  dimensions remain separate; the module owns no scalar agency score, agent
  policy, solver, game semantics, selection, threshold tuning, or trusted result
  summary.
- Replay telemetry is bounded at 1,000 retained actions, 200 legal actions per
  decision, 200,000 counterfactual successors, and 40,000,000 observed next
  actions. Stored validation accepts only an exact JSON object, with at most
  1,000,000 nodes and depth 32, rejects cycles and non-finite or non-exact values,
  seals untrusted evidence before caller-owned definition code can run, rebuilds
  the complete result, and reseals both inputs. Incomplete traces, actions after
  terminal, vocabulary drift, horizon overflow, and any reconstructed-byte
  mismatch fail closed without returning partial telemetry.
- The code-native synthetic benchmark freezes seven schema-v4 definitions and
  complete traces, each definition/trace/evidence digest, and ordered benchmark
  root `6789f97e7f0948df9fa66f75933c061a08e029ce49e9d9da33ae57a7b4a59a33`.
  Its zero-action stuck, CONVERT reconvergence, PUSH next-legal sensitivity,
  actor-relative win/draw/loss, MOVE_CAPTURE/ELIMINATE one-sided effect,
  both-role SWAP repetition, and HOP dependency-without-effect fixtures are
  calculation oracles. D4 and role-swap metamorphic checks test invariance. The
  benchmark is not a corpus of played games and calibrates no universal agency,
  interaction, strategic-quality, or fun threshold.
- Schema-v4 parser, canonicalization, prose, D4, simplicity, legal-action,
  transition, and terminal changes remain within their existing owning modules.
  `PUSH`, `SWAP`, `HOP`, `CONVERT`, and `ELIMINATE` are strict occupancy-only
  extensions that do not change schema-v1/v2/v3 bytes or behavior.
  The provisional `CAPTURE_STEP` token is not executable: its proposed optional
  step-or-capture contract is exactly the already-supported `MOVE_CAPTURE`, which
  schema v4 reuses rather than duplicating under a second name.
- The first schema-v4 checkpoint implements only the cross-role terminal contract
  and `PUSH`. Direct v4 construction and canonical identity boundaries require
  parser-normalized exact types; recorded pushes retain only from/to coordinates,
  and the engine derives the displacement from the definition and current state.
  D4 transforms every declared PUSH vector, while simplicity reports PUSH as an
  ordinary relocation plus a distinct primitive, conditional special form, and
  additional state-transition substep; it reports the v4 terminal-priority
  contract separately from that action cost.
- The second schema-v4 checkpoint adds `SWAP` as ordinary adjacent relocation or
  exchange with one adjacent opponent, with no friendly, ranged, or multi-piece
  exchange. Recorded actions remain `kind/from/to`; the engine derives the effect
  from the definition and state. Schema v4 admits the historical action kinds plus
  `PUSH` and `SWAP` but requires at least one of those v4-only action kinds. D4
  transforms SWAP vectors, and simplicity charges its shared primitive, per-role
  conditional form, and extra transition substep.
- The third schema-v4 checkpoint adds `HOP` as ordinary adjacent relocation or a
  jump over exactly one adjacent occupied piece to the empty cell one more step
  along the same declared vector. The jumped piece is unchanged regardless of
  owner or kind; chains, occupied or off-board landings, and jumps over empty
  cells are illegal. The recorded `to` is the actor's final landing cell, while
  replay derives the intermediate cell from `kind/from/to`, the definition, and
  state. Schema v4 now requires at least one `PUSH`, `SWAP`, or `HOP` role. D4 and
  simplicity use the same explicit vector and conditional-special accounting as
  the earlier v4 movement actions.
- The fourth schema-v4 checkpoint adds `CONVERT` as a vector-bearing but
  non-moving action. One matching owned actor stays in place and changes one
  adjacent opponent target, of any kind, into an actor-owned piece of the
  action's declared kind at the same target cell. Empty, friendly, ranged, and
  multi-target conversion is illegal. Recorded actions remain `kind/from/to`;
  no target kind or effect is stored. D4 transforms declared CONVERT vectors,
  while movement-only analysis excludes CONVERT. Simplicity charges CONVERT as
  one standalone shared primitive with two action substeps and no conditional
  special form. At that checkpoint schema v4 required at least one `PUSH`,
  `SWAP`, `HOP`, or `CONVERT` role; the later ELIMINATE checkpoint broadens
  admission without changing those definitions.
- A pre-implementation alias audit rejects `CAPTURE_STEP` as a DSL addition.
  Under the proposed contract it has the same legal-action relation, transition,
  action record, D4 action, and schema-v4 terminal behavior as `MOVE_CAPTURE`.
  Adding a second executable DSL `ActionKind` would therefore create false
  family, DSL, D4, asymmetry, simplicity, and census distinctions from a spelling
  difference. The historical
  family-signature-v1 proposal token remains readable for identity compatibility,
  but the provisional capture cells and future compiler use `MOVE_CAPTURE`.
  `validate_nonretired_family_signature` and
  `validate_nonretired_family_registry` are the mandatory fail-closed entry for
  any future active compiler or final-registry builder. They exclude retired
  identity tokens only; DSL compilability and schema admission remain separate
  compiler checks. A separately packaged capability-minimal compiler that cannot
  import the frozen eager legacy package may instead consume a sealed vocabulary
  whose complete finite set is exhaustively and bidirectionally checked against
  these validators in tests. It may not use an unsealed duplicated allow-list or
  broaden the accepted set at runtime.
- The fifth schema-v4 checkpoint adds the non-spatial `ELIMINATE(piece)` state
  goal. It is true exactly when the opponent owns no piece of the declared kind;
  zero initial targets are intentionally a goal and must be excluded later by
  generator feasibility rather than hidden DSL state. Schema-v4 admission now
  requires at least one v4-only action or one ELIMINATE goal. D4 leaves the goal
  unchanged, simplicity counts one shared goal primitive, and static analysis
  permits an unsatisfied goal only under a `MOVE_CAPTURE` or `CONVERT` role with
  a matching initial owned action actor. Existing goal-progress-v1 agents reject
  any ELIMINATE definition before applying an action, consuming RNG, or spending
  search nodes; no uncalibrated elimination heuristic is implied.
- Plan 0012 feasibility construction owns setup descriptors, bounded enumeration,
  D4 identity, initial-state gates, family census, and state/work proofs, with no
  gameplay access. Plan 0013 now owns historical exclusion and outcome-blind
  selection. Its later separately reviewed slices own evaluator calibration,
  fixed schedules, deterministic budgets, raw traces, telemetry reconstruction,
  censoring, assessment, and inspection.
- Future-facing evidence utilities may own canonical JSON, exclusive writes,
  reservations, attempts/failures, paths, byte seals, executable fingerprints,
  and ancestry for new experiments. Historical experiment validators and frozen
  artifacts are not migrated onto those utilities.
- Agents choose from engine-produced legal actions but never alter rules.
- `landscape_evaluation.py` owns raw exact routing, draw stress, and the frozen
  inspection selection; `landscape_experiments.py` owns their evidence chain.
- `stalemate.py` owns the pure paired-manifest, v1/v2 comparison, adaptive
  stalemate-draw stress, assessment, and inspection logic. Its public validators
  reconstruct completed evidence without solving games.
- `stalemate_experiments.py` owns the paired experiment's historical source pins,
  Git and byte attestations, one-shot reservations, phase boundary, and immutable
  attempt/result/failure records. It must validate the complete v1 replay before
  allowing the first v2 evaluation.
- `capture.py` owns pure schema-v1/v3 pairing, replay attestation, capture-trace
  reconstruction, paired and stress assessment, deterministic selection, and the
  public validators that reconstruct completed evidence. It performs no filesystem,
  Git, reservation, or clock I/O.
- `capture_experiments.py` owns the capture experiment's historical source pins,
  executable and artifact fingerprints, Git/byte attestations, one-shot
  reservations, ordered phase boundaries, and immutable attempt/result/failure
  records. It delegates scientific construction and validation to `capture.py`.
- Experiment runners pin component versions, seeds, configuration, and results.

The capture evidence chain has three separately reserved, one-shot stages: freeze
the treatment-outcome-free paired manifest and commit it; run the complete pinned
v1 replay before any v3 treatment and commit the raw paired record; then, only when
that raw record seals an eligible adaptive disposition, run and commit the
interaction-stress record. Each downstream stage re-reads and validates the pinned
upstream bytes, fingerprints, ancestry, and reservation before computation. A
failure produces permanent failure evidence rather than skipping, replacing, or
combining a stage.

The engine is a pure state transition system. Ordering is canonical everywhere
observable so a definition plus move sequence produces the same state and hash
on every run.

Future broad-family work has two distinct evidence modes. Development runs are
repeatable only through new versioned protocol IDs: every run is immutable,
uniquely identified, and retained, but it is not held-out evidence. Confirmation
is a later separate one-shot protocol justified only by development evidence.
Plan 0012 implements neither gameplay mode.

## Evaluation cascade

Static definition checks precede initial-state diagnostics, random play, heuristic
play, search, solver diversity, strategic diagnostics, and human testing. Expensive
discovery stages normally receive only survivors. Separately declared audit lanes
may route all frozen cases independently of gates so evaluator errors and censored
regions remain visible. Generator and evaluator changes are measured in separate
experiments against frozen counterparts. A future family pilot may match nominal
case and compute exposure, but must still report family-specific branching,
state-space bounds, work, D4 policy, and censoring. Agency, interaction, exact
value, play shape, simplicity, and novelty remain separate evidence dimensions.
