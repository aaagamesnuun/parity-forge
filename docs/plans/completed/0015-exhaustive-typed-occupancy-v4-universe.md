> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Plan 0015 — Exhaustive typed occupancy-v4 universe and blind partition

## Status

Closed on 2026-09-05, pre-outcome, transition-free. The scientific breadth result is
`BREADTH_FLOOR_NOT_MET`; the repaired history implementation passed the full
regression (1,177 tests in 5,148.015 seconds, two intended skips), accepted at
commit `1fe53927c`. Partition is `NOT_STARTED`; its skipped completion item is
deliberately not marked performed. Plan 0016 is a separate exploratory pilot.
Plan 0014 is complete and its report-only
attestation does not identify a fair standalone game. This plan replaces the
hand-selected six-family search lane with a closed enumeration of the current
isotropic occupancy-v4 grammar. It creates no gameplay result and does not
consume the frozen Plan-0013 confirmation candidate block.

Slice 1 is complete and outcome-free. The standalone pure typed-universe package
closes every preregistered semantic, spatial, profile, skeleton, witness,
histogram, endpoint, and root identity at descriptor
`05826dc2da02890f3f562ee2d6febda523c58837affb757b5dff6d62c074e6ab`.
Its production imports contain no forbidden capability, the frozen legacy
package initializer remains byte-identical, and independent hostile reviews
report no unresolved P0-P3 finding. The dedicated 47-test boundary passes in
1,119.141 seconds, and the complete dependency-free suite passes 921/921 in
2,188.935 seconds with two intended opt-in skips. Slice 2 is also complete:
strict canonical-wire compilation and full source projection close every
declared factor and transform at compiler/test blobs `95bb7581…251a` /
`d796545f…3113`. Its 35-test boundary passes in 857.518 seconds and two
independent final reviews report P0=P1=P2=P3=0 after closing a pre-acceptance
instance-method-shadow finding. The resulting complete dependency-free suite
passes 956/956 in 3,085.160 seconds with the same two intended opt-in skips.
Slice 3's one-carrier `initial_structure` boundary is also complete at source/
test blobs `c7d806aa…38c1` / `18ff5274…7b`. Its tight count table closes 55
states, 610 directed edges, 1,470 entries, and 22,428 layer memberships at root
`de2e65f28be1f60aff4712c23c8681ea7945324886a2954a0f8d8cbfa905d226`,
with maxima 115,194 state weight and 2,070,432 action/scan work per schedule.
The focused 30-test boundary passes in 9.618 seconds, all 33 tests in the
dedicated current file pass within the 989/989 complete suite in 4,357.623
seconds with two intended skips, and independent semantic and hostile-boundary
audits report P0=P1=P2=P3=0. Slice 3's factorized `static_census` implementation
is now also complete at source/test blobs
`fd5fb486ea33fac840b2951ff0a3680a3c221058` /
`93aa6d428b5378f06027438c04d6a38f9ad25bae`, with raw SHA-256
`f7205f8113b37d28bd003884438fb88bb19eb2a608fb12263c979faa2670d460` /
`510a28556955008be2f61336323b38351872137fe9795a01ae2a23c2e68bec83`.
Its exact setup table and skeleton authority roots are
`f1bc82d1cfbaac9933e097aba2f4118737e19f7a190f06bc9f0a83add17c2e23`
and `53221ffdbd42e4c86e9c54eadb6e0659bf71ff350dcdf0944b062ce56c3e1488`.
The dedicated 36-test boundary passes in 601.045 seconds, the complete suite
passes 1,025/1,025 in 4,908.329 seconds with the same two intended skips, and
two independent final reviews report P0=P1=P2=P3=0. The audited evidence edge
then passed its 119-test boundary and the complete 1,144-test suite. The single
authorized production census sealed `COMPLETED`; public recovery returned
`VERIFIED_NO_OP`, and independent reconstruction matched report SHA-256
`fa7daf48992f2b186fd980d42f670beda651b1adc7fe4c1fb62b67d1fdc05f97` and
terminal seal `299a76910ee7fa072c0ec1b8cadb31d13714b922d0dcfa7c65c06e96e2306e34`.

## Objective

Construct one deterministic, inspectable map of every coherent typed two-role
program expressible by the current seven action primitives, three goal
primitives, complete D4 goal relations, and complete nonempty D4-invariant Moore
vector profiles. Remove semantic aliases and the full role-swap closure of the
six already evaluated Plan-0013 regions before setup generation. Then partition
static-eligible setup carriers into disjoint development, future-reserve, and
untouched sets without observing an outcome or applying an action.

This plan answers whether the current language contains a broad, auditable
unseen search surface. It does not answer whether any member is fair, strategic,
replayable, or fun.

## Why this plan

The original `A = PLACE / B = MOVE` lane and later capture/two-runner variants
were narrow hypotheses. Plan 0013 widened the action vocabulary but still chose
only six signatures by hand; its formal report contains 14 frontier pairs, all
exactly first-player-dominant. Continuing to tune those six cells would spend
more evidence inside a region that has no surviving standalone-game candidate.

