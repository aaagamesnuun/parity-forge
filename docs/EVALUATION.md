> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Evaluation contract

Evaluation follows the charter's lexicographic order. A single weighted score
must not allow complexity or richness to compensate for invalidity or unfairness.

## Current mandatory gate — no draws (D-055)

User confirmed 2026-09-05: every legal play of an admitted game must terminate
in finite play with exactly one A/B winner. A reachable draw or nonterminating
continuation violates this requirement, even if other or optimal play is
decisive. A sampled zero draw rate or a decisive minimax value is not proof of
this universal condition. Require a sound termination/terminal-outcome argument
or a complete bounded verification before qualification; unknown is not pass.
Search-budget censors remain UNKNOWN, never draw/win/loss substitutions.

This is the product contract for future evaluator versions, not a claim that
frozen executable gates have already been changed. Historical draw-rate gates,
DSLs, calibration draws and raw labels below remain documented as originally
run and cannot override this new admission condition. Preserve them as evidence.
Do not reject exact A_WIN/B_WIN merely for being a forced result: no-draw finite
deterministic perfect-information games necessarily have a forced winner under
optimal play. Finite-skill fairness and trivial forced strategies are separate.

## Practical solving resistance and bounded verification — D-057

User clarified 2026-09-05: simple rules must retain computational complexity
beyond easy complete AI analysis. This adds a product-complexity screen; it
does not turn a forced winner into evidence of unfairness or alter frozen runs.
Before the next experiment, specify the reference solver(s), positive state/
node limits, operational time/memory limits and precise success target. Initial
position game-theoretic value is distinct from solving every reachable state
or exporting a complete contingent strategy; one PV is not that strategy.

- A correct exact result obtained within the registered easy-solve allowance
  rejects that definition as TOO_EASILY_SOLVED under this prospective screen.
- Exhaustion remains UNKNOWN/UNRESOLVED_WITHIN_BUDGET, not difficulty-pass.
  Exceptions, invalid inputs or broken/weak solvers must not earn quality credit.
- Check short rule-level winning arguments and meaningful contingent choices
  separately; a large tree can still have a simple strategy. No unbounded retries.
- Prove all-legal finite decisive termination structurally where possible.
  Proving that play ends need not require computing who wins from the start.
- Retain fairness, meaningful asymmetry, simplicity and later human evaluation;
  solving resistance alone does not establish an enjoyable game.

These labels and orchestration limits are a future evaluation contract, not
implemented fields in the current frozen evaluator. Existing solve_game defaults
to unlimited states; a future common entry point must require an explicit
positive allowance rather than relying on that default.

To assess a search method, compare it with a frozen baseline using the same
allowed definition space, evaluator/agents and fixed resource accounting.
Report unique eligible candidates, rejection causes, surviving choice evidence,
unresolved cases, compute cost and model-intervention cost separately. A higher
timeout rate or a method's own score is not an improvement. Numerical budgets
and comparison thresholds must be fixed before new outcomes, not invented here.

Keep per-candidate execution LLM-free. Bound candidate attempts, games, solver
work and outer review rounds; save detailed logs locally and expose compact
summaries or selected failures to the model. Exact token metering/enforcement
is not yet implemented; review-call limits are not a guaranteed token quota.

## Required result dimensions

- validity and named failure categories
- A wins, B wins, draws, samples, uncertainty interval, average length
- agent family/version, strength/budget, role configuration, and seeds
- mechanical asymmetry dimensions rather than names or colors
- structural, description, and operational complexity separately
- strategic diagnostics and evaluator disagreements

Fairness uses decisive win share and uncertainty while draw rate remains an
independent gate. Measurements at weak strength cannot establish balance at
stronger strength. Agent changes are evaluated on a frozen corpus; evaluator
changes on a frozen candidate corpus; generator changes under a frozen evaluator.

## Initial simplicity model

