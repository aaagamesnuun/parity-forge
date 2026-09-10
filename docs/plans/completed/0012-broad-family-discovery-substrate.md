> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0012 — Broad-family grammar and occupancy-v4 feasibility

## Status

Completed outcome-free. Plan 0011 remains `SUPERSEDED_PRE_OUTCOME`. Plan 0012
created no gameplay outcome, atlas membership, frozen family registry,
search-envelope root, reservation, or experiment run.

## Objective

Create a bounded route out of the exhausted `A = PLACE / B = MOVE` lane without
turning the DSL into a general programming language. This plan will:

1. establish a strict ludeme-level family identity;
2. define and implement a small occupancy-only schema v4;
3. validate replay-derived agency and interaction measurements against synthetic
   counterexamples; and
4. perform an outcome-free feasibility census for a provisional six-cell
   occupancy portfolio.

This plan stops before gameplay evaluation. If the semantics, telemetry, and
family domains survive review, a later plan may freeze a development atlas. That
later atlas will be a pilot over one 3×3 local-occupancy portfolio, not a claim to
have searched all abstract games.

## Observation

Plans 0006–0010 varied terminals, capture permission, movement bands, runner
count, and board parameters around one placement-versus-runner topology. They
found mechanical response but no non-dominant candidate shape. Plan 0011 built a
reviewed 4×4 evaluator calibration for that lane, but no production edge or
outcome was created before the broader-family pivot.

The present uncertainty is therefore not another parameter value inside the old
generator. It is whether a small, inspectable vocabulary of genuinely different
local actions can support fair and consequential asymmetric play at all.

## Hypothesis

Atomic relocation, displacement, exchange, leap-dependency, ownership transfer,
and removal can create more reciprocal interaction than one role building static
occupancy while the other traverses it. A finite portfolio can test that
hypothesis without callbacks, phases, counters, chained actions, or arbitrary
rule predicates.

A negative result will apply only to the exact registered signatures, setup
envelopes, board size, and evaluation protocol. It cannot justify retirement of
the whole occupancy model or identify one ludeme as causal without a subsequent
matched ablation.

## Identity layers

Do not collapse these identities:

1. **Family semantic identity** — a name-free `FamilySignature` containing the
   state kernel, ordered A/B action and goal ludemes, terminal contract, and turn
   structure.
2. **Registry identity** — an ordered `FamilyRegistry` of stable
   `FamilyRecord(family_id, signature)` values. The ID is not part of the semantic
   signature hash; the registry hash includes both IDs and ordered signatures.
3. **Search-envelope identity** — a future versioned record containing the
   required DSL version, setup-template descriptor, board-size domain, exact
   direction/setup/first-player/horizon domains, generator route and version, and
   D4 canonicalization version.
4. **Definition identity** — authoritative canonical DSL bytes and exact hash.
5. **D4 identity** — the separate orientation-independent mechanical orbit hash.
6. **Derivation witness** — after schema v4 and its pure compiler exist, a public
   reconstruction binds one search input, family signature, search envelope,
   exact definition, exact hash, and D4 hash.

The family layer must not carry setup parameters, generated definitions,
callbacks, outcomes, prose names, or claims about interaction quality. The search
envelope must not masquerade as a new family merely because a quota or horizon
changed.

## Definition of done

- [x] Add a versioned, canonical, callback-free `FamilySignature`, stable
  name-separated records, ordered registry artifact, domain-separated hashes,
  strict parser boundaries, and adversarial tests. Demonstrate that all six
  provisional ludeme cells are representable and distinct, but do not freeze the
  final Plan-0012 registry before feasibility.
- [x] Freeze the schema-v4 terminal contract, including cross-role and
  simultaneous goals, initial goals, horizon precedence, and stuck-player
  precedence. Prove schemas 1–3 retain their exact terminal behavior.
- [x] Add strict schema v4 one atomic action at a time: `PUSH`, `SWAP`, `HOP`,
  and `CONVERT`, followed by `ELIMINATE`. The proposed `CAPTURE_STEP` contract was
  rejected before implementation because it exactly aliases existing v4
  `MOVE_CAPTURE`; the capture cells reuse that primitive. Every slice must prove
  schema-v1/v2/v3 canonical JSON, hashes, prose, legal actions, transitions,
  terminal results, and frozen fixtures unchanged.
- [x] Extend D4 transforms and simplicity accounting for every new field and
  action submode. Ordinary step plus a conditional special form counts as more
  than one operational or descriptive concept even when represented by one
  action ludeme.
- [x] Add versioned replay telemetry reconstructed from an authoritative
  definition and a complete retained trace. It must distinguish immediate
  terminal-outcome sensitivity from next-player legal-set sensitivity and state
  effects; bound hostile iterables by the definition horizon; and freeze the
  action vocabulary per telemetry version.
- [x] Freeze a synthetic telemetry benchmark only after the required v4 actions
  exist. Cover forced branching, consequence-free branching, immediate
  win/draw/loss alternatives, no/one-sided/both-role direct effects,
  repeated-state prefixes, capture, conversion, elimination, and malformed
  traces. The benchmark verifies computation and known counterexamples; it does
  not validate a universal threshold for fun or agency.