The current DSL already expresses substantially more structure. A complete
static grammar census can expose that breadth without inventing a new primitive,
using an outcome proxy, or peeking at a held-out block. The smallest next step is
therefore to close and factor this existing universe first. Dynamic structural
probing belongs to a separately versioned Plan 0016.

## Fixed scope

- two players, deterministic complete information, alternating one action;
- schema v4 and its existing terminal contract, unchanged;
- occupancy state kernel on a 3×3 square board;
- one action, one goal, and one piece kind per role;
- fixed `max_plies = 18`, retained only in later compiled definitions;
- action primitives `PLACE`, `MOVE`, `MOVE_CAPTURE`, `PUSH`, `SWAP`, `HOP`,
  and `CONVERT`;
- goals `CONNECT_EDGES`, `REACH_EDGE`, and `ELIMINATE`;
- all nonempty D4-invariant subsets of the local Moore neighbourhood; and
- initial role counts 0 through 3 with total count 1 through 6.

`CAPTURE_STEP` remains a retired signature alias of `MOVE_CAPTURE` and is not
enumerated. No new action, goal, terminal policy, board topology, hidden state,
chance, simultaneous move, or compound role program is added. The completeness
claim is limited to this isotropic local occupancy-v4 envelope, not schema v4 in
all possible parameterizations and not abstract games generally.

## Closed typed grammar

For `CONNECT_EDGES` and `REACH_EDGE`, each of the seven actions forms a role
atom. `ELIMINATE` forms a coherent role atom only with `MOVE_CAPTURE` or
`CONVERT`, the two current actions capable of reducing opposing material.
Therefore the grammar has 16 coherent role atoms.

The fixed semantic arithmetic is:

- 16 role atoms and 256 ordered A/B atom pairs;
- 36 legacy-only spatial pairs rejected by the existing schema-v4 admission
  rule;
- 220 admitted ordered signatures;
- 10 admitted signatures fixed by role swap;
- 115 role-swap semantic classes; and
- 109 fresh semantic classes after removing the six Plan-0013 classes and their
  reverse-role images.

The six excluded semantic orbits are fixed by their public role programs, not by
reading the Plan-0013 candidate artifact:

1. PUSH/REACH_EDGE — HOP/REACH_EDGE;
2. SWAP/CONNECT_EDGES — HOP/REACH_EDGE;
3. CONVERT/CONNECT_EDGES — PUSH/REACH_EDGE;
4. MOVE_CAPTURE/ELIMINATE — HOP/REACH_EDGE;
5. CONVERT/ELIMINATE — MOVE_CAPTURE/ELIMINATE; and
6. PUSH/CONNECT_EDGES — SWAP/CONNECT_EDGES.

Exclusion applies to each whole semantic orbit across every goal frame, vector
profile, setup, first-player value, and role-swapped image. It is not limited to
the 144 development pairs and does not require opening the unused candidate
block.

## Complete spatial quotient

D4 has two direction orbits on the Moore neighbourhood: four orthogonal and four
diagonal directions. Its complete nonempty invariant profile set is therefore:

- `ORTHOGONAL_4`;
- `DIAGONAL_4`; and
- `KING_8`.

`PLACE` has profile `NONE`; every other action uses exactly one of the three
profiles.

The complete ordered D4 quotient of goal relations has 14 frames:

- CONNECT/CONNECT: same axis, perpendicular;
- CONNECT/REACH: aligned, perpendicular;
- CONNECT/ELIMINATE: one frame;
- REACH/CONNECT: aligned, perpendicular;
- REACH/REACH: same, opposite, adjacent;
- REACH/ELIMINATE: one frame;
- ELIMINATE/CONNECT: one frame;
- ELIMINATE/REACH: one frame; and
- ELIMINATE/ELIMINATE: one frame.

The role-neutral quotient has 10 goal-frame classes. Enumeration must retain an
inverse witness for the ordered source, D4 transform, role-swap flag, goal frame,
and vector profiles.

## Skeleton identity and fixed arithmetic

A profiled skeleton contains both typed role programs, their vector profiles,
and one ordered goal frame, but no setup, first player, display name, or result.
Its canonical bytes are the minimum across all D4 transforms of both the ordered
source and its complete role swap. Role swap exchanges action, goal, vector
profile, spatial target, and ownership together. First player and role display
letters never create mechanical asymmetry.

The preregistered arithmetic is:

- 3,300 schema-admitted ordered profiled skeletons;
- 66 role-swap-plus-D4 self-isomorphic skeletons, rejected as
  `TOO_SYMMETRIC`;
- 198 ordered skeletons in the full swap closure of the old six regions,
  representing 99 asymmetric role-neutral orbits; and
- `(3,300 - 66 - 198) / 2 = 1,518` fresh canonical asymmetric skeletons.

The implementation enumerator and a structurally independent golden derivation
must agree on every count, stabilizer histogram, identity, endpoint, and ordered
root. A disagreement is `UNIVERSE_NOT_CLOSED`; no subset may be published.

## Setup master census

The syntactic master lattice includes all 15 ordered count pairs
`0 <= A_count,B_count <= 3`, excluding only `(0,0)`. Across nine cells this is:

```text
sum C(9, A_count) C(9 - A_count, B_count) = 6,798
```

