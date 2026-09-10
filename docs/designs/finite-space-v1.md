> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Finite-space v1: minimum two-skeleton interface

2026-09-08, Plan0032 stage 0. New namespace; no change to historical DSL,
engine, policy, fixtures, prior proposals or results. Only `Player` and
`DefinitionError` may be imported from the old DSL. No external dependencies.

## Authoritative wire

Top-level exact keys:

```json
{
  "format": "parity-forge:finite-space:v1",
  "id": "example-name",
  "board": {"rows": 7, "cols": 7, "blocked": []},
  "first_player": "A",
  "terminal_rule": "NO_LEGAL_ACTION_LOSES",
  "roles": {
    "A": {"kind": "TILE", "shapes": [[[0, 0], [0, 1], [0, 2]]]},
    "B": {"kind": "TILE", "shapes": [[[0, 0], [0, 1], [1, 0]]]}
  }
}
```

This example is syntax, not a research candidate. Board coordinates are
zero-based `[row, col]`. Integers exclude bool. Dimensions are 1..32; this is
the first implementation's explicit resource guard, not a product-size goal.
Unknown keys, duplicate JSON keys when reading files, duplicate cells,
overlapping starting pieces, and out-of-board coordinates must fail closed.
`id` is a nonempty bounded identifier, not executable text.

A TILE role has exactly `kind` and `shapes`. Each shape is a nonempty, connected
orthogonal set of at most8 distinct integer cells with minimum row and column0.
At most16 distinct shapes per role. Cell/shape ordering is canonicalized;
duplicate equivalent translations are rejected. Rotations/reflections are
permitted only when explicitly listed. A TILE action places its shape on empty
cells anywhere; all placed cells belong to that role forever. There are no
anchors, connectivity-to-own-territory rules, captures or implicit transformations.

A TRAIL role has exactly:

```json
{"kind": "TRAIL", "vectors": [[-1, 0], [0, -1], [0, 1], [1, 0]],
 "max_distance": 6, "starts": [[1, 1], [5, 1]]}
```

Vectors are distinct nonzero unit-neighborhood integer vectors, each coordinate
in -1..1. `max_distance` is an integer1..32, and starts is a nonempty tuple of
distinct board coordinates (at most16 mobile pieces per role in this version).
Move one piece between1 and max_distance steps along one listed direction.
Every traversed cell including destination must be unoccupied and unclosed.
After moving, the origin becomes permanently closed. There is no jumping,
capture, pass, reopening or independent placement of the closed cell.

Mixed TILE/TRAIL definitions are supported by the same semantics, but neither
calibration nor discovery silently adds a mixed production candidate.

## Outcomes and all-legal proof

The exact meaning of `NO_LEGAL_ACTION_LOSES` is: if the player whose turn it is
has no legal action, that player loses and the other player is the sole winner.
This also defines an initially immobile state, although a discovery candidate
must have meaningful initial choices; initial-terminal fixtures are calibration
only. The engine checks terminality before any move and after switching turns.
It never manufactures a DRAW or ends a game because an external search stops.

Potential `E = rows*cols - closed_cells - occupied_cells` is a nonnegative
integer. TILE reduces E by its positive area; TRAIL reduces E by exactly1
(origin becomes closed, destination becomes occupied, piece count unchanged).
Therefore every legal play has at most its initial E actions. With no action,
the sole winner is defined above. Check strict potential decrease on transitions.
No `max_plies`, score comparison, arbitrary tiebreak or repetition rule exists.

## Core Python contract

Module `parity_forge.finite_space`. Immutable, hashable dataclasses:

- `Role(kind, shapes=(), vectors=(), max_distance=0, starts=())`; positions and
  shapes use tuples of coordinate pairs in this definition type.
- `Definition(id, rows, cols, blocked, first_player, roles)`; roles is ordered
  `(A_role, B_role)`; blocked uses coordinate pairs. A `role(player)` helper is
  permitted. Definition serialization includes format and terminal rule above.
- `State(closed, a, b, to_move, plies, winner=None)`; closed is a nonnegative
  bitmask and a/b are sorted tuples of row-major cell indices. TILE ownership
  and TRAIL piece positions use a/b. winner is `None` or `Player`, never a draw.
- `Action(kind, cells=(), source=-1, destination=-1)`; frozen/orderable. TILE
  has a sorted tuple of row-major cells; TRAIL has only source/destination.

Public functions:

