import unittest
from collections import Counter
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


def convert_definition():
    return {
        "schema_version": 4,
        "name": "Convert engine probe",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 20,
        "roles": {
            "A": {
                "action": {
                    "kind": "CONVERT",
                    "piece": "converter",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "CONNECT_EDGES",
                    "piece": "converter",
                    "edges": ["TOP", "BOTTOM"],
                },
            },
            "B": {
                "action": {
                    "kind": "MOVE",
                    "piece": "runner",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "RIGHT",
                },
            },
        },
        "initial_pieces": [
            {"owner": "A", "piece": "converter", "position": [0, 0]},
            {"owner": "A", "piece": "converter", "position": [1, 0]},
            {"owner": "B", "piece": "target", "position": [1, 1]},
            {"owner": "B", "piece": "runner", "position": [2, 0]},
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


class SchemaV4ConvertEngineTests(unittest.TestCase):
    def test_convert_action_uses_shared_exact_value_boundaries(self) -> None:
        invalid_actions = (
            lambda: Action(  # type: ignore[arg-type]
                kind="CONVERT",
                from_position=(1, 0),
                to_position=(1, 1),
            ),
            lambda: Action.convert((True, 0), (1, 1)),
            lambda: Action(
                kind=ActionKind.CONVERT,
                from_position=None,
                to_position=(1, 1),
            ),
        )
        for make_action in invalid_actions:
            with self.subTest(make_action=make_action):
                with self.assertRaises(IllegalAction):
                    make_action()

        definition = parse_definition(convert_definition())
        state = initial_state(definition)
        forged_kind = Action.convert((1, 0), (1, 1))
        object.__setattr__(forged_kind, "kind", "CONVERT")
        forged_position = Action.convert((1, 0), (1, 1))
        object.__setattr__(forged_position, "to_position", (1, True))
        hidden = Action.convert((1, 0), (1, 1))
        object.__setattr__(hidden, "target_kind", "target")
        missing = Action.convert((1, 0), (1, 1))
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

    def test_convert_legality_matches_local_reference_for_all_3x3_occupancies(
        self,
    ) -> None:
        raw = convert_definition()
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
        legal_action_total = 0
        legal_count_histogram = Counter()

        for origin in cells:
            other_cells = tuple(cell for cell in cells if cell != origin)
            for labels in product(range(3), repeat=len(other_cells)):
                pieces = [InitialPiece(Player.A, "converter", origin)]
                occupied = {origin: Player.A}
                for position, label in zip(other_cells, labels):
                    if label == 1:
                        pieces.append(
                            InitialPiece(Player.A, "friendly", position)
                        )
                        occupied[position] = Player.A
                    elif label == 2:
                        pieces.append(
                            InitialPiece(Player.B, "opponent", position)
                        )
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
                    target = (
                        origin[0] + row_delta,
                        origin[1] + column_delta,
                    )
                    if (
                        all(0 <= coordinate < 3 for coordinate in target)
                        and occupied.get(target) is Player.B
                    ):
                        expected.append(Action.convert(origin, target))

                actual = legal_actions(definition, state)
                self.assertEqual(
                    actual,
                    tuple(sorted(expected, key=Action.sort_key)),
                )
                checked += 1
                legal_action_total += len(actual)
                legal_count_histogram[len(actual)] += 1

        self.assertEqual(checked, 59049)
        self.assertEqual(legal_action_total, 87480)
        self.assertEqual(
            dict(sorted(legal_count_histogram.items())),
            {
                0: 11488,
                1: 21328,
                2: 16264,
                3: 7084,
                4: 2200,
                5: 556,
                6: 112,
                7: 16,
                8: 1,
            },
        )

    def test_convert_changes_only_the_opponent_target(self) -> None:
        raw = convert_definition()
        raw["initial_pieces"][2]["piece"] = "converter"
        definition = parse_definition(raw)
        state = initial_state(definition)
        action = Action.convert((1, 0), (1, 1))

        self.assertEqual(legal_actions(definition, state), (action,))
        self.assertTrue(
            all(
                legal.kind is ActionKind.CONVERT
                for legal in legal_actions(definition, state)
            )
        )
        after = apply_action(definition, state, action)

        self.assertEqual(len(after.pieces), len(state.pieces))
        self.assertEqual(
            {piece.position for piece in after.pieces},
            {piece.position for piece in state.pieces},
        )
        self.assertEqual(
            piece_snapshot(after),
            (
                (Player.A, "converter", (0, 0)),
                (Player.A, "converter", (1, 0)),
                (Player.A, "converter", (1, 1)),
                (Player.B, "runner", (2, 0)),
            ),
        )
        self.assertEqual(
            next(piece for piece in after.pieces if piece.position == (1, 0)),
            next(piece for piece in state.pieces if piece.position == (1, 0)),
        )

    def test_multiple_converters_keep_distinct_actions_to_one_target(self) -> None:
        raw = convert_definition()
        raw["initial_pieces"] = []
        raw["roles"]["A"]["action"]["vectors"] = [
            [-1, 0],
            [0, -1],
            [0, 1],
            [1, 0],
        ]
        definition = parse_definition(raw)
        state = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(
                InitialPiece(Player.A, "converter", (0, 1)),
                InitialPiece(Player.A, "converter", (1, 0)),
                InitialPiece(Player.B, "target", (1, 1)),
                InitialPiece(Player.A, "converter", (1, 2)),
                InitialPiece(Player.A, "converter", (2, 1)),
            ),
        )

        self.assertEqual(
            legal_actions(definition, state),
            (
                Action.convert((0, 1), (1, 1)),
                Action.convert((1, 0), (1, 1)),
                Action.convert((1, 2), (1, 1)),
                Action.convert((2, 1), (1, 1)),
            ),
        )

    def test_convert_rejects_empty_friendly_boundary_and_wrong_actions(
        self,
    ) -> None:
        raw = convert_definition()
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
        state = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(
                InitialPiece(Player.A, "converter", (0, 0)),
                InitialPiece(Player.B, "target", (0, 1)),
                InitialPiece(Player.A, "converter", (1, 0)),
                InitialPiece(Player.A, "converter", (2, 0)),
                InitialPiece(Player.A, "friendly", (2, 1)),
                InitialPiece(Player.A, "wrong_kind", (3, 0)),
                InitialPiece(Player.B, "target", (3, 1)),
                InitialPiece(Player.B, "converter", (4, 0)),
                InitialPiece(Player.A, "target", (4, 1)),
                InitialPiece(Player.A, "converter", (4, 4)),
            ),
        )
        valid = Action.convert((0, 0), (0, 1))
        invalid = {
            "empty target": Action.convert((1, 0), (1, 1)),
            "friendly target": Action.convert((2, 0), (2, 1)),
            "wrong-kind source": Action.convert((3, 0), (3, 1)),
            "opponent source": Action.convert((4, 0), (4, 1)),
            "missing source": Action.convert((1, 2), (1, 3)),
            "off-board target": Action.convert((4, 4), (4, 5)),
            "ranged target": Action.convert((0, 0), (0, 2)),
            "undeclared vector": Action.convert((0, 0), (1, 0)),
            "wrong action kind": Action.move((0, 0), (0, 1)),
        }

        self.assertEqual(legal_actions(definition, state), (valid,))
        for label, action in invalid.items():
            with self.subTest(label=label):
                self.assertNotIn(action, legal_actions(definition, state))
                with self.assertRaisesRegex(IllegalAction, "not legal"):
                    apply_action(definition, state, action)

    def test_convert_action_serialization_and_replay_preserve_only_kind_from_to(
        self,
    ) -> None:
        definition = parse_definition(convert_definition())
        action = Action.convert((1, 0), (1, 1))
        recorded = {"kind": "CONVERT", "from": [1, 0], "to": [1, 1]}

        self.assertEqual(action.to_dict(), recorded)
        self.assertEqual(action_from_dict(recorded), action)
        self.assertEqual(
            replay_dicts(definition, [recorded]),
            replay(definition, [action]),
        )
        for extra in ("target", "piece"):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(IllegalAction, "fields do not match"):
                    action_from_dict({**recorded, extra: "target"})

    def test_convert_keeps_actor_goal_ply_limit_and_stuck_priority(self) -> None:
        actor_raw = convert_definition()
        actor_raw["max_plies"] = 1
        actor_raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "converter",
            "edge": "RIGHT",
        }
        actor_raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_b",
            "edge": "TOP",
        }
        actor_raw["initial_pieces"] = [
            {"owner": "A", "piece": "converter", "position": [1, 1]},
            {"owner": "B", "piece": "target", "position": [1, 2]},
        ]
        actor_definition = parse_definition(actor_raw)
        after_actor_goal = apply_action(
            actor_definition,
            initial_state(actor_definition),
            Action.convert((1, 1), (1, 2)),
        )
        self.assertEqual(after_actor_goal.outcome.winner, Player.A)
        self.assertEqual(after_actor_goal.outcome.reason, "GOAL")

        limit_raw = convert_definition()
        limit_raw["max_plies"] = 1
        limit_raw["roles"]["A"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_a",
            "edge": "TOP",
        }
        limit_raw["roles"]["B"]["goal"] = {
            "kind": "REACH_EDGE",
            "piece": "goal_b",
            "edge": "TOP",
        }
        limit_raw["initial_pieces"] = [
            {"owner": "A", "piece": "converter", "position": [1, 1]},
            {"owner": "B", "piece": "target", "position": [1, 2]},
        ]
        limit_definition = parse_definition(limit_raw)
        after_limit = apply_action(
            limit_definition,
            initial_state(limit_definition),
            Action.convert((1, 1), (1, 2)),
        )
        self.assertIsNone(after_limit.outcome.winner)
        self.assertEqual(after_limit.outcome.reason, "PLY_LIMIT")

        limit_raw["max_plies"] = 2
        stuck_definition = parse_definition(limit_raw)
        after_stuck = apply_action(
            stuck_definition,
            initial_state(stuck_definition),
            Action.convert((1, 1), (1, 2)),
        )
        self.assertEqual(after_stuck.outcome.winner, Player.A)
        self.assertEqual(after_stuck.outcome.reason, "NO_LEGAL_ACTION")


if __name__ == "__main__":
    unittest.main()