- [x] Specify pure setup templates and exact finite parameter domains for the
  provisional portfolio, then enumerate them without engine play, solver, agent,
  or outcome access. Report supply, D4 orbits, initial-goal exclusions, initial
  mobility, reachable work bounds, and actual density/branching descriptors.
- [x] Review whether every proposed cell is semantically coherent and has enough
  support for a matched nominal-exposure pilot. Revise or remove infeasible cells
  only from this outcome-free evidence, using a new registry/search-envelope
  version for every change.
- [x] End with one explicit recommendation: freeze a later development-atlas
  plan, repair a semantic or measurement defect, propose another bounded
  portfolio, or retire only this exact provisional 3×3 portfolio.
- [x] Run independent semantic, backward-compatibility, telemetry, identity, and
  feasibility reviews plus the complete dependency-free test suite. Create no
  gameplay outcome in this plan.

## Schema-v4 terminal contract

Schema v4 uses state predicates that may be changed by either role. After a legal
action, evaluate terminal conditions in this order:

1. the acting player's goal;
2. the opposing player's goal;
3. the explicit ply cap;
4. absence of a legal action for the next player, which is a loss for that
   player.

Thus an action may immediately give the opponent its goal, and if both goals are
true after the same action the actor wins. At the initial state, use first-player
then second-player goal priority before testing first-player mobility. The
provisional generator rejects every initial-goal setup, but the DSL and engine
still require deterministic semantics for hand-authored definitions.

This contract is schema-v4-only. Schemas 1–3 retain actor-goal-only behavior,
their existing goal/ply/stuck precedence, and their existing initial-state
behavior byte for byte.

## Occupancy schema v4

Schema v4 remains a deterministic square-board occupancy model. It adds no
reserve, score, phase, chance, hidden state, simultaneous turn, arbitrary graph,
callback, or user-defined procedure. Each role still has one action and one goal.
Every vector-bearing action uses a declared one-step vector, and every action
affects at most one owned actor, one opposing target, and one landing cell.

- `PUSH` *(implemented checkpoint)*: step to an empty adjacent destination, or
  enter one adjacent opponent cell while moving that target one more cell along
  the same vector. The landing cell must be in bounds and empty. No friendly
  target, chain, or off-board push.
- `SWAP` *(implemented checkpoint)*: step to an empty adjacent destination, or
  exchange positions with one adjacent opponent. No friendly, ranged, or
  multi-piece swap.
- `HOP` *(implemented checkpoint)*: step to an empty adjacent destination, or
  jump over exactly one occupied adjacent cell to the empty cell one more step
  along the same vector. The jumped piece is unchanged. No chain hop.
- `CONVERT` *(implemented checkpoint)*: the owned actor stays in place and
  changes exactly one adjacent opposing target of any kind into an actor-owned
  piece of the action's declared kind at the same target cell. A same-kind
  opponent remains a legal target because ownership changes. No empty or
  friendly target, actor movement, ranged conversion, or multi-target
  conversion.
- `MOVE_CAPTURE` *(existing primitive reused by v4)*: step to an empty adjacent
  destination, or enter one adjacent opponent cell, remove that target, and
  occupy its cell. The proposed `CAPTURE_STEP` name had exactly this contract and
  is not added to the executable DSL.
- `ELIMINATE` *(implemented checkpoint)*: a role's goal is true when no opposing
  piece of its declared target kind remains.

`PUSH`, `SWAP`, and `HOP` each contain an ordinary step and a conditional special
submode. Simplicity metrics count that condition, target/landing relation, and
state effect rather than treating the enum name as one indivisible rule.
`MOVE_CAPTURE` retains its already-frozen cross-schema simplicity report; any
future reclassification of removal substeps requires a new simplicity-model
version applied consistently, not a duplicate action name.

## Provisional portfolio

These six cells are hypotheses for feasibility work, not a frozen registry or an
equal scientific sample:

| Provisional ID | Role A | Role B | Interaction hypothesis |
|---|---|---|---|
| `push-hop-race-v1` | `PUSH / REACH_EDGE` | `HOP / REACH_EDGE` | displacement versus occupancy-dependent evasion |
| `swap-hop-network-v1` | `SWAP / CONNECT_EDGES` | `HOP / REACH_EDGE` | exchange-built network versus escape |
| `convert-push-front-v1` | `CONVERT / CONNECT_EDGES` | `PUSH / REACH_EDGE` | ownership growth versus displacement |
| `capture-hop-hunt-v1` | `MOVE_CAPTURE / ELIMINATE` | `HOP / REACH_EDGE` | attrition versus evasion |
| `convert-capture-duel-v1` | `CONVERT / ELIMINATE` | `MOVE_CAPTURE / ELIMINATE` | ownership transfer versus removal |
| `push-swap-networks-v1` | `PUSH / CONNECT_EDGES` | `SWAP / CONNECT_EDGES` | two ways to reorganize mobile networks |