The first model is deliberately transparent and untrained. Structural metrics
count action kinds, piece types, state variables, numeric parameters, goal clauses,
phases, substeps, primitive concepts, and exception clauses. Description metrics
count independent rule statements, conditional clauses, exception clauses, and
concepts. Operational metrics measure action parameters, bookkeeping fields, and
initial legal-action count. These dimensions remain separate; any later ranking
tuple must preserve them rather than hide them in one scalar.

Human judgments eventually supersede proxy rankings but remain separated into
perceived simplicity, fairness, role preference, strategic interest, replay desire,
and comprehension time.

Schema v4 keeps legacy reports frozen and makes its added costs explicit. Its
initial and post-action goal/mobility ordering contributes five terminal
conditional groups rather than the three used by schemas v1–v3, plus two learned
concepts: initial first-player priority and post-action actor priority. Each PUSH,
SWAP, or HOP role contributes one conditional special form and one action substep
beyond ordinary relocation, while each distinct PUSH, SWAP, or HOP action kind
used is one shared primitive concept. CONVERT is instead a vector-bearing,
non-moving standalone primitive: each role contributes two action substeps, one
independent prose statement, no conditional special-form clause, and two numeric
parameters per declared vector. Multiple CONVERT roles share that one primitive,
and it adds no MOVE base concept. The historical default complexity limits
predate this vocabulary and are diagnostic only; they are not a Plan-0012
family-admission gate.
Any later v4 limit must be frozen from outcome-free feasibility and eventually
checked against human comprehension evidence.

The provisional `CAPTURE_STEP` alias is not assigned a second simplicity cost.
Its optional step-or-capture contract is exactly the frozen `MOVE_CAPTURE`
primitive, prose, condition, and transition. Plan-0012 capture cells reuse that
existing report. If removal substeps are ever reclassified, that must be a
separately versioned simplicity model applied consistently to both schemas,
rather than a cost difference caused by enum spelling.

ELIMINATE contributes one goal primitive and one learned concept when introduced
beside an existing goal kind. Both roles using ELIMINATE share that primitive;
the target identifier increases piece-type count only when it is new. It adds no
state field, numeric parameter, action substep, conditional clause, or prose
statement beyond the one goal statement that it replaces.

Static reachability treats an initially satisfied ELIMINATE goal as reachable
and separately flags the initial result as trivial. If a target remains, the
optimistic upper bound is true only for a `MOVE_CAPTURE` or `CONVERT` role with
at least one matching owned action actor initially present. It deliberately
relaxes direction, blockers, horizon, and the order needed to remove every
target; action-piece and target-piece identifiers need not agree.

## Replay telemetry v1

Replay telemetry is descriptive evidence reconstructed from one authoritative
schema-v4 definition and a complete retained action trace. It is neither an
agent report nor a scalar quality score. At every actual decision it enumerates
the complete legal action set and evaluates every one-ply successor; it performs
no sampling, depth-2 search, solver call, policy choice, or gameplay generation.

The record keeps these evidence dimensions separate:

- exact legal counts, role-level `0`/`1`/`2+` observations, exact forced
  fractions, and the longest forced run;
- frozen action-kind and effect-mode histograms, ordinary-step versus
  conditional-special availability and selection, and actor-relative piece,
  occupancy, movement, conversion, removal, opponent-dependency, and realized
  opponent-effect deltas;
- distinct successor-position and effect-signature variant counts, immediate
  reconvergence, and redundant successor count;
- actor-relative immediate `NONTERMINAL`/`ACTOR_WIN`/`DRAW`/`ACTOR_LOSS`
  alternatives, separate from exact next-player legal-action-set variation among
  at least two nonterminal successors;
- repeated configurations and cycle prefixes, terminal reason/winner/length,
  exact work counters, per-decision counterfactual digests, and one root evidence
  digest.

Successor position identity includes side to move and the canonical pieces but
not ply or terminal metadata; immediate outcome class is compared separately.
Next-player sensitivity compares complete canonical legal-action identities, not
only their counts. Repetition likewise includes side to move and the canonical
pieces while excluding ply and outcome. `CONVERT` is a standalone effect, not a
conditional ordinary-move alternative; only capture, push, swap, and hop are
conditional specials. A HOP over an opponent is an opponent dependency without
a direct opponent state effect. `BOTH_ROLES` means only that both roles realized
such an effect somewhere in the retained trace; it is not a causal reciprocity
claim.

