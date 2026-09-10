> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Connection v1 — registered implementation contract

Plan40 registration: `experiments/proposals/plan0040-connection-baseline-v0.json`.
This document specifies implementation; no source exists yet. Product rules are
the registration's two connection definitions and mechanics, derived from the
selected Plan39 sketch. Its only condition change is initial A/B turn.

## Core: src/parity_forge/connection.py

Use immutable Definition, State and Action dataclasses; existing dsl.Player may
be imported unchanged. No modification or dependency on old terminal semantics.
Definition contains id, size, first_player, bridge_credits_A, conversion_credits_B.
Parser requires exact keys, RHOMBUS_HEX_CELLS and OPPOSITE_EDGE_CONNECTION;
integer parameters reject bool. Size2..19 and credits0..9 support technical fixtures;
only the two registered size9/A3/B2 empty-board definitions enter this experiment.
An accepted small technical fixture is not an admitted discovery candidate.

State fields: a/b integer bitmasks, bridge_left/conversion_left, to_move, plies,
winner. Cell index is row*size+col; neighbors are exactly the six registered deltas
in bounds. State wire a/b are sorted coordinate arrays, not unsafe JSON/JavaScript
large numeric bitmasks. Other wire fields use integers and player strings/null.
State checks include bounds/disjointness, credit bounds, turn count, occupancy,
and connectivity. For tA/tB turns from first_player and plies, usedA=initialA-leftA,
usedB=initialB-leftB: |a|=tA+usedA-usedB, |b|=tB+usedB; usedA<=tA, usedB<=tB.
These necessary invariants are not a claim of complete reachability checking.

Action(kind,cells) uses a tuple of cell indices: PLACE_ONE one; BRIDGE_PAIR two
canonical sorted neighboring empties; PLACE_AND_CONVERT ordered(place,convert).
Wire is {kind,cells:[[r,c],...]}; conversion order has meaning and is not sorted.
All three action kinds are atomic, no intermediate-win checkpoint. Apply only
the active role's legal action, debit its credit when used, then check connection.
Winner retains mover in to_move; otherwise switch. Applying to terminal state,
noncanonical/duplicate pair, wrong credit/role/ownership or illegal neighbor raises.

Expose parse_definition, definition_hash, initial_state, legal_actions,
apply_action, winner_from_board, action_to_dict/from_dict, state_to_dict/from_dict,
describe_rules and termination_certificate. All functions are deterministic.
Canonical definition hash removes id only, then SHA256 of ensure_ascii=True,
sort_keys=True, separators=(',',':'), allow_nan=False JSON with no newline.
Recompute connectivity after conversion; incremental union-find without deletions
is not sound for A's removed connection. No-legal-action never awards a winner.
Both winners/full board with no winner is a technical error, not DRAW or tiebreak.

## Search: src/parity_forge/connection_search.py

Expose connection_distance, evaluate_state and select_action(definition,state,
policy,rng,max_transitions,max_depth,cpu_expired). select_action returns action
plus actual transition/depth/fallback/budget/CPU metadata. No policy calls models.
Use registered 0/1 shortest vertex-path distance, including start cell cost,
opponent cells impassable and no-path=size*size+1. Score=dB-dA for A; terminal
scores+/-1000. No credit, mobility, length, centrality or other bonus.
This intentionally simple baseline does not infer convertibility from distance;
only explicit search models conversions. No new agent tuning during the cohort.

Random selects uniformly from canonical legal actions without successor search.
Greedy completes one-ply minimax. Search uses iterative-deepening alpha-beta,
canonical traversal, no beam, transposition table or uncharged tactical presearch.
A maximizes/B minimizes. Keep all equal best root actions at the last completely
finished depth; choose once using that role's RNG after search ends. Internal
ties retain canonical order. Each root child starts a full(-infinity,+infinity)
window so a cut-off bound cannot be mistaken for an equal-valued root action.
Aborted partial root results must not overwrite a
completed iteration. If none completed, explicitly tagged canonical fallback.
CPU expiry yields UNKNOWN/interruption, never an applied fallback or game loss.
Charge every speculative apply, including repeated iterations and greedy work.
Record actual accepted moves and reference replay separately; CPU covers all work.

## Runner/reference: src/parity_forge/connection_batch.py

Validate prospective registration, exact schedule/definitions/limits, sealed
registration-byte hash and six source hashes. Preserve old206 pins. The sealed
manifest is a separate artifact created only after source freeze/full regression
acceptance; source-unavailable registration is never executable. Run id, output
and exclusive batch-1 claim are fixed in the registration. An existing/failed
claim or output blocks any retry or differently named replacement in this cohort.

Schedule profiles in registered list order, each seed in listed order, and each
definition A-first then B-first for that seed. Each role's Random gets2*seed or
2*seed+1. Exactly8 games/definition,16 total; no extra calibration tournaments.
Cooperative total CPU checks and OS hard backstop enforce14,400seconds including
generation/evaluation/serialization/reference replay. Per-decision/game caps are
as registered; unknown/not-started entries stay explicit and are never losses.

Save registration, trace-rich results, runtime or technical failure using exclusive
writes and a cumulative16MiB raw-output ceiling, including the claim. Save actual
process exit externally; runtimeCOMPLETED alone is not an observed process exit.
Game records retain definition hash, first role, policies, seed, actions, decisions,
final state, plies, credit consumption, winner/status/reason and cost counters.
All fairness/depth/fun/human flags remain false, including balanced score samples.

For each complete trace, perform one independent reference replay in this module,
using coordinate sets, direct neighbor predicates and independently coded flood
fill/transition checks, not core apply_action/winner_from_board. Compare every
action/state/credit/turn/winner and reject mismatch. This is technical validation,
not another game or independent quality sample. No replay/proof loop after the run.

## Tests and sequencing

Only three new test files, matching these modules. Test syntax/invariants,
asymmetric action access/credits, all adjacency directions, atomic conversion
destroying A links/creating B links, real connection endings, no draw/default-loss,
independent replay tamper detection, seed determinism, both perspective signs,
partial-depth accounting, forced budget/CPU interruptions, pins, claim exclusivity,
and output limits. Use small synthetic fixtures and injected/mocked runner tests;
never call the production cohort or its real output root from the test suite.
Synthetic traces/partial-board tests are not new discovery games or exact solving.

Integrate within3 focused suite invocations; independently review frozen source,
verify all206 old pins, then run the mandatory full regression once and capture
actual exit. No source changes or new policy parameters after freeze/registration
without an explicit corrective decision. Only then seal and launch the one cohort.
No engine/search/test code, actual games or exact query is authorized in the
registration-only activation itself. The next active Plan40 unit owns implementation.