None is `PLACE` versus `MOVE`. Schema-v3 runner capture remains negative evidence
for its exact historical family. The provisional cells reuse its capture
primitive but change the ordered action/goal topology: capture-versus-hop and
convert-versus-capture with elimination goals are not the historical
place-versus-capture race. Setup and source membership also remain separate, so
the prior result cannot be revived or discarded by renaming the action.

Setup counts and labels such as `LOW/HIGH` or `SPARSE/DENSE` are intentionally not
fixed yet. Their meanings differ across action types and connection goals may
require higher minimum occupancy. The outcome-free census must first expose the
common support. If relative strata are later used, report absolute occupancy,
vector count, initial legal-action count, and proved state/work bounds alongside
them.

## Telemetry contract

Telemetry is evidence reconstructed from definitions, states, and complete action
traces; it is never an agent-supplied score. The first v4 version should retain at
least:

- legal-action counts and 0/1/2+ decision distribution by role;
- forced fraction and longest forced sequence;
- chosen action and ordinary/special effect availability and use;
- own movement, opponent movement, conversion, and removal deltas;
- counterfactual next-player legal-set sensitivity;
- counterfactual immediate terminal-outcome sensitivity;
- a separately specified bounded reconvergence observation, if implemented;
- unilateral and reciprocal realized effects by role;
- repeated-state and cycle-prefix observations;
- terminal reason, winner, length, and action counts.

The synthetic corpus tests these calculations and known false positives. It
cannot establish that a numerical cutoff means “fun,” “depth,” or humanly
meaningful agency. The first atlas, if authorized later, reports telemetry
descriptively. Any operational trigger is explicitly provisional, fixed before
play, and cannot override fairness, censoring, or evaluator disagreement.

## Feasibility and later comparison

Equal case counts, seeds, or node caps do not make heterogeneous families equally
difficult to solve. A later pilot may offer matched nominal exposure, but it must
report state-space bounds, branching, node use, censor rates, and censor-aware
bounds per family. It cannot rank family prevalence or quality from those quotas.

Before any gameplay, the feasibility census will determine common support and a
defensible cap. A deficient cell remains `INCOMPLETE_FAMILY_DOMAIN`; it does not
silently receive replacement cases. Other coherent cells may proceed in a
separately versioned sub-atlas rather than losing all information because one
cell failed.

Known coordinate tie-breaking can make sampled agents orientation-sensitive.
Before cross-family interpretation, either demonstrate D4-equivariance for the
fixed agent or evaluate a predeclared complete D4 orientation schedule.

Development and confirmation remain distinct. Repeatable development uses unique,
immutable versioned runs. Fresh one-shot confirmation, reservations, and generic
provenance infrastructure are deferred until development evidence actually
justifies them.

## Non-goals

- Do not resume or infer an outcome for Plan 0011.
- Do not generate gameplay, solve provisional definitions, or select an atlas in
  Plan 0012.
- Do not freeze six-family membership, setup domains, quotas, telemetry routing
  thresholds, or a registry root before the outcome-free feasibility census.
- Do not add a general rule AST, script, callback, phase language, counter,
  inventory, score, chain action, ranged effect, chance, or hidden information.
- Do not call nominally matched compute “equal difficulty” or a synthetic metric
  “fun.”
- Do not infer individual-ludeme causality from unmatched family comparisons.
- Do not implement a confirmation runner or refactor frozen historical evidence
  modules in this plan.

## Implementation slices

1. **Family identity scaffold:** semantic signature, record/registry artifacts,
   canonical hashes, parser normalization, and adversarial tests. The provisional
   six cells must be representable but are not frozen as the final registry.
2. **Terminal and DSL-v4 shell:** cross-role terminal contract, strict parser and
   data types, canonicalization, prose, D4, and frozen backward-compatibility
   fixtures.
3. **Atomic actions and goal:** implement `PUSH`, `SWAP`, `HOP`, `CONVERT`, then
   `ELIMINATE`, each in an independently reviewed slice. Reuse `MOVE_CAPTURE` for
   the removal cells; do not implement the semantically duplicate
   `CAPTURE_STEP` proposal.
4. **Telemetry and benchmark:** build the complete v4 replay schema and freeze
   synthetic definitions/traces only after the required semantics exist.
5. **Outcome-free feasibility:** setup descriptors, finite domains, pure
   enumerators, D4 identity, initial gates, census, and work bounds.
6. **Closeout:** independent review, full reconstruction, and one next-branch
   recommendation. A gameplay atlas requires a new plan.

## Slice 1 checkpoint

The family-identity scaffold is complete. Its v1 vocabulary contains only the
historical occupancy actions/goals and the five documented v4 action proposals;
undefined future kernels and ludemes are rejected until a later signature
version. Family and registry JSON/hash golden vectors are fixed. Registry
construction detaches caller inputs and binds an internal canonical snapshot, so
low-level mutation fails through accessors, serialization, parsing, and hash
boundaries. All six provisional cells are representable and have distinct
semantic hashes, but no final six-record registry or search envelope was frozen.

