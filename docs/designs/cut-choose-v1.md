> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Cut-choose v1 — faithful fixed-role edge game and bounded proof

Plan0034, 2026-09-08. Independent stdlib-only Python3.9 namespace. No old source
imports/edits, executable definition callbacks, symmetry or graph reductions.

## Wire and core API

Exact JSON keys: format, id, vertices, edges, left, right, roles, terminal_rule.
`format` = `parity-forge:cut-choose:v1`; `roles` = `{"A":"CUTTER","B":"BUILDER"}`;
`terminal_rule` = `SECURED_CONNECTS_ELSE_POTENTIAL_DISCONNECTED`.
id is a nonempty short string (maximum80 characters). vertices is an integer
count2..32; vertices are0..vertices-1. edges is a nonempty even list of at most32
distinct undirected integer endpoint pairs. Canonicalize each edge u<v, then sort
all edges. left/right are nonempty disjoint sets of in-range vertex indices,
canonical sorted lists. Reject duplicate edges/vertices, loops, unknown keys,
bool-as-int, floats, wrong tags and extra role fields. Initially disconnected
graphs are allowed as terminal fixtures, never auto-qualified discovery games.

`Definition(id, vertices, edges, left, right)` is frozen; tuple fields are canonical.
`State(secured=0, removed=0, pending=())` is frozen. secured/removed are disjoint
nonnegative in-range bitmasks of equal cardinality. All other edges are unresolved.
pending is empty or an increasing2-tuple of unresolved edge indices. It is empty
at terminal states. No stored winner, free actor, pass or draw field.

Functions in parity_forge.cut_choose:

```text
parse_definition(mapping) -> Definition
definition_to_dict(definition) -> dict
definition_hash(definition) -> hex str
original_definition() -> Definition
initial_state(definition) -> State
validate_state(definition, state) -> None or ValueError
connected(definition, edge_mask) -> bool
terminal(definition, state) -> "A" | "B" | None
legal_actions(definition, state) -> tuple[tuple[int,...],...]
apply_action(definition, state, action:tuple[int,...]) -> State
replay(definition, actions) -> State
```

Hash canonical JSON without id, sorted keys/compact separators/UTF-8, prefixed
by `b"parity-forge:cut-choose-definition:v1\n"`. id changes no game semantics.
Original ID `bridge-cut-choose-4x4-v1`: row-major vertices4*r+c, 12 horizontal
and12 vertical neighboring edges, left[0,4,8,12], right[3,7,11,15]. Never remove
boundary vertical edges. Sorting edges fixes stable action indices.

With pending empty, A proposes any increasing pair(i,j) of unresolved edges;
with pending nonempty, B selects (i,) for one pending edge, secures it and removes
the other simultaneously. Clear pending. Proposal locks both choices and cannot
alter the masks. Actor is derived from pending; the tuple action length/type
enforces correct phase. Terminal states have no legal actions and reject moves.

Terminal B if secured edges connect some left vertex to some right vertex;
terminal A if all edges except removed fail to connect; otherwise None.
Test terminal at the initial state and after each complete choice. A pending
proposal on a terminal graph is invalid. No transition may continue after a win.
Every complete round removes2 unresolved edges; even initial count implies
finite unique winner within edges/2 rounds for every legal play.

## Solver and proof API

Functions in parity_forge.cut_choose_search:

```text
solve(definition, node_limit, transition_limit, proof_arc_limit=1000000,
      cpu_seconds=1800) -> dict
verify_proof(definition, proof, arc_limit=1000000, cpu_seconds=1800) -> dict
```

Search starts only at the empty round state, memoized by (secured,removed).
Children are complete pair+choice rounds; pending phase remains explicit in
the core and checker. No game-tree cache crosses definitions or invocations.
Budgets are strict nonbool nonnegative integers, CPU positive finite number.
Every uncached nonterminal round-state expansion costs1 node. Every generated
complete pair/choice child costs1 transition, checked before generating it.
Terminal states and exact memo hits cost0 expansions. Check CPU during recursion.
An exhausted budget returns UNKNOWN/winner null/proof null, never a fake leaf.