Telemetry-v1 accepts only schema v4 and freezes the seven action kinds, three
goal kinds, three terminal reasons, seven effect modes, four actor-relative
outcome classes, and four direct-effect statuses that it understands. Work is
bounded at 1,000 replay actions, 200 legal actions per decision, 200,000 successor
evaluations, and 40,000,000 next-action observations. Stored evidence is further
bounded at 1,000,000 exact finite-JSON nodes and depth 32. Complete-trace,
canonical-action, exact-type, horizon, mutation, cycle, vocabulary, and
reconstruction checks fail closed; validation accepts an exact stored dictionary
and returns only a fully rebuilt record.

The frozen synthetic benchmark contains seven calculation oracles: an initial
stuck zero-action case, immediate CONVERT reconvergence, PUSH next-legal-set
sensitivity without terminal sensitivity, PUSH alternatives spanning
actor-relative win/draw/loss, B-only realized capture with ELIMINATE, a forced
both-role SWAP repetition, and HOP opponent-dependency without a direct effect.
Every definition, trace, and telemetry evidence digest is fixed under ordered
benchmark root
`6789f97e7f0948df9fa66f75933c061a08e029ce49e9d9da33ae57a7b4a59a33`.
All seven metric projections are invariant under all eight D4 orientations, and
the SWAP cycle has a role-swap metamorphic oracle. Separate adversarial tests
cover malformed, incomplete, trailing, oversized, cyclic, mutable, and forged
inputs. These hand-authored traces validate computation and known false
positives only; they establish no threshold for fairness, agency, strategic
depth, enjoyment, or atlas admission, and they contain no production gameplay
outcome.

## Initial agent evidence

- `random-v1` is a weak stochastic baseline.
- `goal-directed-v1` greedily advances each role's local goal. It is not a monotone
  strength scale and misdirected 8 of 20 exact cases.
- `minimax-v1` uses zero-sum terminal utility and normalized goal-progress leaves.
  Depth 3 matched 16/20 exact directions; depth 5 matched 20/20 on exact-v1.
- `exact-solver-v1` performs full-width memoized minimax to the DSL ply cap and is
  proof-producing for completed tractable searches.

`goal-directed-v1`, `minimax-v1`, and their shared goal-progress heuristic do not
support ELIMINATE. They fail closed before action application, RNG consumption,
or node accounting. Random action selection and exact terminal search need no
goal-progress heuristic. Plan 0013 therefore adds a separate terminal-only
search instead of weakening those guards.

## Plan 0013 family-neutral evaluator benchmark

`terminal_only_minimax-v1` is full-width depth-limited minimax with A-relative
terminal utility `A_WIN=+1`, `B_WIN=-1`, `DRAW=0` and exact zero for every
nonterminal cutoff. A maximizes and B minimizes. The root is not charged; each
new `(GameState, remaining_depth)` successor in one selection consumes one node,
cache hits are free, and the cache is discarded after selection. Node allowance
is cumulative over one role slot. A unique best action consumes no RNG; a tie
uses one seeded `randrange` over canonical best actions. Version 1 supports exact
schema-v4 inputs and depths 1 through 64.

The frozen conformance corpus contains five synthetic definitions: four exact
Plan-0012 telemetry fixtures plus one new SWAP/CONNECT fixture that jointly
exercises actor-priority simultaneous goals and both root and recursive B
minimization. It yields 40 ordered D4 exact/search slots. Exact synthetic labels
are A/B/draw = 16/8/16. Separate complete-game checks run 320 seeded random games
and 320 terminal-only depth-1 games; both use distinct A/B instances per
definition-orientation slot, reuse them across ordered seeds 0–7, and replay the
whole slot with fresh instances. All selections are legal, every game terminates,
and terminal-only role slots have zero budget censors. Random has no node cap.
Exact scalar values are D4-invariant and per-action values transform covariantly,
but a fixed seed applied to coordinate-ordered tied actions does not make the
selected action D4-equivariant. The production schedule therefore retains all
eight orientations and reports sampled orientation sensitivity rather than
treating it as an engine error.