Independent adversarial review found and closed premature generator-domain
coupling, registry mutation, terminal-order naming, undefined-vocabulary, and
golden-vector gaps, then reported no remaining P0–P3 defect. The complete suite
passes 381/381 tests. No engine, solver, agent, filesystem, Git, manifest, or
gameplay capability was added to the family module.

## Schema-v4/PUSH checkpoint

The schema-v4 terminal contract and the first atomic action are implemented as
one backward-compatible vertical slice. Initial goals use first-player priority;
post-action goals use actor priority; both precede the ply cap, and the ply cap
precedes post-action immobility. Schemas v1–v3 retain actor-only goal checking and
their previous initial semantics.

At this checkpoint v4 admits `PLACE`, `MOVE`, `MOVE_CAPTURE`, and `PUSH` but
requires at least one PUSH role. PUSH has only ordinary empty-cell relocation or
one adjacent-opponent displacement into one in-bounds empty landing cell. Its
recorded action remains `kind/from/to`; replay derives the displaced target and
landing from the definition and state. Friendly, chained, occupied-landing,
off-board, and undeclared-vector pushes are illegal.

An exhaustive local reference check covers all 59,049 assignments formed by one
A pusher and every empty/friendly/opponent occupancy labeling of the other eight
3×3 cells. Engine legal actions match the independent PUSH predicate in every
assignment; this is a semantics check, not gameplay or an outcome census.

Direct v4 construction validates the complete parser-normalized object graph,
including exact enum/integer types, canonical tuples and ordering, roles, goals,
actions, and setup. Canonical JSON, hashes, and prose independently reparse and
compare typed values, closing string-enum equality, mutable-container, hidden
field, and low-level mutation paths. The fixed v4 definition hash is
`e81605ebb3709c1b97069b141ea2ee70e58c3c74130f0403293493e0a9fe1c3f`; the PUSH
D4 fixture hash is
`656981777ffbe417479a6cd6b84eddaeea199dd18a57e41e99f48355535ef802`.

D4 transforms PUSH vectors. Simplicity treats each PUSH role as ordinary movement
plus one distinct primitive, one conditional special rule, and one additional
action substep. It separately charges schema v4's initial/post-action terminal
priority as two additional conditional clauses and two learned concepts. Two PUSH
roles pay the per-role structural/description cost without double-counting the
shared learned primitive. No compiler, search
envelope, or telemetry was added. No Plan-0012 solver, agent, gameplay experiment,
or outcome was run or created.

Independent DSL and engine/integration reviews found and closed direct-construction,
string-enum equality, bool-coordinate equality, mutable-container, hidden/missing
field, D4-boundary, and terminal/simplicity accounting defects, then reported no
remaining P0–P3 finding. Separate compatibility checks found zero schema-v1/v2/v3
differences over 3,600 states and 7,804 legal transitions. The complete suite
passes 409/409 tests in 323.286 seconds.

## Schema-v4/SWAP checkpoint

The second atomic v4 action is implemented without changing the terminal
contract or any already-valid PUSH definition. Schema v4 now accepts `PLACE`,
`MOVE`, `MOVE_CAPTURE`, `PUSH`, and `SWAP`, while requiring at least one role to
use `PUSH` or `SWAP`. This prevents old-only definitions from acquiring v4 terminal
semantics by a version-only change.

SWAP uses an owned actor and one declared adjacent vector. An empty destination
is an ordinary relocation; an opponent destination exchanges the actor and target
positions while preserving both owners and piece kinds. Friendly destinations,
ranged or multi-piece swaps, undeclared vectors, and additional recorded effect
fields are illegal. The canonical action remains `kind/from/to`, and replay
derives the exchange from the definition and current state.

The fixed SWAP v4 definition hash is
`c8dba41bb2e97e5fcc5dd119a415da2ee74b68e196f38c70d2aada292de73ba2`; its fixed
D4 fixture hash is
`aae4af10c105a9e498277a0df32024f3bdbd4baf91ef95368ba2d9985030c4b0`.
D4 transforms every declared SWAP vector. Simplicity treats SWAP as ordinary
movement plus one distinct shared primitive, one conditional special rule per
SWAP role, and one additional action substep per role.

An independent local predicate matches engine SWAP legality over all 59,049
assignments formed by one A swapper and every empty/friendly/opponent labeling of
the other eight 3×3 cells. Backward-compatibility comparison found zero
schema-v1/v2/v3 differences over 3,600 states and 7,804 legal transitions and zero
PUSH differences over 1,200 states and 835 transitions. The SWAP D4 comparison
found zero differences over 2,368 cases. The focused regression suite passes
99/99, and the complete dependency-free suite passes 425/425 tests in 332.954
seconds. No Plan-0012 compiler, search envelope, or telemetry was added, and no
Plan-0012 solver/agent run, gameplay experiment, or outcome artifact was created
in this slice.

## Schema-v4/HOP checkpoint

The third atomic v4 action is implemented without changing the terminal contract
or any already-valid PUSH or SWAP definition. Schema v4 now accepts `PLACE`,
`MOVE`, `MOVE_CAPTURE`, `PUSH`, `SWAP`, and `HOP`, while requiring at least one
role to use `PUSH`, `SWAP`, or `HOP`. All 36 ordered role-action pairs are tested:
the 27 pairs containing a v4-only action are admitted and the nine old-only pairs
are rejected.