A round-state win proof for A contains one legal offer and BOTH choices, all
children A. A round-state win proof for B covers EVERY legal offer with ONE
chosen edge per offer, all children B. Pair and choice order are lexicographic;
depth-first solve stops when these exact obligations are met. A budget abort
may conservatively discard partial conclusions; no extra solve/restart is implied.

Result exact keys: status (COMPLETE|UNKNOWN), winner (A|B|null), reason,
nodes, transitions, proof_arcs, proof. COMPLETE means proof produced AND verified.
reason is PROVED or NODE_LIMIT/TRANSITION_LIMIT/PROOF_ARC_LIMIT/CPU_LIMIT.
The runner may additionally return RESULT_BYTE_LIMIT if serialization exceeds
the registered bound, or CPU_LIMIT during verification/serialization. It clears
winner/proof and preserves observed counters; it does not overwrite a saved result.
Diagnostics do not imply a human-readiness or fairness/depth flag.

Proof JSON exact keys: format (`parity-forge:cut-choose-proof:v1`),
definition_hash, root ("0:0"), winner, nodes. nodes maps canonical decimal
`secured:removed` to {winner, replies}. replies is a list of exact
{offer:[i,j], keep:i, child:"secured:removed"} objects. Terminal nodes have
replies[]. A nonterminal node has2 replies for one offer with the two distinct
keeps. B has one reply per legal offer. All child winners equal the proof winner.
Serialize only reachable proof closure; reject orphans, malformed keys, booleans,
missing/duplicate/wrong replies, graph mismatch, false leaves and illegal children.

Independent checker must not call solve, trust its cache, or trust claimed
terminal winners/child transitions. Reconstruct legal core states/terminal/actions
and independently flood-fill adjacency for terminality. Enforce finite arcs before
processing and exact root/all-node reachability. Return {status:PASS,nodes,arcs,winner}
or raise ValueError; malformed/oversized proofs cannot become accepted wins.
Require len(nodes)<=arc_limit+1 before iteration as well as the arc bound.
BudgetExceeded (a ValueError subclass carrying reason) distinguishes a check's
CPU/proof-work limit from a malformed certificate. All CPU deadlines are checked
during recursion, proof extraction and checking, and runner serialization; the
registered1,800 CPU seconds covers the whole diagnostic, not just search.
External forced kill/interruption is failure/incomplete, never a fabricated result.
Proof-arc budget bounds retained search evidence and checker work. Charge before
retaining each reply in temporary DFS frames or completed cache records; release
discarded temporary replies, never cached records. `proof_arcs` reports the peak
retained count, including solved branches not ultimately in the root closure.

## Runner, tests and acceptance

cut_choose_batch provides one command:
`python3 -m parity_forge.cut_choose_batch --manifest PATH --output ROOT`.
The manifest schema and exact-source pins are fixed by the main agent before
candidate execution. Reject duplicate keys, missing/unknown fields, pin drift,
overlarge files and existing run claims. No repeated original query in tests.
Use exclusive creation for claim, registration, result and failure. Save UTC,
Python/host, git provenance, actual counters, source manifest and result hash.
Never hide an exception by deleting a claim or automatically rerunning.

Four nonterminal solver calibration graphs: chain[(0,1),(1,2)] A; direct+padding[(0,1),(2,3)] B;
diamond[(0,1),(0,2),(1,3),(2,3)] A; direct4[(0,1),(0,2),(1,2),(2,3)] B.
Left/right for first are[0]/[2]; second/fourth[0]/[1]; diamond[0]/[3].
Use these same wires across solver tests; don't add research candidates from fixtures.
Malformed representation and initial-disconnection checks are separate rule-fault
fixtures, not additional nonterminal solving/research supply.
All core/solver/certificate tampering tests are synthetic. Original inspection
tests only initial graph/action count and no solver or played original prefixes.
Before code completion run the mandatory full suite with actual exit evidence.
