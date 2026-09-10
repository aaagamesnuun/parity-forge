> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Game DSL schemas v1–v4

JSON is the interchange format; immutable typed objects are the in-process form.
Unknown fields are rejected. Natural-language rules are derived and non-authoritative.

## Schema-v1 definition

```json
{
  "schema_version": 1,
  "name": "Crossing Seeds",
  "board_size": 3,
  "first_player": "A",
  "max_plies": 20,
  "roles": {
    "A": {
      "action": {"kind": "PLACE", "piece": "seed"},
      "goal": {"kind": "CONNECT_EDGES", "piece": "seed", "edges": ["TOP", "BOTTOM"]}
    },
    "B": {
      "action": {"kind": "MOVE", "piece": "runner", "vectors": [[-1, 0], [0, -1], [0, 1], [1, 0]]},
      "goal": {"kind": "REACH_EDGE", "piece": "runner", "edge": "TOP"}
    }
  },
  "initial_pieces": [{"owner": "B", "piece": "runner", "position": [2, 1]}]
}
```

Coordinates are `[row, column]`, zero-based from the top-left. Arrays used as
sets are canonicalized into deterministic order.

## Shared primitive semantics

- `PLACE`: place the role's named piece in any empty cell.
- `MOVE`: move one matching owned piece by one listed vector to an in-bounds empty
  cell. Jumping, capture, and wrapping are never implied by `MOVE`; schemas v1 and
  v2 accept only `PLACE` and `MOVE` actions.
- `MOVE_CAPTURE` (introduced in schema v3 and also accepted by v4): use the same
  from/to action and listed one-step
  vectors as `MOVE`. An empty destination is an ordinary move. An opponent-occupied
  destination removes exactly that piece and the moving piece occupies the cell;
  an own-piece destination remains blocked. It adds no jump, push, ranged or
  multi-capture, capture obligation, reserve, score, or goal.
- `PUSH` (schema v4): use the same from/to action and listed one-step vectors as
  `MOVE`. An empty destination is an ordinary move. If the adjacent destination
  contains one opponent piece, the actor enters that cell and displaces the
  target one further cell along the same vector. That landing cell must be in
  bounds and empty. A friendly destination, occupied landing, off-board landing,
  or chain push is illegal. The pushed piece retains its owner and piece kind.
- `SWAP` (schema v4): use the same from/to action and listed one-step vectors as
  `MOVE`. An empty destination is an ordinary move. If the adjacent destination
  contains one opponent piece, the actor and target exchange positions while both
  retain their owner and piece kind. A friendly destination, ranged exchange, or
  multi-piece exchange is illegal.
- `HOP` (schema v4): an empty cell one declared vector from the actor is an
  ordinary move. If that adjacent cell is occupied by any friendly or opposing
  piece, the actor may instead land in the empty in-bounds cell one more step
  along the same vector. The jumped piece retains its owner, kind, and position.
  Jumping over an empty cell, landing on an occupied or off-board cell, changing
  direction, moving three or more cells, and chaining hops are illegal.
- `CONVERT` (schema v4): one matching owned actor remains in its cell and uses
  one declared vector to target an adjacent opponent piece of any kind. The
  target remains in its cell but changes to the actor's owner and the action's
  declared piece kind. A target already of that kind is still legal because its
  owner changes. An empty or friendly target, an undeclared or ranged target,
  actor movement, and multi-target conversion are illegal.
- `CONNECT_EDGES`: an orthogonally connected group of the role's named pieces
  touches both specified opposite edges.
- `REACH_EDGE`: any matching owned piece occupies the specified edge.

Actions, goals, board setup, move order, and the ply limit have identical meaning
in schemas v1 and v2. After an action, only the acting role's goal is checked. A
goal has first terminal precedence and the existing ply cap has second precedence.
The no-legal-action rule is checked only after those two conditions.

### Schema-v1 terminal semantics

If neither the acting role's goal nor the ply cap terminates an action, the turn
changes. If the next role has no legal action, the acting role wins. The initial
state has no winner even if a goal is already satisfied; static analysis rejects
such trivial definitions. A first player with no legal action is also diagnosed
statically and is terminal with the other role winning.

### Schema-v2 stalemate-draw treatment

Schema v2 is a strict, single-treatment extension of schema v1. It requires exactly
one additional top-level object:

```json
"terminal_policy": {"no_legal_action": "DRAW"}
```

No other terminal-policy key or value is accepted, and there is no implicit
default. Schema-v1 definitions reject `terminal_policy`; schema-v2 definitions
reject its omission. Every other field has the same validation and semantics as
schema v1.

Under schema v2, initial immobility and post-action next-player immobility both end
in a draw with terminal reason `NO_LEGAL_ACTION`. Static analysis still emits
`NO_LEGAL_MOVE_AT_START` for an immobile first player. After an action, terminal
precedence is therefore:

1. acting player's goal: that player wins with `GOAL`;
2. reached `max_plies`: draw with `PLY_LIMIT`;
3. next player has no legal action: draw with `NO_LEGAL_ACTION`.

The schema-v2 display name is unchanged when a v1 definition is paired with this
treatment. Its schema version and terminal-policy object nevertheless produce a
distinct canonical DSL hash and a distinct mechanical D4 identity.

### Schema-v3 capture-on-entry treatment