HOP uses an owned actor and one declared adjacent vector. An empty adjacent cell
is an ordinary relocation. An occupied adjacent cell of either owner and any kind
may instead be jumped when the cell one more step along the same vector is in
bounds and empty. The jumped piece is unchanged. Empty intermediates, occupied or
off-board landings, undeclared directions, moves longer than two cells, and chains
are illegal. A special action records the final landing as `to`; the canonical
action remains `kind/from/to`, and replay derives the intermediate cell from the
definition and state.

The fixed HOP v4 definition hash is
`4ad5598c0b5a15cb24fa9b79747634c7a8ea87fa909f40cb23ad2181528015ce`; its fixed
D4 fixture hash is
`94d8d41c58a35f6882846ebefe0fb7a19ab2787238819e83e61773fc54266b95`.
D4 transforms every declared HOP vector. Simplicity treats HOP as ordinary
movement plus one distinct shared primitive, one conditional special rule per
HOP role, and one additional action substep per role.

An independent local predicate matches engine HOP legality over all 59,049
assignments formed by one A hopper and every empty/friendly/opponent labeling of
the other eight 3×3 cells. It produces exactly 110,808 actions: 87,480 ordinary,
11,664 over friendly pieces, and 11,664 over opposing pieces. Independent D4
checks found zero differences across 472,392 transformed legality cases and
886,464 transformed transitions. Comparison with the SWAP checkpoint found zero
differences across 6,000 schema-v1/v2/v3/PUSH/SWAP states and 11,822 transitions,
including canonical JSON, hash, and prose identity. The focused regression suite
passes 117/117, and the complete dependency-free suite passes 443/443 tests in
333.079 seconds. Independent DSL, engine, and integration reviews closed one P3
ordered-pair test-coverage gap and reported no remaining P0–P3 finding. No
Plan-0012 compiler, search envelope, or telemetry was added, and no Plan-0012
solver/agent run, gameplay experiment, or outcome artifact was created in this
slice.

## Schema-v4/CONVERT checkpoint

The fourth atomic v4 action is implemented without changing the terminal
contract or any already-valid PUSH, SWAP, or HOP definition. Schema v4 now
accepts `PLACE`, `MOVE`, `MOVE_CAPTURE`, `PUSH`, `SWAP`, `HOP`, and `CONVERT`,
while requiring at least one role to use `PUSH`, `SWAP`, `HOP`, or `CONVERT`.
All 49 ordered role-action pairs are tested: the 40 pairs containing a v4-only
action are admitted and the nine old-only pairs are rejected.

CONVERT uses one matching owned actor and one declared adjacent vector. The actor
stays completely unchanged. One opponent target of any kind at the declared
target cell changes owner to the actor and piece kind to the action's declared
kind without moving. A same-kind opponent remains a legal target because its
owner changes. Empty or friendly targets, missing or wrong-kind actors,
off-board, ranged, or undeclared targets, actor movement, and multiple targets
are illegal. Each action records only `kind/from/to`; `from` is the unchanged
actor cell and `to` is the rewritten target cell.

The fixed CONVERT v4 definition hash is
`9233c363533156baa3553832d277810658256b65ddac28490af19b15e5478429`; its fixed
D4 fixture hash is
`64f7f012a33713f90276d2cd2ecfdc5bef8c5966295632c575a64c8dcbbc1f0f`.
CONVERT belongs to the vector-bearing set used by canonicalization, D4, and
numeric-parameter accounting, but not to the movement set used by mobility and
asymmetry analysis. Simplicity treats it as one standalone shared primitive,
with two action substeps and one prose statement per role, no conditional
special-form clause, and two numeric parameters per declared vector. The static
goal upper bound is relaxed only when a matching initial CONVERT actor exists and
the action and goal piece kinds agree; no broader cross-role PUSH/SWAP relaxation
is introduced in this slice.

An independent local predicate matches engine legality over all 59,049
assignments formed by one A converter and every empty/friendly/opponent labeling
of the other eight 3×3 cells. It produces exactly 87,480 actions, with legal-count
histogram `0:11488, 1:21328, 2:16264, 3:7084, 4:2200, 5:556, 6:112, 7:16,
8:1`. Independent D4 checks found zero differences across 472,392 transformed
legality cases and 699,840 transformed transitions. Comparison with the HOP
checkpoint found zero differences across 7,200 schema-v1/v2/v3/PUSH/SWAP/HOP
states and 19,301 legal transitions, including terminal metadata.

The focused regression suite passes 138/138, and the complete dependency-free
suite passes 464/464 tests in 333.681 seconds. Independent DSL, engine, and
integration reviews reported no P0–P3 finding. No Plan-0012 compiler, search
envelope, or telemetry was added, and no Plan-0012 solver/agent run, gameplay
experiment, or outcome artifact was created in this slice.

## CAPTURE_STEP alias-audit checkpoint