```text
parse_definition(mapping) -> Definition
definition_to_dict(definition) -> dict
canonical_json(definition) -> str
definition_hash(definition) -> str
initial_state(definition) -> State
legal_actions(definition, state, player=None) -> tuple[Action, ...]
apply_action(definition, state, action) -> State
free_cells(definition, state) -> int
action_to_dict(definition, action) -> dict
action_from_dict(definition, mapping) -> Action
state_to_dict(definition, state) -> dict
replay(definition, iterable_of_action_dicts) -> State
termination_certificate(definition) -> dict
asymmetry_witness(definition) -> dict
describe_rules(definition) -> tuple[str, ...]
```

`legal_actions` defaults to the current actor; optional player calculates
that role's geometric actions on a nonterminal state for mobility diagnostics.
It returns empty on a terminal state. Canonical action order is stable, with
no duplicate TILE placements even if two orientations yield the same cells.
`apply_action` rejects an action outside the current actor's legal set, any
wrong-kind/forged action and any attempt to move after terminality. It does not
silently normalize invalid caller actions into legal ones.

`definition_hash` hashes canonical definition JSON excluding only `id`, with
UTF-8 domain separator `parity-forge:finite-space-definition:v1\n`. Thus renaming
a candidate creates no new semantic identity. The canonical JSON itself retains
the id. Coordinates, not bitmasks, are the public record representation.

Action wires are exactly `{"kind":"TILE","cells":[[r,c],...]}` or
`{"kind":"TRAIL","from":[r,c],"to":[r,c]}`. State wire keys are
`closed`, `A`, `B`, `to_move`, `plies`, `winner`, all positions coordinate lists.
`termination_certificate` reports proof type `STRICT_EMPTY_CAPACITY`, initial
capacity, maximum legal plies, terminal rule and the two fixed decrease laws.
It is a structural argument for this closed grammar, not a certificate for any
arbitrary rule system or for fun/strength/balance.

`asymmetry_witness` returns at least `mechanically_asymmetric: bool` and `reason`.
It compares role action capabilities, not sampled win rates. Different kinds,
TRAIL piece counts/ranges, inequivalent direction sets, or inequivalent TILE
shape sets can witness asymmetry. Check the eight square-grid isometries on
capabilities so horizontal-vs-vertical domino alone is not accepted as a new
asymmetric mechanism. A conservative false result is `NOT_ESTABLISHED`, not a
general theorem that arbitrary games are equivalent. Starting-position-only
differences do not qualify. Symmetric fixtures parse but fail this admission
diagnostic. `describe_rules` derives Japanese instructions from the definition.

TRAIL admission is deliberately conservative: equal piece counts plus either
abstract capability equivalence (range clipped to the common maximum board
dimension) or direction-specific effective-capability equivalence under D4
returns NOT_ESTABLISHED. Only differences surviving both checks are witnesses.
This avoids treating unused ranges/directions or rectangular orientation alone
as conclusive asymmetry. NOT_ESTABLISHED is incomplete admission evidence,
not an invalid-game or bad-game training label.

## Required calibration, separate from discovery

Use tiny synthetic fixtures, not any old candidate. Cover these10 propositions:

1. strict parse rejects malformed/bool/unknown/duplicate/out-of-board inputs;
2. ordering canonicalizes but id-only change cannot change semantic identity;
3. explicit TILE orientations generate exactly the hand-counted legal cells;
4. TRAIL rays stop at either owner's piece or a closed cell;
5. a TRAIL move permanently closes its source and cannot cycle back;
6. empty legal set yields the other sole winner, including initially;
7. TILE and TRAIL decrease E by the declared amount;
8. exhaustive tiny legal continuations terminate before E is exhausted;
9. serialized replay agrees with direct transitions and rejects illegal records;
10. renamed/rotated equal abilities do not become mechanical asymmetry.

Both successful valid cases and expected failures are required. Any exhaustive
calibration enumerator has a strict state cap and does not access production
definitions. These prove implementation properties, not human enjoyment.

## Minimal reusable next boundary

The core has no agent/model/network/filesystem side effects. A separate bounded
search module and a data-driven batch CLI may consume this interface under
Plan32's allowlist. Do not retrofit old agents or replay old evidence through
this engine. Keep elapsed/resource censoring outside all core game outcomes.

The batch CLI uses a canonical campaign root and exclusive episode1/2/3 claims;
claims survive failures. Its initial stage supports only up to4 TILE and4 TRAIL
definitions and8 games each, with provenance and source pins. Additional16-game
diagnostics are deferred, not automatically authorized by unused budget.
CPU checks occur inside search at successor boundaries, and the CLI worker
uses an OS CPU hard limit as a backstop. The in-process API used by synthetic
tests has only cooperative CPU checks plus deterministic node limits.

An optional terminal prototype consumes the same rule parser, engine and policy.
It accepts coordinates for either one human versus AI or two local human roles,
and prints the unverified status. It writes no human-evidence record and is not
automatically launched as a playtest. It is not the paused online Site.