for each canonical skeleton. Non-`PLACE` roles with zero initial pieces remain
in the master census and are then explicitly rejected as
`ZERO_ACTOR_WITH_NONPLACE`; this distinction is required for the fixed totals.

The fixed upper-domain arithmetic is:

- 10,319,364 labeled setup rows (`1,518 × 6,798`);
- 20,638,728 paired first-player definition members; and
- 5,111,055 D4 setup carriers after frame-stabilizer factoring.

The D4 carrier value must independently reconstruct from all ordered carriers
11,085,600, self-isomorphic contribution 215,508, and old-six swap-closure
contribution 647,982. The census is streamed one skeleton at a time; retaining or
materializing the full domain is forbidden. Peak retained setup state may not
exceed one 6,798-row skeleton shard plus fixed aggregate counters.

## Compiler wire and transform contract

The authoritative bridge value for this capability-minimal plan is exact
canonical schema-v4 JSON, not an imported `GameDefinition` object. Ordinary
`parity_forge.dsl` import executes the frozen legacy package initializer and
loads the engine, so production compilation and inverse projection live in the
pure sibling package and import only the sealed typed universe plus the standard
library. Tests must differentially prove that every emitted wire value is
accepted unchanged by the authoritative parser and has identical canonical JSON
and definition hash.

The strict compiler input has three nested layers: one 3×3 setup with canonical
disjoint A/B position tuples and zero through three pieces per owner except the
all-empty setup; one exact ordered/oriented fresh profiled skeleton plus setup;
and one member with first player A or B. The 10,319,364-row master domain uses
only the 1,518 canonical fresh representatives. Compiler transforms additionally
accept their complete ordered/oriented D4-plus-role-swap transport closure so
that equivariance can be stated without silently canonicalizing and losing an
inverse. Self-isomorphic and old-six skeletons remain rejected.

For a member `m = (s, X, Y, f)`, fix the transformations as:

```text
D_g(m) = (g(s), g(X), g(Y), f)
O(m)   = (s, Y, X, f)
P(m)   = (s, X, Y, opposite(f))
R(m)   = (swap(s), Y, X, opposite(f))
```

`O` is setup-owner swap only; it does not exchange role programs or first-player
labels. `R` is complete role relabeling and exchanges programs, goal targets,
profiles, setup owners, first player, and the role-local DSL piece identifiers
`a`/`b` together. D4, O, P, and R must obey their group and commutation laws.
First-player expansion is ordered `(A_FIRST, B_FIRST)` and P reverses that pair.

Emitted names are `pf15-` plus the complete typed-member hash. Names are
non-mechanical; an exact DSL transform comparison replaces the source name with
the independently compiled target name. Inverse projection accepts only bounded
canonical JSON in the compiler's own image, reconstructs every source field,
checks the derived name, and requires byte-identical recompilation. Injectivity
must follow from full field reconstruction rather than from collision resistance.

## Transition-free eligibility

Plan 0015 never applies an action. Its production closure must not import or call
`engine`, `apply_action`, terminal/result logic, replay, play, a solver, an agent,
or telemetry generation. Where initial legality or goal shape is needed, a new
closed initial-structure kernel derives it directly from strict DSL fields;
tests may differentially compare that pure kernel with the existing engine, but
the production closure may not depend on the engine module.

Each carrier records independent reason fields rather than a composite score:

1. strict compile, parse, and inverse projection;
2. fresh semantic orbit membership;
3. role-swap-plus-D4 asymmetry;
4. nonempty initial actor unless that role uses `PLACE`;
5. neither goal already satisfied initially;
6. at least one initial legal action for each role;
7. optimistic action-aware goal reachability;
8. finite count-lattice reachability within 18 alternating plies; and
9. a finite structural work bound.

The count lattice is an explicit over-approximation over role counts 0 through 9:
`PLACE` adds one own piece, MOVE/PUSH/SWAP/HOP preserve counts,
`MOVE_CAPTURE` may reduce the opponent by one, and `CONVERT` adds one own piece
while reducing the opponent by one. Failure proves only a static impossibility;
success is not dynamic reachability.

### Fixed initial-structure kernel

For one role, let `X` be its occupied cells, `Y` the opponent's occupied cells,
`E` the empty cells, `V` its declared vectors, `y = x + v`, and `z = x + 2v`.
The kernel computes hypothetical preterminal legal actions for both roles even
when an initial goal is true. It creates no state or action object. Exact counts
are:

```text
PLACE         |E|
MOVE          sum[x in X,v in V] [y in E]
MOVE_CAPTURE  sum[x in X,v in V] [y is in bounds and y not in X]
PUSH          sum[x in X,v in V] ([y in E] + [y in Y and z in E])
SWAP          sum[x in X,v in V] [y is in bounds and y not in X]
HOP           sum[x in X,v in V] ([y in E] + [y occupied and z in E])
CONVERT       sum[x in X,v in V] [y in Y]
```

`CONNECT_EDGES` uses orthogonal connectivity of owned cells and its two opposite
edge masks; it never uses the action profile. `REACH_EDGE` tests an owned cell
against its target edge. `ELIMINATE` is true exactly when the opposing setup set
is empty. Empty-destination, occupied-dependency, opponent-dependency,
friendly-dependency, and direct-opponent-effect action counts remain separate;
their exact sums must reconstruct the legal count.