Pre-implementation review found that the proposed `CAPTURE_STEP` contract was
not a new mechanic. Schema v4 already accepts `MOVE_CAPTURE` with the same
declared one-step vectors, ordinary empty-cell moves, optional entry into one
adjacent opponent cell, single-target removal, final actor position, exact
`kind/from/to` evidence, D4 action, static movement treatment, and v4 terminal
contract. A second executable DSL `ActionKind` would differ only in spelling.

That alias would falsely create separate family-signature hashes, exact DSL
hashes, D4 identities, asymmetry dimensions, simplicity concepts, and feasibility
orbits for one transition system. It is therefore rejected before executable
implementation. The family-signature-v1 `CAPTURE_STEP` proposal token remains
readable solely for identity compatibility, but the current provisional cells
use existing `MOVE_CAPTURE`, and the future compiler/final registry must not emit
the retired token. The explicit `NONRETIRED_ACTION_PRIMITIVES_V1` allow-list and
`validate_nonretired_family_signature`/`registry` boundaries make that exclusion
fail closed while preserving legacy parse and hash reconstruction. These
boundaries reject retired aliases only; the future compiler must separately
prove DSL compilability and schema admission. Mandatory capture remains a
possible genuinely different future action, not an implicit change to this
portfolio.

The capture cells remain mechanically different from the rejected historical
family at the complete signature level: `MOVE_CAPTURE / ELIMINATE` faces
`HOP / REACH_EDGE`, and `CONVERT / ELIMINATE` faces
`MOVE_CAPTURE / ELIMINATE`. No outcome was consulted, no v4 admission change was
needed, and no solver, agent, or gameplay experiment was run.

The independent all-occupancy oracle covered 59,049 3×3 states and exactly
174,960 actions: 87,480 ordinary steps and 87,480 captures, with histogram
`{0:1081, 1:6928, 2:16096, 3:16864, 4:9760, 5:5248, 6:1792, 7:1024, 8:256}`.
It found zero D4 differences over 472,392 legality cases and 1,399,680
transitions. Three independent reviews found no remaining P0–P3 issue. The
focused family/reuse suite passes 22/22 tests, and the complete dependency-free
suite passes 472/472 tests in 350.375 seconds.

## Schema-v4/ELIMINATE checkpoint

The planned occupancy-v4 action/goal vocabulary is complete. ELIMINATE has
exactly `kind` and `piece`; the piece names an opponent target kind. Its state
predicate is true iff no opponent-owned piece of that kind remains. Owned
same-kind pieces and opponent other-kind pieces are irrelevant. No edge,
counter, owner, or history field is stored. An initial target count of zero is
intentionally a goal under the existing first-player priority; later
outcome-free feasibility must exclude such trivial starts.

Schemas v1–v3 reject ELIMINATE through both parser and direct-construction
boundaries. Schema v4 admits a definition iff it has at least one
PUSH/SWAP/HOP/CONVERT action or at least one ELIMINATE goal. Exhaustive coverage
of all `7^2 × 3^2 = 441` ordered action/goal combinations yields 405 admissions
and 36 rejections; the rejected set is exactly the `3^2` old-action pairs with
the `2^2` old-goal pairs. Existing valid v4 definitions remain byte-identical.

The fixed canonical parser/prose fixture hash is
`6c1aa7c031eaf54772f128bfdfd6dc0305a3e3b18c9b9f0898875c03f51f94c4`.
The fixed asymmetric two-ELIMINATE fixture has exact DSL hash
`a3a1761e1a04e62f95d69e0190d7368936842fdaf40a123f02a0f5696ec8f0a2`
and D4 hash
`3a104109d52a633fb2b698fdfffa7f7189f373ad357d5796e7accba923013030`.
D4 changes positions and action vectors but leaves the non-spatial goal dict
unchanged.

An independent predicate covers every assignment of each 3×3 cell to empty,
A-target, or B-target: 19,683 states and 39,366 role checks. The exact truth
distribution is neither 18,660, A-only 511, B-only 511, and both 1. Applying all
eight D4 maps produces zero differences over 314,928 checks. Targeted transition
tests cover last, non-last, and wrong-kind MOVE_CAPTURE; same- and other-kind
CONVERT; non-removing PUSH/SWAP/HOP; and initial, actor, opponent, ply-cap, and
stuck precedence.

Static reachability returns true immediately for an already satisfied goal. With
a target remaining, it is optimistic only when the role uses MOVE_CAPTURE or
CONVERT and has a matching initial owned action actor; action and target piece
kinds need not agree. Simplicity adds only the distinct shared goal primitive
and learned concept, with a piece-type increase only for a new target identifier.
Goal-directed-v1, minimax-v1, and goal-progress-v1 reject any ELIMINATE definition
before action application, RNG consumption, or node accounting rather than
inventing an uncalibrated heuristic.

The focused regression suite passes 157/157. Three independent reviews compared
104 legacy definitions at canonical JSON/hash/prose boundaries and 52 legacy
definitions over 236 legal actions/transitions, closed one P3 implicit-CONNECT
analysis branch, and found no remaining P0–P3 issue. The complete
dependency-free suite passes 495/495 tests in 340.804 seconds. No Plan-0012
solver/agent run, gameplay experiment, outcome artifact, compiler, search
envelope, or telemetry was created in this slice.