The initial production ladder is only `random-v1-weak` plus
`terminal_only_minimax-v1-depth1`. Its depth-1 cumulative cap is 3,456 nodes per
`definition × orientation × controlled role` slot. Depth 2 and its 169,344-node
structural bound are benchmark diagnostics, not authorized atlas strength. The
fixture/ladder/random/terminal/evidence/separation/benchmark roots are
`9a45e26f…99f565`, `62255ad5…65e62`, `50a0ef2d…77576`,
`38dce33d…480026`, `5cd0dd2a…f8d075`, `a82e7640…51eba`, and
`340e928d…15da0`; canonical SHA-256 is `5097d4d5…a3ffc`.

All fixtures differ from the atlas in D4-preserved piece count and ply cap, and
that separation is checked before any evaluator call. Consequently this
benchmark validates calculations and lifecycle only: it contains zero selected
atlas definition access and zero production outcome, and says nothing yet about
family fairness, strategic depth, or enjoyment.

Profile disagreement is never averaged away. Depth-5 evidence remains sampled and
corpus-limited; exact forced results supersede it where available. Stronger stages
must receive only survivors of explicit cheap admission rules.

## Cascade v2

Discovery admission is lexicographic and unweighted: reject `TOO_SHORT`, then admit
if weak-random draw rate is at least 50% or cheap play assigned no dominance code.
All cheap-play 3×3 cases take an independent exact-audit lane regardless of
admission, preventing false-negative labels from being hidden. Exact draws receive
a depth-5 draw diagnostic; admitted 4×4 cases receive depth-5 discovery evaluation;
5×5 remains an explicit compute deferral.

Audit labels and audit-only depth-5 diagnostics cannot promote a definition that
failed the sealed admission gate. They measure false negatives and agent accuracy;
only an admitted definition can become a strong-stage survivor.

Deterministic node/state caps are part of evaluator configuration. Exhaustion means
unknown and cannot be counted as rejection, survival, fairness, or a solved result.

The held-out cascade-v2 run completed within its deterministic budgets, but every
admission was caused by ply-limit-heavy weak random play and already carried a
non-rescuable shape failure. Cascade-v2 is therefore preserved as a failed discovery
policy, not retuned. Subsequent research separates outcome-independent candidate
selection from explicitly diagnostic evaluator stress lanes.

## Landscape v1

The 3×3 landscape is descriptive, not a generator prevalence estimate. Exact
solving is attempted on all 384 frozen cases independent of every structural or
play gate. Cheap random and goal-directed profiles run only after static,
asymmetry, and simplicity gates pass. Exact censoring remains in the fixed
denominator and makes frontier absence inconclusive.

Completed exact draws enter a separate shape-clean-first depth-5 stress lane with
no replacement after budget exhaustion. A diagnostic-frontier case must be an
exact draw, pass the structural gates, avoid frozen cheap duration/draw failures,
remain non-decisive at depth 5, complete within budget, and have no strong play
failure. This is a search diagnostic rather than a fairness or fun claim. General
depth-5 draw support and exhaustive coverage of shape-clean draw frontiers are
reported as separate assessments.

The completed landscape exactly solved 384/384 cases without censoring. All 13
exact draws ended at `PLY_LIMIT`; depth 5 completed all 13 without a decisive error,
but every strong profile failed excessive-draw and long-game gates. General draw
handling remains `INCONCLUSIVE` because the preregistered minimum was 15, while
frontier coverage is `COMPLETE` and the diagnostic-frontier count is zero. No
landscape definition is a provisional qualifier.

## Stalemate paired test