Optimistic reachability is a necessary-condition relaxation, not the older
role-local heuristic. For role `r`, `S_r` is the whole board for `PLACE` and
otherwise the closure of its initial positions under its own vectors plus the
opponent's vectors when the opponent has an initial actor and uses `PUSH` or
`SWAP`. This second term is required because schema v4 checks the opponent's
goal after an action and those primitives can relocate the goal role's pieces.
`REACH_EDGE` and `CONNECT_EDGES` are tested on `S_r`. For `ELIMINATE`, each
initial opponent position `y` has a separate lineage support `T_y`: closure
under the opponent vectors for `MOVE`, `MOVE_CAPTURE`, `PUSH`, `SWAP`, or `HOP`,
and the singleton `{y}` for `PLACE` or `CONVERT`. The relaxation passes only if
the initial goal is true or every `T_y` intersects `S_r`. It ignores blockers,
target supply, scheduling, terminal order, and destructive interference.

### Fixed count lattice and work proof

The count domain is the 55 pairs `(a,b)` with nonnegative counts and
`a + b <= 9`. From local `(own, opponent, empty) = (o,p,e)`, the exact
necessary-resource relaxation is:

```text
PLACE         (o+1,p) if e>0
MOVE/PUSH/HOP (o,p) if o>0 and e>0
SWAP          (o,p) if o>0 and (e>0 or p>0)
MOVE_CAPTURE  (o,p) if o>0 and e>0; also (o,p-1) if o>0 and p>0
CONVERT       (o+1,p-1) if o>0 and p>0
```

It retains every real count edge while removing impossible full-board
self-loops. For each initial count pair, A-first and B-first form separate exact
layers from ply 0 through ply 18; they are never unioned. Necessary goal sets are
own count at least one for `REACH_EDGE`, own count at least three for
`CONNECT_EDGES`, and opponent count zero for `ELIMINATE`. The carrier must have a
minimum-ply witness for both goal roles under both first-player schedules.

For `N(a,b) = C(9,a) C(9-a,b)`, each schedule records:

```text
S = sum[p=0..18] sum[(a,b) in layer[p]] N(a,b)
W_action = sum[p=0..17] N(a,b) U_actor(a,b)
W_scan   = sum[p=0..17] N(a,b) C_actor(a,b)
```

Here `U` is empty cells for `PLACE` and `own * |V|` otherwise; `C` is nine
candidate-cell iterations for `PLACE` and `own * |V|` otherwise. `W_scan` counts
candidate-loop iterations, not occupancy-cell lookups. Universal per-schedule
ceilings are `S <= 373,958` and `W_action,W_scan <= 25,507,872`; the complete
49-action-pair table must independently recover maxima 115,194 and 2,070,432.

Ordinary row reasons are structured `(code, role, first_player-or-null)` atoms
in fixed gate/role/tempo order. The closed codes are
`ZERO_ACTOR_WITH_NONPLACE`, `INITIAL_GOAL_SATISFIED`, `INITIAL_IMMOBILITY`,
`OPTIMISTIC_GOAL_UNREACHABLE`, and
`COUNT_LATTICE_GOAL_UNREACHABLE_WITHIN_18`. Only the final code carries a
first-player value. Every overlapping reason is retained; eligibility is exactly
an empty reason tuple. Compiler, universe, asymmetry, invariance, and work-proof
failures abort the census instead of becoming row reasons.

### Fixed setup-orbit factorization

Setup order is count-pair order `(0,1)` through `(3,3)`, skipping `(0,0)`, then
lexicographic A positions and lexicographic B positions within the remaining
row-major cells. For each canonical fresh skeleton, setup equivalence uses its
exact D4 stabilizer, never stabilizer size alone. The only admitted subgroup
signatures and skeleton counts are:

```text
{I}: 141
{I,FLR}: 810
{I,FTB}: 165
{I,R180,FLR,FTB}: 396
D4: 6
```

Canonical setup bytes, not their hash, select an orbit representative. Its
weight is the number of distinct stabilizer images. Per-group orbit counts are
6,798, 3,511, 1,827, and 970; global weights are 1,184,850 of weight 1,
3,294,033 of weight 2, 627,732 of weight 4, and 4,440 of weight 8. Their count,
weighted sum, and paired-first-player sum must be exactly 5,111,055,
10,319,364, and 20,638,728. Complete role swap has already selected the 1,518
skeleton cross-section and does not divide setup orbits again. Owner-only swap
and first-player toggle are not equivalences.

Slice 3 is split into a one-carrier `initial_structure` authority and a
`static_census` setup/orbit/aggregation layer. A prepared skeleton value may
cache only immutable role, vector, edge, descriptor, and count-table data for
one shard. Every fast-path carrier must still pass the strict nested compiler
boundary and match the prepared skeleton's canonical bytes. Result values bind
the exact carrier identities, role-local gate facts, two-tempo count references,
separate descriptor groups, complete structured reasons, and a domain-separated
digest. No public mutable cache, generic callback registry, full-domain set or
sort, outcome field, rank, score, history, selection, or evidence I/O is added.