## Replay-telemetry/benchmark checkpoint

Replay telemetry v1 is implemented for authoritative schema-v4 definitions and
complete retained action traces. It reparses a detached definition, validates
exact action records, rejects incomplete and post-terminal traces, and bounds
replay length, legal-action enumeration, counterfactual successors,
next-action observations, and stored JSON structure. Its action, goal, terminal,
effect-mode, actor-relative outcome, and direct-effect-status vocabularies are
closed for this version; a future DSL addition therefore fails closed until a
new telemetry version admits it.

Every actual decision retains the exact legal-action count and action/effect
histograms, the selected effect and state deltas, ordinary-step and conditional-
special availability/use, exact one-ply successor-position and effect-signature
variation, immediate reconvergence, actor-relative terminal-outcome sensitivity,
and exact next-player legal-action-set sensitivity where comparable. Role
summaries retain 0/1/2+ decision counts, exact forced fractions, longest forced
run, action/effect totals, and realized state deltas. The replay also records
repeated configurations and cycle prefixes, terminal evidence, bounded-work
counters, and one canonical evidence digest. `CONVERT` is a standalone action;
only `MOVE_CAPTURE`, `PUSH`, `SWAP`, and `HOP` have a conditional special mode.
No scalar agency score, policy, solver, depth search, sampling, or universal
threshold is part of telemetry v1.

The frozen synthetic benchmark contains seven definition-plus-trace fixtures:
initial immobility, conversion reconvergence, PUSH next-legal-set sensitivity,
immediate actor-relative win/draw/loss alternatives, capture with ELIMINATE and a
one-sided direct effect, SWAP with both roles realizing direct effects plus a
repeated-state prefix, and HOP opponent-dependency without a direct opponent
effect. It fixes every definition hash, trace digest, telemetry evidence digest,
and ordered benchmark root. All seven fixtures preserve their metric projection
under every D4 transform; the both-role SWAP cycle also preserves its declared
relationship under a role swap. The benchmark root is
`6789f97e7f0948df9fa66f75933c061a08e029ce49e9d9da33ae57a7b4a59a33`.

This checkpoint validates reconstruction and the named counterexamples only.
Independent semantic and hostile-boundary reviews found and closed defects in
CONVERT classification, repeated-period calculation, zero-action summaries,
typed/stored evidence trust, validation ordering, and bounded JSON handling,
then reported no remaining P0–P3 issue. The focused telemetry suite passes 39/39
tests, and the complete dependency-free suite passes 534/534 tests in 337.888
seconds.

It created no Plan-0012 candidate corpus, solver or agent run, gameplay
experiment, outcome-based comparison, atlas selection, registry freeze, or
search-envelope freeze.

## Provisional feasibility domain/compiler checkpoint

The first outcome-free feasibility slice fixes a provisional, exactly enumerable
3×3 input domain without declaring it a final registry or search envelope. It
uses balanced disjoint A/B setups with two or three pieces per role, independent
ordered `ORTHOGONAL_4`/`KING_8` vector profiles, A- or B-first play, a fixed
18-ply structural horizon, and the complete family-specific D4 quotient of goal
relations. The arithmetic is 2,436 setups × 11 family/frame occurrences × four
ordered vector pairs × two first-player choices = 214,368 unique inputs.

The descriptor hash is
`3456b5873dadfd177639b4c0d062bad6717d328a7ebee88a71f4294f9a5b0bc5`.
Every input hash is unique, and the fixed ordered input root is
`e3011f74256fe39881eda3636533ec4352f7b4d2c4386e12d775ccc031b6d2e8`.
The pure compiler emits strict schema-v4 definitions for all six provisional
family signatures, passes the nonretired-family boundary, and projects every
definition back to its exact ordered signature. Exact definition identity and
name-free D4 identity remain separate.

A public derivation witness reconstructs and binds the domain, case, family
signature, compiled definition, exact hash, D4 hash, and structural state/work
proof. The proof counts conservative board/ply layers without applying an action.
For two/three initial pieces per role, state bounds are 14,364/31,920 for fixed
counts, 26,334/67,032 for A-converts-B, 19,836/67,032 for A-captures-B, and
40,603/181,051 for convert-versus-capture; the maximum declared
actor-vector candidate bound is 48. These are safe upper bounds, not reachable
state counts or gameplay measurements.

The focused feasibility suite passes 19/19. Fixed domain, input, definition, D4,
witness, and ordered-enumeration goldens detect identity drift; exhaustive input
hash uniqueness, all six family projections, every goal frame, independent role
vectors, both setup counts and first players, D4 metamorphism, proof formulas,
hostile parser/witness mutation, and import/call purity are covered. Independent
semantic and hostile-boundary reviews found no implementation P0–P2 issue; two P3
coverage gaps were closed by the ordered root/uniqueness and B-first 3+3 tests.
The complete dependency-free suite passes 553/553 tests in 347.078 seconds.