Schema v2 changes only the no-legal-action outcome from an immobile-player loss to
a draw. Exact solving remains independent of all gates. The paired evaluation
reports v1-to-v2 result and terminal transitions, principal-variation changes,
structural diagnostics, weak and medium play profiles, and duration both relative
to the frozen 18-ply field and to the proved natural 15/16-ply exhaustion bound.
A treatment `PLY_LIMIT` result is a semantic failure, not a draw observation.

Semantic support requires at least four static-valid, post-action exact
`NO_LEGAL_ACTION` draws across at least two frozen strata. A shape-clean draw must
also pass asymmetry and simplicity and avoid the frozen cheap excessive-draw,
too-short, and too-long failures. Shape-clean draws are selected first for the
separately committed depth-5 lane; remaining slots may diagnose other
structurally-valid stalemate draws. Exact censoring, depth-5 directional labels,
node censoring, and candidate-cap censoring retain distinct predeclared meanings
and cannot be averaged into a positive result.

The completed treatment exactly solved all 128 pairs with no horizon or state
censor: 73 A wins, 35 B wins, and 20 stalemate draws. Only two draws were
static-valid post-action cases, so semantic response remained `INCONCLUSIVE`; none
was shape-clean. Depth 5 completed both eligible draws without directional error,
but both were 30/30 stalemates with `EXCESSIVE_DRAWS`, leaving a complete frontier
of zero and an overall `NOT_SUPPORTED` result. Formal draw count, structural
validity, sampled play shape, and frontier membership remain separate quantities.

## Capture paired counterplay test

The preregistered schema-v1/v3 comparison treats a case as `paired-valid` only when
both the replayed v1 source and its v3 treatment pass the unchanged static,
asymmetry, and simplicity gates. The primary response is a paired-valid baseline
`A_WIN`/`NO_LEGAL_ACTION` becoming a treatment `B_WIN`/`GOAL`; four such responses
across at least two frozen strata are `SUPPORTED`, zero is `NOT_SUPPORTED`, and any
intermediate count is `INCONCLUSIVE`. Realized-capture response applies the same
threshold independently to paired-valid, non-horizon exact principal variations
that execute a capture. Capture availability, realized capture, exact value change,
and sampled play shape remain separate evidence.

Exact solving is attempted for every pair independently of the gates. Any exact
state censor makes all counterplay conclusions `INCONCLUSIVE` and blocks adaptive
stress before a reservation is created. The raw record must then seal
`adaptive_stress_disposition: BLOCKED_EXACT_CENSOR`; otherwise it seals `ELIGIBLE`.
A treatment `PLY_LIMIT` is cycling/horizon evidence: that case cannot count toward
a response or frontier and is excluded from stress eligibility without raising the
ply cap. `PLY_LIMIT` is only a case-level exclusion and does not block stress for
other eligible, exactly completed cases.

After an `ELIGIBLE` raw record is committed, adaptive stress may select at most 32
paired-valid, exact-completed, non-`PLY_LIMIT` cases whose exact value changed or
whose treatment principal variation captured, using the preregistered
shape-clean-first hash order without replacement. A stress result must keep exact
direction authoritative, expose node and candidate censor separately, and require
an interaction-frontier case to complete without censoring, avoid frozen strong
duration/draw failures, match its non-horizon exact A/B result, and execute at least
one capture in strong play. Direction mismatch is an evaluator error; censoring or
unselected eligible cases makes the affected frontier and overall conclusions
`INCONCLUSIVE` rather than negative evidence.

The later fixed-membership capture-boundary replication removed adaptive frontier
censoring but did not reproduce a three-versus-four-vector separator. Both halves
were exact A/B = 3/29 and all 64 depth-5 profiles were 30–0. Unrestricted capture
and vector-count tuning are therefore preserved negative evidence rather than an
authorized generator substrate.

## Two-runner setup test

Plan 0010 changes only B's initial multiplicity from one ordinary runner to two.
Exact runner lineage is a trace-local diagnostic derived from retained actions and
never part of engine identity. Exact engagement requires one treatment PV that
both moves the added start lineage and exposes a B decision with legal actions from
both current lineages. Strong sampled engagement requires those two facts in the
same completed treatment game; exact traces, cross-game unions, and censored
prefixes cannot substitute.