Structural, description-clause, operational/substep, primitive/concept, vector-
cardinality, density, contact, and dependency measurements remain separate.
They cannot be combined into a score, thresholded as quality, or used to rank
partition membership.

Both Slice-3 implementation boundaries are complete. The strict ordinary and
prepared one-carrier paths derive identical fully rederivable results, while an
output-only snapshot bridge returns fresh canonical result bytes and their
result hash without weakening the public parser. The factorizer closes the
6,798-row setup table, five exact stabilizer partitions, 1,518-skeleton
authority, one-shard leaf/summary roots, compact checkpoint aggregation, and a
strict output-only report. Its one-shot builder prepares and derives each
skeleton exactly once and retains only the setup table, compact shard summaries,
and current row/shard state. The incremental checkpoint path is a strict
diagnostic interface with repeated prefix validation, not the production
execution path. No 5,111,055-carrier production stream, report root, eligibility
total, rejection total, history projection, or evidence artifact exists yet.

### Pre-registered static-census production edge

The production stage is fixed as
`plan0015-factorized-static-census-stage-v1` under evidence protocol
`plan0015-factorized-static-census-evidence-v1`. Its only public operations are
`run` and `recover` with one exact repository-top path. `run` accepts no table,
shard, report, callback, clock, resume token, selection, or outcome input. After
durable reservation and attempt publication it calls
`build_static_census_v1()` exactly once with no arguments. `recover` never calls
the builder, advances a checkpoint, or resumes a calculation.

The fixed store is
`experiments/runs/plan0015-factorized-static-census-evidence-v1`. It contains
one root bootstrap, one stage directory, an optional contradiction, operational
`.locks` and `.pending` directories, and only these ordered stage artifacts:

```text
reservation.json
attempt.json
static-census-report.json
completed.json | failure.json | orphaned.json
terminal-seal.json
```

The report artifact is the UTF-8 bytes returned by
`canonical_static_census_report_json_v1` without reformatting, compression, or
field removal. It has a fixed 256 MiB byte ceiling, 5,000,000-node ceiling, and
depth-32 ceiling. Its ordinary whole-file SHA-256 is distinct from the embedded
domain-separated `report_digest`. `completed.json` stores the report body
reference and only summary anchors re-extracted from the validated report; it
does not duplicate the report. The 9,462,884-byte synthetic complete report is
a lower-shape resource fixture, not a production-size prediction or census
result.

The only accepted lifecycle is:

```text
ABSENT -> BOOTSTRAPPED -> RESERVED -> ATTEMPTED
       -> REPORTED -> COMPLETED -> TERMINAL(COMPLETED)
       -> FAILED -> TERMINAL(FAILED)
       -> ORPHANED -> TERMINAL(ORPHANED)
```

Bootstrap alone has consumed no calculation and `run` may continue it only
after current-source resealing. Reservation or attempt without a complete
report recovers to `ORPHANED`; it is never rerun. A valid report published after
attempt but before completion recovers by constructing only completion and
terminal artifacts. A completed, failed, or orphaned body without a terminal
recovers by sealing only that terminal. A valid terminal makes later `run` and
`recover` verified no-ops. Multiple lifecycle bodies, report/failure coexistence,
unknown catalog entries, mismatched pending/public bytes, or any identity drift
is an immutable contradiction. Once a valid report or completion exists, an
exception cannot replace it with failure.

Every publication uses a bounded canonical pending file, file `fsync`, private
read-only mode, no-replace hard-link publication, destination-directory `fsync`,
pending unlink, and both-directory `fsync`. Readers walk from a filesystem
anchor by directory descriptor and require `O_NOFOLLOW|O_NONBLOCK`, exact
regular-file type, allowed mode, single link after reconciliation, fixed size,
bounded reads, and stable before/after descriptor metadata. Symlinks, FIFOs,
sockets, devices, external hard links, path swaps, unknown entries, and a second
nonblocking stage lock fail closed. Locks and pending files are operational and
never evidence identities.

Production source must retain the exact Slice-3 calculation blobs for package
initializer `6a7aba9e…5bd3`, typed universe `55cc8f7c…71f7`, compiler
`95bb7581…251a`, initial kernel `c7d806aa…38c1`, and static census
`fd5fb486…1058`. The source-closure implementation will pin the commit that
first contains this preregistration and admit only a merge-free descendant whose
complete changed-path set is `.gitignore`, four named evidence-edge modules,
and their four matching test files. The active plan must remain byte-identical.
The recursive production closure is exactly the five sealed calculation files
plus `static_census_reconstruction.py`, `static_census_protocol.py`,
`static_census_evidence.py`, and `static_census_stage.py`; every record retains
path, Git blob, raw SHA-256, and byte count. Current HEAD/tree and every current
closure/plan byte are resealed immediately before the first publication, after
calculation before report publication, and again before returning a terminal.

Stored-report reconstruction is a separate pure implementation. It accepts
only bounded canonical bytes, independently validates both embedded authority
descriptors, all 1,518 ordered shard summaries, exact reason/contact/supply/work
arithmetic, every shard commitment, every report-level aggregate/root, the
actual body canonical bytes, `report_digest`, and whole-file reference. It does
not traverse 5,111,055 carriers. Thus compact recovery proves the immutable
report's provenance and internal reconstruction from all shard summaries; it
does not claim an independent leaf-semantic rerun. Recomputing a leaf or shard
belongs to a separately declared read-only audit and can never replace or extend
the one authorized production attempt.