Schema v3 is a strict, single-interaction extension of schema v1. It accepts
`PLACE`, `MOVE`, and `MOVE_CAPTURE`, but every schema-v3 definition must contain at
least one role whose action is `MOVE_CAPTURE`; a v3 definition containing only the
older action kinds is rejected. Schemas v1 and v2 reject `MOVE_CAPTURE`.

Schema v3 forbids `terminal_policy` rather than supplying a default. Its terminal
precedence is exactly schema v1's: the acting role's goal first, the ply cap second,
and then next-player immobility awards the acting role a `NO_LEGAL_ACTION` win.
The capture treatment changes a paired source only from `schema_version: 1` to `3`
and from B's `MOVE` action to `MOVE_CAPTURE`; board, setup, goals, vectors, move
order, maximum plies, and display name remain unchanged.

Derived prose describes capture in a separate statement. The action kind and
schema version remain semantic fields, so the paired schema-v3 definition has its
own canonical DSL hash and mechanical D4 identity even when no played move captures.

### Schema-v4 state goals and PUSH/SWAP/HOP/CONVERT checkpoints

Schema v4 changes terminal interpretation because displacement and later v4
actions can satisfy either role's state predicate. At the initial state, terminal
precedence is:

1. first player's goal: the first player wins with `GOAL`;
2. second player's goal: the second player wins with `GOAL`;
3. first player has no legal action: the second player wins with
   `NO_LEGAL_ACTION`.

After every legal action, precedence is:

1. acting player's goal: the actor wins with `GOAL`;
2. opposing player's goal: the opponent wins with `GOAL`;
3. reached `max_plies`: draw with `PLY_LIMIT`;
4. next player has no legal action: the actor wins with `NO_LEGAL_ACTION`.

If both goals hold initially, the first player wins. If both hold after one
action, the actor wins. Goal checks therefore precede both the horizon and
mobility checks, while the horizon precedes post-action immobility. Schema v4
forbids `terminal_policy`; schemas v1–v3 retain their older terminal semantics.

Schema v4 accepts `PLACE`, `MOVE`, `MOVE_CAPTURE`, `PUSH`, `SWAP`, `HOP`, and
`CONVERT`. It requires at least one role to use `PUSH`, `SWAP`, `HOP`, or
`CONVERT`, or at least one role to use an `ELIMINATE` goal. This prevents an old
definition with only old actions and old goals from acquiring new terminal
semantics by changing only its version number.

An ELIMINATE goal has exactly `kind` and `piece`, for example
`{"kind":"ELIMINATE","piece":"runner"}`. Its piece names the opponent target
kind, not an owned goal actor. The goal is true exactly when no opponent-owned
piece of that kind remains; owned same-kind pieces and opponent pieces of other
kinds do not matter. It has no edge, counter, target owner, or history field.
Zero matching opponent pieces in the initial position therefore satisfy the
goal intentionally, under the same schema-v4 first-player priority above.
Outcome-free feasibility must exclude such trivial starts rather than changing
the goal predicate. Schemas v1–v3 reject ELIMINATE.

`PUSH`, `SWAP`, `HOP`, and `CONVERT` action objects each have exactly `kind`,
`piece`, and `vectors`. Vectors are a non-empty duplicate-free collection of
nonzero one-step integer offsets and are canonically sorted. Recorded engine
actions have exactly `kind`, `from`, and `to`; no hidden intermediate, target
kind, landing, chain, or effect callback is stored. A special HOP records its
final two-cell landing as `to`; CONVERT records the unchanged actor cell as
`from` and the rewritten target cell as `to`. Replay derives displacement,
exchange, the jumped cell, or conversion from the authoritative definition and
state.

Plan 0012 does not add the provisional name `CAPTURE_STEP` to the DSL. Its draft
contract—an ordinary declared one-step move to empty or entry into one adjacent
opponent cell with that target removed—is exactly `MOVE_CAPTURE`. Schema v4
already accepts that action with its existing `kind/from/to` record. Reusing it
prevents identical mechanics from receiving different definition and D4
identities. A genuinely different rule such as mandatory capture would require a
separate future decision and semantics; it is not implied here.

Schema-v4 typed definitions must already be parser-normalized even when directly
constructed in process: role and setup containers are immutable canonical tuples,
roles are uniquely ordered A then B, enum and integer fields use exact types, and
all nested action, goal, and piece values are revalidated. Canonical JSON, hashes,
and derived prose repeat this exact-type parser validation so forged or mutated
objects cannot acquire an authoritative identity.

## Version discipline

DSL semantics are immutable within a schema version. New primitives or changed
semantics require a new version or an explicitly compatible extension plus tests.
Canonical SHA-256 identity excludes formatting but includes all semantic fields.
Schema-v1, schema-v2, and schema-v3 canonical JSON, hashes, derived prose, legal
actions, transitions, and terminal behavior remain frozen: adding schema v4
neither reinterprets nor reserializes an older definition, and schema v2 never
adds its policy field to a schema-v1 serialization.

Spatial D4 canonicalization is a separate research identity for square-board
sampling. It rotates or reflects coordinates, goal edges, initial pieces, and all
declared spatial vectors, including the non-moving `CONVERT`, while preserving
roles, first player, ply limit, terminal policy, and every non-spatial field. Its
versioned hash ignores only the display `name`. It never replaces the
authoritative DSL hash: stored
definitions retain their exact canonical DSL identity, while the D4 hash records
membership in a mechanical symmetry orbit.
