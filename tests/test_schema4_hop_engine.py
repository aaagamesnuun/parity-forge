import copy
import unittest
from itertools import product

from parity_forge.dsl import ActionKind, InitialPiece, Player, parse_definition
from parity_forge.engine import (
    Action,
    GameState,
    IllegalAction,
    action_from_dict,
    apply_action,
    initial_state,
    legal_actions,
    replay,
    replay_dicts,
)


def hop_definition():
    return {
        "schema_version": 4,
        "name": "Hop engine probe",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 20,
        "roles": {
            "A": {
                "action": {
                    "kind": "HOP",
                    "piece": "hopper",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "hopper",
                    "edges": ["TOP", "BOTTOM"],
                },
            },
            "B": {
                "action": {
                    "kind": "MOVE",
                    "piece": "runner",
                    "vectors": [[-1, 0]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "RIGHT",
                },
            },
        },
        "initial_pieces": [
            {"owner": "A", "piece": "hopper", "position": [0, 0]},
            {"owner": "A", "piece": "hopper", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [1, 1]},
        ],
    }


def canonical_pieces(*pieces):
    return tuple(
        sorted(
            pieces,
            key=lambda piece: (
                piece.position,
                piece.owner.value,
                piece.piece,
            ),
        )
    )


def piece_snapshot(state):
    return tuple(
        (piece.owner, piece.piece, piece.position) for piece in state.pieces
    )


class SchemaV4HopEngineTests(unittest.TestCase):
    def test_hop_action_uses_shared_exact_value_boundaries(self) -> None:
        invalid_actions = (
            lambda: Action(  # type: ignore[arg-type]
                kind="HOP",
                from_position=(1, 0),
                to_position=(1, 2),
            ),
            lambda: Action.hop((True, 0), (1, 2)),
            lambda: Action(
                kind=ActionKind.HOP,
                from_position=None,
                to_position=(1, 2),
            ),
        )
        for make_action in invalid_actions:
            with self.subTest(make_action=make_action):
                with self.assertRaises(IllegalAction):
                    make_action()

        definition = parse_definition(hop_definition())
        state = initial_state(definition)
        forged_kind = Action.hop((1, 0), (1, 2))
        object.__setattr__(forged_kind, "kind", "HOP")
        forged_position = Action.hop((1, 0), (1, 2))
        object.__setattr__(forged_position, "to_position", (1, True))
        hidden = Action.hop((1, 0), (1, 2))
        object.__setattr__(hidden, "over", (1, 1))
        missing = Action.hop((1, 0), (1, 2))
        object.__delattr__(missing, "from_position")

        for label, action in (
            ("kind", forged_kind),
            ("position", forged_position),
            ("hidden", hidden),
            ("missing", missing),
        ):
            with self.subTest(label=label, boundary="serialize"):
                with self.assertRaises(IllegalAction):
                    action.to_dict()
            with self.subTest(label=label, boundary="sort"):
                with self.assertRaises(IllegalAction):
                    action.sort_key()
            with self.subTest(label=label, boundary="transition"):
                with self.assertRaises(IllegalAction):
                    apply_action(definition, state, action)

    def test_hop_legality_matches_local_reference_for_all_3x3_occupancies(
        self,
    ) -> None:
        raw = hop_definition()
        raw["initial_pieces"] = []
        raw["roles"]["A"]["action"]["vectors"] = [
            [row_delta, column_delta]
            for row_delta in (-1, 0, 1)
            for column_delta in (-1, 0, 1)
            if (row_delta, column_delta) != (0, 0)
        ]
        definition = parse_definition(raw)
        cells = tuple((row, column) for row in range(3) for column in range(3))
        checked = 0
        ordinary_count = 0
        friendly_special_count = 0
        opponent_special_count = 0

        for origin in cells:
            other_cells = tuple(cell for cell in cells if cell != origin)
            for labels in product(range(3), repeat=len(other_cells)):
                pieces = [InitialPiece(Player.A, "hopper", origin)]
                occupied = {origin: Player.A}
                for position, label in zip(other_cells, labels):
                    if label == 1:
                        pieces.append(InitialPiece(Player.A, "friendly", position))
                        occupied[position] = Player.A
                    elif label == 2:
                        pieces.append(InitialPiece(Player.B, "opponent", position))
                        occupied[position] = Player.B
                state = GameState(
                    ply=0,
                    to_move=Player.A,
                    pieces=canonical_pieces(*pieces),
                )

                expected = []
                for row_delta, column_delta in definition.role(
                    Player.A
                ).action.vectors:
                    adjacent = (
                        origin[0] + row_delta,
                        origin[1] + column_delta,
                    )
                    if not all(0 <= coordinate < 3 for coordinate in adjacent):
                        continue
                    adjacent_owner = occupied.get(adjacent)
                    if adjacent_owner is None:
                        expected.append(Action.hop(origin, adjacent))
                        ordinary_count += 1
                        continue
                    landing = (
                        adjacent[0] + row_delta,
                        adjacent[1] + column_delta,
                    )
                    if (
                        all(0 <= coordinate < 3 for coordinate in landing)
                        and landing not in occupied
                    ):
                        expected.append(Action.hop(origin, landing))
                        if adjacent_owner is Player.A:
                            friendly_special_count += 1
                        else:
                            opponent_special_count += 1

                self.assertEqual(
                    legal_actions(definition, state),
                    tuple(sorted(expected, key=Action.sort_key)),
                )
                checked += 1

        self.assertEqual(checked, 59049)
        self.assertEqual(ordinary_count, 87480)
        self.assertEqual(friendly_special_count, 11664)
        self.assertEqual(opponent_special_count, 11664)
        self.assertEqual(
            ordinary_count + friendly_special_count + opponent_special_count,
            110808,
        )

    def test_hop_has_ordinary_and_opponent_special_transitions(self) -> None:
        definition = parse_definition(hop_definition())
        state = initial_state(definition)
        ordinary = Action.hop((0, 0), (0, 1))
        special = Action.hop((1, 0), (1, 2))

        self.assertEqual(legal_actions(definition, state), (ordinary, special))
        self.assertTrue(
            all(
                action.kind is ActionKind.HOP
                for action in legal_actions(definition, state)
            )
        )
        with self.assertRaisesRegex(IllegalAction, "not legal"):
            apply_action(
                definition,
                state,
                Action.move((0, 0), (0, 1)),
            )

        ordinary_state = apply_action(definition, state, ordinary)
        self.assertEqual(
            piece_snapshot(ordinary_state),
            (
                (Player.A, "hopper", (0, 1)),
                (Player.A, "hopper", (1, 0)),
                (Player.B, "runner", (1, 1)),
            ),
        )

        special_state = apply_action(definition, state, special)
        self.assertEqual(
            piece_snapshot(special_state),
            (
                (Player.A, "hopper", (0, 0)),
                (Player.B, "runner", (1, 1)),
                (Player.A, "hopper", (1, 2)),
            ),
        )

    def test_hop_jumps_over_friendly_and_opponent_without_changing_them(
        self,
    ) -> None:
        raw = hop_definition()
        raw["initial_pieces"] = []
        raw["roles"]["A"]["action"]["vectors"] = [[0, 1], [1, 1]]
        definition = parse_definition(raw)

        friendly_state = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(
                InitialPiece(Player.A, "hopper", (1, 0)),
                InitialPiece(Player.A, "friendly_kind", (1, 1)),
            ),
        )
        after_friendly = apply_action(
            definition,
            friendly_state,
            Action.hop((1, 0), (1, 2)),
        )
        self.assertEqual(
            piece_snapshot(after_friendly),
            (
                (Player.A, "friendly_kind", (1, 1)),
                (Player.A, "hopper", (1, 2)),
            ),
        )

        opponent_state = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(
                InitialPiece(Player.A, "hopper", (0, 0)),
                InitialPiece(Player.B, "unrelated_kind", (1, 1)),
            ),
        )
        after_opponent = apply_action(
            definition,
            opponent_state,
            Action.hop((0, 0), (2, 2)),
        )
        self.assertEqual(
            piece_snapshot(after_opponent),
            (
                (Player.B, "unrelated_kind", (1, 1)),
                (Player.A, "hopper", (2, 2)),
            ),
        )

    def test_hop_rejects_stops_leaps_landings_boundaries_and_wrong_vectors(
        self,
    ) -> None:
        raw = hop_definition()
        raw["board_size"] = 5
        raw["initial_pieces"] = []
        raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_a",
            "edge": "TOP",
        }
        raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_b",
            "edge": "TOP",
        }
        definition = parse_definition(raw)

        cases = (
            (
                "occupied adjacent cannot be the destination",
                canonical_pieces(
                    InitialPiece(Player.A, "hopper", (2, 0)),
                    InitialPiece(Player.B, "block", (2, 1)),
                ),
                Action.hop((2, 0), (2, 1)),
            ),
            (
                "empty adjacent cannot be crossed",
                canonical_pieces(InitialPiece(Player.A, "hopper", (2, 0))),
                Action.hop((2, 0), (2, 2)),
            ),
            (
                "occupied landing",
                canonical_pieces(
                    InitialPiece(Player.A, "hopper", (2, 0)),
                    InitialPiece(Player.A, "block", (2, 1)),
                    InitialPiece(Player.B, "block", (2, 2)),
                ),
                Action.hop((2, 0), (2, 2)),
            ),
            (
                "off-board landing",
                canonical_pieces(
                    InitialPiece(Player.A, "hopper", (2, 3)),
                    InitialPiece(Player.B, "block", (2, 4)),
                ),
                Action.hop((2, 3), (2, 5)),
            ),
            (
                "chain or three-cell hop",
                canonical_pieces(
                    InitialPiece(Player.A, "hopper", (2, 0)),
                    InitialPiece(Player.B, "block", (2, 1)),
                ),
                Action.hop((2, 0), (2, 3)),
            ),
            (
                "undeclared vector",
                canonical_pieces(InitialPiece(Player.A, "hopper", (2, 0))),
                Action.hop((2, 0), (3, 0)),
            ),
        )

        for label, pieces, action in cases:
            state = GameState(ply=0, to_move=Player.A, pieces=pieces)
            with self.subTest(label=label):
                self.assertNotIn(action, legal_actions(definition, state))
                with self.assertRaisesRegex(IllegalAction, "not legal"):
                    apply_action(definition, state, action)

    def test_hop_action_serialization_and_replay_preserve_only_kind_from_to(
        self,
    ) -> None:
        definition = parse_definition(hop_definition())
        action = Action.hop((1, 0), (1, 2))
        recorded = {"kind": "HOP", "from": [1, 0], "to": [1, 2]}

        self.assertEqual(action.to_dict(), recorded)
        self.assertEqual(action_from_dict(recorded), action)
        self.assertEqual(
            replay_dicts(definition, [recorded]),
            replay(definition, [action]),
        )
        for extra in ("over", "landing"):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(IllegalAction, "fields do not match"):
                    action_from_dict({**recorded, extra: [1, 1]})

    def test_hop_keeps_schema_v4_terminal_priorities(self) -> None:
        simultaneous_raw = hop_definition()
        simultaneous_raw["max_plies"] = 1
        simultaneous_raw["initial_pieces"] = []
        simultaneous_raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "hopper",
            "edge": "RIGHT",
        }
        simultaneous_raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "runner",
            "edge": "TOP",
        }
        simultaneous_definition = parse_definition(simultaneous_raw)
        simultaneous_state = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(
                InitialPiece(Player.A, "hopper", (0, 0)),
                InitialPiece(Player.B, "runner", (0, 1)),
            ),
        )
        after_simultaneous = apply_action(
            simultaneous_definition,
            simultaneous_state,
            Action.hop((0, 0), (0, 2)),
        )
        self.assertEqual(after_simultaneous.outcome.winner, Player.A)
        self.assertEqual(after_simultaneous.outcome.reason, "GOAL")

        opponent_raw = copy.deepcopy(simultaneous_raw)
        opponent_raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_a",
            "edge": "BOTTOM",
        }
        opponent_definition = parse_definition(opponent_raw)
        after_opponent = apply_action(
            opponent_definition,
            simultaneous_state,
            Action.hop((0, 0), (0, 2)),
        )
        self.assertEqual(after_opponent.outcome.winner, Player.B)
        self.assertEqual(after_opponent.outcome.reason, "GOAL")

        immobility_raw = copy.deepcopy(opponent_raw)
        immobility_raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_b",
            "edge": "TOP",
        }
        immobility_definition = parse_definition(immobility_raw)
        immobility_state = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(InitialPiece(Player.A, "hopper", (1, 0))),
        )
        after_limit = apply_action(
            immobility_definition,
            immobility_state,
            Action.hop((1, 0), (1, 1)),
        )
        self.assertIsNone(after_limit.outcome.winner)
        self.assertEqual(after_limit.outcome.reason, "PLY_LIMIT")

        immobility_raw["max_plies"] = 2
        stuck_definition = parse_definition(immobility_raw)
        after_stuck = apply_action(
            stuck_definition,
            immobility_state,
            Action.hop((1, 0), (1, 1)),
        )
        self.assertEqual(after_stuck.outcome.winner, Player.A)
        self.assertEqual(after_stuck.outcome.reason, "NO_LEGAL_ACTION")


if __name__ == "__main__":
    unittest.main()