## History and candidate firewall

The production code never imports a Plan-0013 selection/candidate builder and
never reads the candidate artifact or any candidate-bearing source path. The six
public semantic orbits are removed before setup enumeration, which removes both
their development and candidate regions inclusively.

All other definitions exposed before the fixed cutoff enter through a separate
identity-only history projection. It retains exact definition identity, D4
identity, role-neutral identity, schema version, and source carrier identity,
but no result, winner, score, trace, agent, family assessment, or metric. Unknown
sources, omitted sources, outcome-bearing adapter fields, or unresolved aliases
terminate with `HISTORY_PROJECTION_INCOMPLETE`.

The fixed history cutoff is Plan-0015's opening commit
`0d041629bb584f47e7f10f1358f89e6920fee299` and tree
`4adb84cf439f07fad579d4a6a9999c07bb6f4853`. Its complete `experiments/**/*.json`
inventory has exactly 152,749 paths and is classified without reading an outcome
artifact:

- exactly 66 paths are the already authenticated Plan-0013 prior-gameplay
  inventory at commit `6910b6cc03c03701c56bc44d98bb9cf8ac5bf03c` / tree
  `6bc44b1d51fcf67f691e5cc8106b1b1140947007`;
- exactly 152,678 paths lie below the Plan-0013 evidence subtree at Git tree
  `40f4b65f913a842a43e1b3a092a40cbb9933e489`; that entire generated domain is
  already removed by the six-public-semantic-orbit closure, so the adapter must
  authenticate and classify the subtree but must not open any member, selection,
  candidate, journal, trace, or outcome artifact; and
- exactly five paths lie below the Plan-0014 reconstruction subtree at Git tree
  `beaed7c4bb82d0aa8d3e8e3d1a8f1d942de03f96`; Plan 0014 generated no definition,
  so this subtree is likewise authenticated and classified without opening its
  artifacts.

The source-scanning adapter therefore reads exactly the 66 previously frozen
source blobs plus the seven frozen Plan-0012 synthetic fixtures, and nothing
else. The cutoff-tree classifier proves that no experiment JSON source was
omitted. Its output is an exact-key, bounded, canonical identity projection;
the blind partition consumes only that detached projection and never receives
raw history bytes or paths to candidate-bearing artifacts.

The implemented projection uses a standard-library-only strict wire adapter;
importing it must not import the legacy package or its engine. All 66 blobs and
all seven fixture wires are mandatory and authenticated before interpretation.
Exact and D4 identities remain unchanged. The new role-neutral identity takes
the canonical minimum over D4 and complete owner/program/first-player exchange,
with global piece-kind alpha normalization in each image. Global label equality
and opponent-goal references are preserved; owner-local renaming is not enough.

The additional source-only Plan-0013 `swap-simultaneous-connect-v1` fixture is
authenticated separately in tests at source blob
`ef1e99a87be4b0cf2e9e4fe30557b111fa979a7d`. Its two-ply horizon and single-vector
SWAP action remain outside this 18-ply isotropic compiler image under every
D4/role/alpha image. It is not an eighth member of the seven-fixture projection,
and this witness does not open a Plan-0013 experiment artifact.

## Blind partition

The selection unit is a role-neutral mechanical skeleton/setup carrier. Only
after partitioning is the carrier expanded into a paired A-first/B-first DSL
unit. The two definitions remain separate games; their aggregate can never be
called single-game fairness.

Eligible carriers are stratified by:

```text
canonical profiled skeleton × {CONTACT, SEPARATED}
```

`CONTACT` means at least one cross-owner initial adjacency along either role's
declared vector profile; all other setups are `SEPARATED`. The class and all
static gates must be invariant under D4 and role swap.

Within each stratum, a domain-separated hash of only the role-neutral skeleton,
class, and setup identity defines rank. Display names, first player, history
root, complexity values, metrics, and outcomes are not rank inputs. History
collisions are skipped after ranking and never backfilled from another stratum.

A supported stratum requires at least five fresh eligible carriers:

- two `DEVELOPMENT` carriers, using different resource-count pairs when supply
  permits;
- two disjoint `FUTURE_RESERVE` carriers, also resource-diverse when possible;
- at least one `UNTOUCHED` carrier; and
- no cross-partition exact, D4, or role-neutral collision.

There is no backfill across strata. Empty and short strata retain complete count
and reason evidence. Maximum development exposure is 6,072 carriers and 12,144
paired first-player definition members; future reserve has the same maximum but
is not exported to the next probe. Untouched members are committed by root and
count rather than serialized wholesale.

## Breadth floor and terminal decisions

`READY_FOR_TERMINAL_BLIND_PROBE` requires:

- all 109 fresh semantic classes have at least one supported development
  stratum;
- all 1,518 canonical skeletons are supported or have a complete static
  rejection proof;