This checkpoint deliberately has no initial-goal or mobility gate, D4-orbit
census, actual density/branching result, final family membership, registry,
search envelope, gameplay, solver, agent, or outcome. In particular, two-piece
`CONNECT_EDGES` setups cannot span a 3×3 board and must be reported rather than
silently repaired by the next census.

## Next action

Close Plan 0012. Its explicit recommendation is to create a separate
development-atlas plan over the six supported family cells, using only the 3+3
common-support core and an outcome-free, D4-aware selector. That later plan must
freeze the registry, search envelope, nominal exposure, historical exclusions,
orientation schedule, and evaluator protocol before producing gameplay.

## Outcome-free feasibility census checkpoint

The complete provisional domain was reconstructed without applying an action,
constructing a terminal result, calling an agent or solver, or reading a gameplay
outcome. Of 214,368 exact inputs and 102,336 name-free D4 orbits, 71,384 exact
inputs and 24,208 D4 orbits pass all three gates: neither role initially has its
goal, every CONNECT role has an action-aware structural material upper bound of
at least three pieces, and both roles have at least one legal initial action.

The sequential exact/D4 counts are 214,368/102,336 raw,
89,712/30,496 with no initial goal, 72,576/24,608 after also requiring connection
material, and 71,384/24,208 eligible. Initial mobility alone passes
212,376/101,504; all 1,992 exact and 832 D4 mobility failures are A-side CONVERT
positions. The complete rejection-reason combination partition is retained, so
overlapping goal, material, and mobility failures are not collapsed.

All six provisional family cells retain eligible support:

| Family | Raw exact / D4 | Eligible exact / D4 | Supported strata | Eligible D4 per supported stratum |
|---|---:|---:|---:|---:|
| `push-hop-race-v1` | 58,464 / 39,456 | 5,064 / 3,528 | 48 | 12–131 |
| `swap-hop-network-v1` | 38,976 / 19,968 | 6,128 / 3,168 | 16 | 194–202 |
| `convert-push-front-v1` | 38,976 / 19,968 | 10,640 / 5,504 | 32 | 138–201 |
| `capture-hop-hunt-v1` | 19,488 / 9,984 | 5,720 / 2,976 | 16 | 164–208 |
| `convert-capture-duel-v1` | 19,488 / 2,688 | 18,824 / 2,576 | 16 | 89–227 |
| `push-swap-networks-v1` | 38,976 / 10,272 | 25,008 / 6,456 | 16 | 402–405 |

Exactly 144 of 176 strata are eligible and nonempty. The 32 unsupported strata
are precisely every 2+2 setup for fixed-count `swap-hop-network-v1` and
`push-swap-networks-v1`: two pieces cannot make an orthogonal connection across a
3×3 board, while those actions cannot create a third owned piece. This rejects
those setup cells, not either family. The 3+3 setup is common to all six families,
all goal-frame representatives, all four ordered vector-profile pairs, and both
first players. Its minimum eligible supply is 12 D4 orbits in each of eight
`push-hop-race-v1 / REACH_REACH_SAME` strata, enough for a bounded later pilot but
not evidence that all families are equally difficult or strategically viable.

The census retains exact initial occupancy, legal-action, occupied-dependency,
direct-effect, structural-state, and state/action candidate-work distributions.
Eligible structural state upper bounds span 14,364 through 181,051 and remain
conservative bounds rather than reachable-state measurements. In particular,
CONVERT's connection-material support is only a necessary structural upper-bound
test, not a proof that connection can be achieved in play.

The canonical 1,055,162-byte aggregate has evidence digest
`ade64ebaaf9892848e03c2312786a6ef3825f3c82f4311e16a9c810711d035d2`.
Its ordered case-to-D4 root is
`e016d4644645595030914f496372c7d07cf2658def25b6c18394a339589100a6`,
sorted orbit-witness root is
`3eccec7f3eb54a9eb7cb69ad707a7c6831426682fdcac9648c3f388919008853`,
and sorted eligible-D4 root is
`6b96cf4ee19d708c61c941c5759c46db0fb0420f2f820959584dd5f1e34d0108`.
The optimized identity path matches the public compiler/D4 descriptor byte for
byte on 391 fixed cases covering all 176 strata. Every one of 214,368 cases also
passes all eight transformed initial-measurement checks: 1,714,944 checks and
zero violations, with measurement root
`e77c7e9cdebdab1251969bcbb5b8c7507849b560c3bf822937362e584960aebe`.

The focused full-census suite passes 8/8 in 304.297 seconds. Public coordinate
D4 authority, descriptors, purity, fixed counts, family and stratum partitions,
gate-reason combinations, distributions, roots, validator tamper rejection,
cache detachment, compactness, and forbidden gameplay-layer boundaries are
covered. Independent output comparison reproduces every global and family count;
independent implementation review reports no remaining P0–P3 finding. The
complete dependency-free suite passes 571/571 in 651.869 seconds.

No final registry, search envelope, selected atlas member, solver label, sampled
profile, gameplay trace, reservation, experiment run, or outcome was created.
