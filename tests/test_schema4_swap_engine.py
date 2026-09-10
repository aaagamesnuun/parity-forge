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


def swap_definition():
    return {
        "schema_version": 4,
        "name": "Swap engine probe",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 20,
        "roles": {
            "A": {
                "action": {
                    "kind": "SWAP",
                    "piece": "swapper",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "swapper",
                    "edges": ["TOP", "BOTTOM"],
                },
            },
            "B": {
                "action": {
                    "kind": "MOVE",
                    "piece": "runner",
                    "vectors": [[1, 0]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "RIGHT",
                },
            },
        },
        "initial_pieces": [
            {"owner": "A", "piece": "swapper", "position": [0, 0]},
            {"owner": "A", "piece": "swapper", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [1, 1]},
        ],
    }


class SchemaV4SwapEngineTests(unittest.TestCase):
    def test_swap_action_uses_shared_exact_value_boundaries(self) -> None:
        with self.assertRaises(IllegalAction):
            Action(  # type: ignore[arg-type]
                kind="SWAP",
                from_position=(1, 0),
                to_position=(1, 1),
            )
        with self.assertRaises(IllegalAction):
            Action.swap((True, 0), (1, 1))

        definition = parse_definition(swap_definition())
        state = initial_state(definition)
        forged_kind = Action.swap((1, 0), (1, 1))
        object.__setattr__(forged_kind, "kind", "SWAP")
        hidden = Action.swap((1, 0), (1, 1))
        object.__setattr__(hidden, "target", (1, 1))

        for label, action in (("kind", forged_kind), ("hidden", hidden)):
            with self.subTest(label=label, boundary="serialize"):
                with self.assertRaises(IllegalAction):
                    action.to_dict()
            with self.subTest(label=label, boundary="sort"):
                with self.assertRaises(IllegalAction):
                    action.sort_key()
            with self.subTest(label=label, boundary="transition"):
                with self.assertRaises(IllegalAction):
                    apply_action(definition, state, action)

    def test_swap_legality_matches_local_reference_for_all_3x3_occupancies(
        self,
    ) -> None:
        raw = swap_definition()
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

        for origin in cells:
            other_cells = tuple(cell for cell in cells if cell != origin)
            for labels in product(range(3), repeat=len(other_cells)):
                pieces = [InitialPiece(Player.A, "swapper", origin)]
                occupied = {origin: Player.A}
                for position, label in zip(other_cells, labels):
                    if label == 1:
                        pieces.append(InitialPiece(Player.A, "block", position))
                        occupied[position] = Player.A
                    elif label == 2:
                        pieces.append(InitialPiece(Player.B, "target", position))
                        occupied[position] = Player.B
                state = GameState(
                    ply=0,
                    to_move=Player.A,
                    pieces=tuple(
                        sorted(
                            pieces,
                            key=lambda piece: (
                                piece.position,
                                piece.owner.value,
                                piece.piece,
                            ),
                        )
                    ),
                )

                expected = []
                for row_delta, column_delta in definition.role(
                    Player.A
                ).action.vectors:
                    destination = (
                        origin[0] + row_delta,
                        origin[1] + column_delta,
                    )
                    if not all(0 <= coordinate < 3 for coordinate in destination):
                        continue
                    if (
                        destination not in occupied
                        or occupied[destination] is Player.B
                    ):
                        expected.append(Action.swap(origin, destination))

                self.assertEqual(
                    legal_actions(definition, state),
                    tuple(sorted(expected, key=Action.sort_key)),
                )
                checked += 1

        self.assertEqual(checked, 59049)

    def test_swap_has_ordinary_and_special_legal_transitions(self) -> None:
        definition = parse_definition(swap_definition())
        state = initial_state(definition)
        ordinary = Action.swap((0, 0), (0, 1))
        special = Action.swap((1, 0), (1, 1))

        self.assertEqual(legal_actions(definition, state), (ordinary, special))
        self.assertTrue(
            all(
                action.kind is ActionKind.SWAP
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
            tuple(
                (piece.owner, piece.piece, piece.position)
                for piece in ordinary_state.pieces
            ),
            (
                (Player.A, "swapper", (0, 1)),
                (Player.A, "swapper", (1, 0)),
                (Player.B, "runner", (1, 1)),
            ),
        )

        special_state = apply_action(definition, state, special)
        self.assertEqual(
            tuple(
                (piece.owner, piece.piece, piece.position)
                for piece in special_state.pieces
            ),
            (
                (Player.A, "swapper", (0, 0)),
                (Player.B, "runner", (1, 0)),
                (Player.A, "swapper", (1, 1)),
            ),
        )

    def test_swap_rejects_friendly_boundary_and_undeclared_vectors(self) -> None:
        raw = swap_definition()
        raw["board_size"] = 4
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
        raw["initial_pieces"] = [
            {"owner": "A", "piece": "swapper", "position": [0, 0]},
            {"owner": "B", "piece": "target", "position": [0, 1]},
            {"owner": "A", "piece": "swapper", "position": [1, 0]},
            {"owner": "A", "piece": "block", "position": [1, 1]},
            {"owner": "A", "piece": "swapper", "position": [2, 0]},
            {"owner": "A", "piece": "swapper", "position": [3, 3]},
        ]
        definition = parse_definition(raw)
        state = initial_state(definition)
        valid = (
            Action.swap((0, 0), (0, 1)),
            Action.swap((2, 0), (2, 1)),
        )
        invalid = {
            "friendly destination": Action.swap((1, 0), (1, 1)),
            "off-board destination": Action.swap((3, 3), (3, 4)),
            "undeclared vector": Action.swap((2, 0), (3, 0)),
            "ranged destination": Action.swap((2, 0), (2, 2)),
        }

        self.assertEqual(legal_actions(definition, state), valid)
        for label, action in invalid.items():
            with self.subTest(label=label):
                self.assertNotIn(action, legal_actions(definition, state))
                with self.assertRaisesRegex(IllegalAction, "not legal"):
                    apply_action(definition, state, action)

    def test_swap_action_serialization_and_replay_preserve_kind(self) -> None:
        definition = parse_definition(swap_definition())
        action = Action.swap((1, 0), (1, 1))
        recorded = {"kind": "SWAP", "from": [1, 0], "to": [1, 1]}

        self.assertEqual(action.to_dict(), recorded)
        self.assertEqual(action_from_dict(recorded), action)
        self.assertEqual(
            replay_dicts(definition, [recorded]),
            replay(definition, [action]),
        )
        with self.assertRaisesRegex(IllegalAction, "fields do not match"):
            action_from_dict({**recorded, "landing": [1, 0]})

    def test_swap_opponent_and_simultaneous_goals_keep_v4_priority(self) -> None:
        opponent_raw = swap_definition()
        opponent_raw["max_plies"] = 1
        opponent_raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_a",
            "edge": "TOP",
        }
        opponent_raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "runner",
            "edge": "LEFT",
        }
        opponent_raw["roles"]["B"]["action"]["vectors"] = [[0, -1]]
        opponent_raw["initial_pieces"] = [
            {"owner": "A", "piece": "swapper", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [1, 1]},
        ]
        opponent_definition = parse_definition(opponent_raw)
        opponent_state = apply_action(
            opponent_definition,
            initial_state(opponent_definition),
            Action.swap((1, 0), (1, 1)),
        )
        self.assertEqual(opponent_state.outcome.winner, Player.B)
        self.assertEqual(opponent_state.outcome.reason, "GOAL")

        simultaneous_raw = swap_definition()
        simultaneous_raw["max_plies"] = 1
        simultaneous_raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "runner",
            "edge": "LEFT",
        }
        simultaneous_raw["roles"]["B"]["action"]["vectors"] = [[0, -1]]
        simultaneous_raw["initial_pieces"] = [
            {"owner": "A", "piece": "swapper", "position": [0, 1]},
            {"owner": "A", "piece": "swapper", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [1, 1]},
            {"owner": "A", "piece": "swapper", "position": [2, 1]},
        ]
        simultaneous_definition = parse_definition(simultaneous_raw)
        simultaneous_state = apply_action(
            simultaneous_definition,
            initial_state(simultaneous_definition),
            Action.swap((1, 0), (1, 1)),
        )
        self.assertEqual(simultaneous_state.outcome.winner, Player.A)
        self.assertEqual(simultaneous_state.outcome.reason, "GOAL")


if __name__ == "__main__":
    unittest.main()