- all seven action primitives occur in the role-neutral incidence projection;
- all 14 ordered and 10 role-neutral goal-frame classes reconstruct;
- all three vector profiles occur;
- CONTACT and SEPARATED both occur globally;
- every supported stratum contains two development, two future-reserve, and at
  least one untouched carrier; and
- every partition and history intersection is exactly disjoint.

If the complete report exists but this floor is not met, the scientific terminal
is `BREADTH_FLOOR_NOT_MET`. That closes this isotropic v4 envelope normally; it
does not authorize quota relaxation, selective family rescue, result-based
reranking, or a new primitive inside this plan.

Integrity failures publish no partition and fail closed with the applicable
code: `UNIVERSE_NOT_CLOSED`, `OUTCOME_CAPABILITY_PRESENT`,
`CANDIDATE_BLOCK_TOUCHED`, `HISTORY_PROJECTION_INCOMPLETE`,
`SEMANTIC_ALIAS_UNRESOLVED`, `ROLE_TEMPO_FACTORING_FAILED`,
`PROXY_INVARIANCE_FAILED`, `PROXY_SELECTION_PRESENT`, `HOLDOUT_COLLISION`,
`WORK_BOUND_UNPROVED`, `SCOPE_OVERCLAIM`, or `AUDIT_NOT_CLEAN`.
`STRATUM_SUPPLY_SHORTFALL` is a per-stratum census reason, not permission to
backfill.

### 2026-09-05 necessary-condition closeout

The existing sealed report has now been publicly reconstructed and independently
grouped. Nine of 109 semantic classes, comprising 51 skeletons, have zero
static-eligible supply. All 3,036 contact/count-pair totals reconcile: 704 strata
are empty, 81 contain one to four, and 2,251 contain at least five before history
exclusion. For every stratum, fresh supply is a subset of static-eligible supply.
Consequently the all-109 supported-class condition is impossible regardless of
rank or historical exclusion, and `BREADTH_FLOOR_NOT_MET` is established.

The [negative report](../../../experiments/reports/0015-static-breadth-floor-negative.md)
preserves the source hashes, all nine class identities, and a read-only
reproduction. The decision criterion was preregistered; skipping the remaining
partition work is an explicit execution decision made after this proof, not a
preregistered early-stop procedure. No partition, member export, or replacement
terminal seal is produced. The original partition completion item below remains
unperformed. No selective rescue, quota change, or gameplay claim follows.

## Implementation slices

### 1. Grammar and canonical skeletons — complete

- Add a new pure module; do not modify frozen family or D4 identities.
- Enumerate the 16 role atoms, complete goal frames, and vector profiles.
- Implement strict profiled-skeleton parsing, hashing, D4-plus-role-swap
  canonicalization, inverse witnesses, old-region closure, and fixed arithmetic.
- Add independent closed-form/Burnside goldens and forbidden-import tests.

### 2. Compiler and inverse projection — complete

- Compile each skeleton/setup/first-player member into exact canonical schema-v4
  JSON without importing the legacy package.
- Require exact parse roundtrip and injective inverse projection.
- Prove D4, role swap, owner swap, and first-player pairing commute.
- Differentially prove authoritative parser, canonical-JSON, and definition-hash
  equality in tests only.
- Add no outcome-bearing production capability.

### 3. Factorized static census — complete

- [x] Implement the independent one-carrier static gates, pair-aware support,
  two-tempo count-lattice proof, work bounds, structured reasons, and separated
  descriptor groups.
- [x] Implement the 15-resource-pair master census stream by skeleton and exact
  frame stabilizer.
- [x] Retain complete rejection combinations, work bounds, shard roots, and
  aggregate roots without materializing the full carrier universe.
- [x] Run the authorized 5,111,055-carrier census exactly once and independently
  reconstruct its complete report and terminal lifecycle.

### 4. Exposure projection and blind partition

- [x] Freeze and implement the content-free cutoff-tree classifier over all
  152,749 experiment JSON paths. Its focused boundary passes 6/6 tests and the
  complete suite passes 1,150 tests with two intentional skips.
- [x] Accept the 66-source plus seven-fixture identity-only history adapter.
  Implementation and independent final review are complete; the focused
  boundary passes 33 tests and the full suite passes 1,177 tests in 5,148.015
  seconds with two intended opt-in skips. Its
  2,250 occurrences close as 1,179 exact, 1,175 D4, and 1,175 complete-role-swap
  identities across 73 source carriers; carrier/identity/projection roots are
  `51b7416d…2c40f`, `e26fbd0d…d26b93`, and `00973dcc…e2e3c9`.
- Historical collision enumeration and development/future-reserve/untouched
  commitment generation are not executed: the negative necessary-condition
  proof makes them irrelevant to this plan's scientific decision.

### 5. Evidence lifecycle

- [x] Pre-register a compact streaming reconstruction protocol and exact source
  closure.
- [x] Implement and obtain independent semantic, arithmetic, provenance,
  capability, and lifecycle
  audits before production.
- [x] Run the static-census stage exactly once; publicly recover and
  independently reconstruct every root.

## Definition of done

- [x] Independent derivations match 16/256/36/220/115/109 semantic counts.
- [x] All 14 ordered goal frames, 10 role-neutral frames, and three vector
  profiles are complete and uniquely represented.