The completed fixed experiment solved all 128 source/treatment slots and ran all
128 depth-5 profiles without censoring, horizon, or direction mismatch. Exact
engagement was supported in 31 cases across 12 strata, and 46 cases formed a
same-game-engaged strong frontier across all 16 strata. Every frontier profile was
30–0 role-dominant, leaving candidate shape empty. The formal result is
`NOT_SUPPORTED_TWO_RUNNER_SETUP`; mechanical use of a piece remains separate from
within-definition fairness.

## Exact-backed 4×4 transfer calibration

Plan 0011 evaluates the promoted depth-5 agent rather than a game family. Its
outcome-blind corpus contains one fresh, gate-valid generator-v2 definition from
each of 32 4×4/`max_plies=8` structural strata. Selection cannot access exact,
sampled, admission, timing, or historical outcome fields.

The reviewed pure checkpoint reconstructs 16,320 raw definitions, 2,040 D4
orbits, 1,592 gate-valid orbits, 14 closed-history exclusions, and 1,578 fresh
orbits. Its one-per-stratum pool root is `963ab02e…44e99` and its selection
fingerprint is `bcf9992c…ce834`. These are definition-only planning identities;
no production manifest or calibration label exists yet.

The pure exact-evaluator checkpoint fixes all 32 manifest-order calls to
`exact-solver-v1` at 100,000 states and publicly reconstructs the result from raw
slots. Validation rebinds each case to the authenticated manifest/history pair,
replays the complete principal variation to its claimed terminal state, checks
search accounting against both the PV and structural bound, and rebuilds the
timing-free evidence digest, label counts, definition-only breakdowns, coverage
decision, and complete 32-row inspection. Descriptive timing is validated but is
excluded from the evidence digest. A raw state-budget censor is a structural-proof
integrity failure, not a calibration observation.

The eight-ply horizon permits structural exact-state bounds of 62,096 for A-first
and 40,272 for B-first definitions, both below the unchanged 100,000-state cap.
An exact state censor therefore contradicts the proof and blocks depth 5. Exact
`DRAW/PLY_LIMIT` is instead a legitimate finite-horizon calibration label; it is
never candidate or fairness evidence.

Transfer label coverage requires at least 15 decisive exact cases, at least four
exact A wins, four exact B wins, and four exact horizon draws, with every label in
at least two strata. Only after that fixed coverage exists does every definition
receive depth-5 self-play over seeds `0..29` under a fresh cumulative
5,000,000-node budget. Support requires all profiles to complete, at least 90%
accuracy on exact decisive A/B directions, and zero exact draw called decisive.
Dominance and play shape are reported but cannot route this calibration result.

The reviewed pure depth checkpoint fixes one freshly constructed and once-reset
`minimax-v1-depth5` instance per definition, shared by both roles and all 30 seeds.
Its agent-facing schedule contains only definition-derived identities. Each
completed game retains a replayable action trace and a contiguous cumulative node
delta whose lower bound is reconstructed from legal root actions. A genuine
per-candidate node censor retains the completed seed prefix and the next
nonterminal action prefix, routes only later seeds of that definition, and makes
the complete transfer result `INCONCLUSIVE_NODE_BUDGET`; later definitions still
run. Exact-type budget fields, agent configuration and identity, input stability,
action legality, cap accounting, and zero-node censor semantics all fail closed.

The result reconstructs exact-label-by-sampled-direction confusion, exact-draw
decisive errors, all fixed definition-only breakdowns, every inspection row, and a
timing-free raw-slot digest. The standalone transfer assessor rechecks sufficient
exact label coverage and applies the 90% threshold by integer comparison. Shape
codes remain visible but cannot alter the transfer disposition. This checkpoint
has not solved a selected case or run the fixed public depth agent, so it supplies
no production 4×4 exact label or transfer evidence.