- [x] Enumeration and independent derivation match 3,300/66/198/99/1,518
  skeleton counts and all stabilizer histograms.
- [x] Setup arithmetic matches 6,798, 10,319,364, 20,638,728, and 5,111,055.
- [x] Strict parser, canonical identity, inverse witness, D4, and role-swap tests
  reject aliases, mutation, and nonexact types.
- [x] Compiler and inverse projection are injective and commute with every
  declared transform and first-player pairing.
- [x] The one-carrier initial-structure authority reproduces every fixed gate,
  reason, descriptor group, count-table entry, and work bound under independent
  semantic and hostile-boundary review.
- [x] Production imports/calls contain no transition, terminal, outcome, solver,
  agent, replay, telemetry-generation, or candidate capability.
- [x] Every master carrier is eligible or has a complete static rejection proof;
  all gates and measurements are D4/role-swap invariant.
- [x] The complete identity-only history projection has no outcome field and no
  unknown source; its combined boundary and legacy-compatibility tests pass
  33/33, with independent final review reporting no unresolved P0–P3 defect.
- [ ] Development, future reserve, and untouched form a complete disjoint
  partition with no exact/D4/role-neutral collision. **Not executed:** unnecessary
  for the proven negative branch; this is not a completed partition.
- [x] The scientific report concludes exactly `READY_FOR_TERMINAL_BLIND_PROBE` or
  `BREADTH_FLOOR_NOT_MET`, without a fairness or quality claim.
- [x] Full dependency-free tests pass (1,177 in 5,148.015 seconds, two intended
  skips), all required independent audits report no unresolved P0-P3 finding,
  and project records contain the accepted result. Git checkpoint/archive remain
  the administrative closeout, not missing test execution.

### Final regression acceptance — 2026-09-05

The preserved log `/tmp/parity-forge-history-tests.ku8hkt/full-suite.log` ends
with `Ran 1177 tests in 5148.015s` and `OK (skipped=2)`. Independent log review
confirms no FAIL/ERROR. The two skips are the previously intended opt-in real
archived-evidence reconstruction tests. No production source/test changed during
the final documentation-only waiting slice.

Accepted pending-file Git blob identities, before the closeout commit:

| Path | Git blob |
| --- | --- |
| `research/parity_forge_history/history_identity.py` | `7d5d8ac52a4bfe5dd5a5bcf18648de6eefa2862c` |
| `research/parity_forge_history/history_pins.py` | `d0ff711533f85a43947c1f69acb47049fd2b5357` |
| `research/parity_forge_history/wire_identity.py` | `fffea8b914f617c49df898c7076aef62086a0b51` |
| `tests/test_history_capability_boundary.py` | `1edf90d12393d8a1dc8f73a31176b58465973352` |
| `tests/test_history_identity.py` | `d5450bef990df80c67607fc9bed7d26b0a85d7a6` |
| `tests/test_history_wire_identity.py` | `f04ba1e949d7d8f3dada59d56fd72a610e42e456` |

## Non-goals

- Do not apply an action, run a game, compute a terminal, solve a position,
  select an agent action, replay a trace, or derive gameplay telemetry.
- Do not read, allocate, export, evaluate, replenish, or replace the Plan-0013
  confirmation candidate block.
- Do not select with branching, complexity, contact, dependency, or any composite
  proxy score.
- Do not call static eligibility a candidate, survivor, fair game, strategic
  game, or fun game.
- Do not add `REMOVE_ADJACENT`, `SURROUND`, or any other primitive in this plan.
- Do not include a terminal-blind BFS; that requires a separately reviewed raw
  transition kernel and belongs to Plan 0016.

## Next action

This plan is archived with scientific result `BREADTH_FLOOR_NOT_MET` and
partition `NOT_STARTED`; its accepted implementation checkpoint is `1fe53927c`.
Retain all census evidence and the unopened Plan-0013 candidate block. Register
the next diagnostic scope separately and review its exact synthetic inputs,
expected fields, integration scope, and work limits before activation. The
[coverage/ranking option](../../designs/0016-complete-accounting-partition.md)
has a reviewed general resource-allocation proof and reproducible synthetic
check (5,272 integer-label patterns / 1,942,800 allocations, no game members).
It is not active: complete accounting and up to 4,502 development allocations
do not justify a gameplay budget. The
[single-game diagnostic draft](../../designs/single-game-diagnostic-contract.md)
is the smaller next question; it also is not an execution plan. The
[static-exposure addendum](../../designs/0016-static-exposure-addendum.md) is a
source-only delta audit, not a new history cutoff. The negative all-109 result is not by
itself evidence that another primitive is needed. No new primitive or gameplay
is the default follow-up.

## 2026-09-05 strategic review — advisory

The user-requested [Astra review](../../reviews/2026-09-05-astra-strategic-review.md)
supports retaining this plan's negative breadth result and unexecuted partition.
For a separately registered future scope it recommends complete supported/rejected
accounting, an explicit fairness objective, small evaluator counterexamples, and
a bounded development study. These are recommendations, not changes to this
plan's registered gates, completion status, or execution authorization. No new
selection, candidate access, transition, or outcome was performed in the review.
