import unittest
from collections import Counter
from itertools import product

from parity_forge.analysis import FailureCode, analyze_definition
from parity_forge.dsl import (
    ActionKind,
    InitialPiece,
    MOVEMENT_ACTION_KINDS,
    Player,
    VECTOR_ACTION_KINDS,
    describe_rules,
    parse_definition,
)
from parity_forge.engine import (
    Action,
    GameState,
    IllegalAction,
    action_from_dict,
    apply_action,
    initial_state,
    legal_actions,
)
from parity_forge.simplicity import evaluate_simplicity
from parity_forge.symmetry import D4_TRANSFORMS, d4_canonical_hash, transform_definition


def move_capture_definition():
    return {
        "schema_version": 4,
        "name": "Move capture reuse probe",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 20,
        "roles": {
            "A": {
                "action": {
                    "kind": "MOVE_CAPTURE",
                    "piece": "hunter",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "hunter",
                    "edge": "RIGHT",
                },
            },
            "B": {
                "action": {
                    "kind": "HOP",
                    "piece": "runner",
                    "vectors": [[0, -1]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "TOP",
                },
            },
        },
        "initial_pieces": [
            {"owner": "A", "piece": "hunter", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [2, 2]},
        ],
    }


def canonical_pieces(*pieces):
    return tuple(
        sorted(
            pieces,
            key=lambda piece: (piece.position, piece.owner.value, piece.piece),
        )
    )


def piece_snapshot(state):
    return tuple(
        (piece.owner, piece.piece, piece.position) for piece in state.pieces
    )


class SchemaV4MoveCaptureReuseTests(unittest.TestCase):
    def test_move_capture_matches_optional_capture_step_for_all_3x3_occupancies(
        self,
    ) -> None:
        raw = move_capture_definition()
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
        capture_count = 0
        legal_count_histogram = Counter()

        for origin in cells:
            other_cells = tuple(cell for cell in cells if cell != origin)
            for labels in product(range(3), repeat=len(other_cells)):
                pieces = [InitialPiece(Player.A, "hunter", origin)]
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
                    destination = (
                        origin[0] + row_delta,
                        origin[1] + column_delta,
                    )
                    if not all(0 <= coordinate < 3 for coordinate in destination):
                        continue
                    destination_owner = occupied.get(destination)
                    if destination_owner is Player.A:
                        continue
                    expected.append(Action.move_capture(origin, destination))
                    if destination_owner is None:
                        ordinary_count += 1
                    else:
                        capture_count += 1

                actual = legal_actions(definition, state)
                self.assertEqual(
                    actual,
                    tuple(sorted(expected, key=Action.sort_key)),
                )
                checked += 1
                legal_count_histogram[len(actual)] += 1

        self.assertEqual(checked, 59049)
        self.assertEqual(ordinary_count, 87480)
        self.assertEqual(capture_count, 87480)
        self.assertEqual(ordinary_count + capture_count, 174960)
        self.assertEqual(
            dict(sorted(legal_count_histogram.items())),
            {
                0: 1081,
                1: 6928,
                2: 16096,
                3: 16864,
                4: 9760,
                5: 5248,
                6: 1792,
                7: 1024,
                8: 256,
            },
        )

    def test_reuse_adds_no_capture_step_kind_or_record_shape(self) -> None:
        self.assertFalse(hasattr(ActionKind, "CAPTURE_STEP"))
        with self.assertRaises(ValueError):
            ActionKind("CAPTURE_STEP")

        action = Action.move_capture((1, 0), (1, 1))
        record = {
            "kind": "MOVE_CAPTURE",
            "from": [1, 0],
            "to": [1, 1],
        }
        self.assertEqual(action.to_dict(), record)
        self.assertEqual(action_from_dict(record), action)
        with self.assertRaisesRegex(IllegalAction, "invalid kind"):
            action_from_dict({**record, "kind": "CAPTURE_STEP"})
        for extra in ("captured", "target", "target_kind", "mandatory"):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(IllegalAction, "fields"):
                    action_from_dict({**record, extra: True})

    def test_ordinary_and_capture_transitions_use_the_same_action_kind(self) -> None:
        ordinary_definition = parse_definition(move_capture_definition())
        ordinary_state = initial_state(ordinary_definition)
        ordinary = Action.move_capture((1, 0), (1, 1))
        self.assertEqual(legal_actions(ordinary_definition, ordinary_state), (ordinary,))
        after_ordinary = apply_action(
            ordinary_definition,
            ordinary_state,
            ordinary,
        )
        self.assertEqual(len(after_ordinary.pieces), len(ordinary_state.pieces))
        self.assertEqual(
            piece_snapshot(after_ordinary),
            (
                (Player.A, "hunter", (1, 1)),
                (Player.B, "runner", (2, 2)),
            ),
        )

        for target_kind in ("idol", "hunter"):
            with self.subTest(target_kind=target_kind):
                raw = move_capture_definition()
                raw["initial_pieces"].append(
                    {"owner": "B", "piece": target_kind, "position": [1, 1]}
                )
                definition = parse_definition(raw)
                state = initial_state(definition)
                capture = Action.move_capture((1, 0), (1, 1))
                self.assertEqual(legal_actions(definition, state), (capture,))
                after_capture = apply_action(definition, state, capture)
                self.assertEqual(len(after_capture.pieces), len(state.pieces) - 1)
                self.assertEqual(
                    piece_snapshot(after_capture),
                    (
                        (Player.A, "hunter", (1, 1)),
                        (Player.B, "runner", (2, 2)),
                    ),
                )

    def test_capture_is_optional_when_an_ordinary_step_also_exists(self) -> None:
        definition = parse_definition(move_capture_definition())
        state = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(
                InitialPiece(Player.A, "hunter", (0, 0)),
                InitialPiece(Player.A, "hunter", (1, 0)),
                InitialPiece(Player.B, "target", (1, 1)),
                InitialPiece(Player.B, "runner", (2, 2)),
            ),
        )
        self.assertEqual(
            legal_actions(definition, state),
            (
                Action.move_capture((0, 0), (0, 1)),
                Action.move_capture((1, 0), (1, 1)),
            ),
        )

    def test_friendly_ranged_undeclared_and_wrong_actor_actions_are_rejected(
        self,
    ) -> None:
        definition = parse_definition(move_capture_definition())
        base = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(
                InitialPiece(Player.A, "hunter", (1, 0)),
                InitialPiece(Player.B, "runner", (2, 2)),
            ),
        )
        cases = (
            (
                "wrong action kind",
                base,
                Action.move((1, 0), (1, 1)),
            ),
            (
                "undeclared vector",
                base,
                Action.move_capture((1, 0), (0, 0)),
            ),
            (
                "ranged destination",
                base,
                Action.move_capture((1, 0), (1, 2)),
            ),
            (
                "empty source",
                base,
                Action.move_capture((0, 0), (0, 1)),
            ),
            (
                "friendly target",
                GameState(
                    ply=0,
                    to_move=Player.A,
                    pieces=canonical_pieces(
                        InitialPiece(Player.A, "hunter", (1, 0)),
                        InitialPiece(Player.A, "friend", (1, 1)),
                        InitialPiece(Player.B, "runner", (2, 2)),
                    ),
                ),
                Action.move_capture((1, 0), (1, 1)),
            ),
            (
                "wrong actor kind",
                GameState(
                    ply=0,
                    to_move=Player.A,
                    pieces=canonical_pieces(
                        InitialPiece(Player.A, "scout", (1, 0)),
                        InitialPiece(Player.B, "runner", (2, 2)),
                    ),
                ),
                Action.move_capture((1, 0), (1, 1)),
            ),
            (
                "opponent actor",
                GameState(
                    ply=0,
                    to_move=Player.A,
                    pieces=canonical_pieces(
                        InitialPiece(Player.B, "hunter", (1, 0)),
                        InitialPiece(Player.B, "runner", (2, 2)),
                    ),
                ),
                Action.move_capture((1, 0), (1, 1)),
            ),
            (
                "off-board destination",
                GameState(
                    ply=0,
                    to_move=Player.A,
                    pieces=canonical_pieces(
                        InitialPiece(Player.A, "hunter", (1, 2)),
                        InitialPiece(Player.B, "runner", (2, 2)),
                    ),
                ),
                Action.move_capture((1, 2), (1, 3)),
            ),
        )
        for label, state, action in cases:
            with self.subTest(label=label):
                self.assertNotIn(action, legal_actions(definition, state))
                with self.assertRaisesRegex(IllegalAction, "not legal"):
                    apply_action(definition, state, action)

    def test_move_capture_keeps_schema_v4_terminal_priorities(self) -> None:
        raw = move_capture_definition()
        raw["max_plies"] = 1
        definition = parse_definition(raw)

        simultaneous = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(
                InitialPiece(Player.A, "hunter", (1, 1)),
                InitialPiece(Player.B, "target", (1, 2)),
                InitialPiece(Player.B, "runner", (0, 0)),
            ),
        )
        after_simultaneous = apply_action(
            definition,
            simultaneous,
            Action.move_capture((1, 1), (1, 2)),
        )
        self.assertEqual(after_simultaneous.outcome.winner, Player.A)
        self.assertEqual(after_simultaneous.outcome.reason, "GOAL")

        opponent_goal = GameState(
            ply=0,
            to_move=Player.A,
            pieces=canonical_pieces(
                InitialPiece(Player.A, "hunter", (1, 0)),
                InitialPiece(Player.B, "runner", (0, 0)),
            ),
        )
        after_opponent_goal = apply_action(
            definition,
            opponent_goal,
            Action.move_capture((1, 0), (1, 1)),
        )
        self.assertEqual(after_opponent_goal.outcome.winner, Player.B)
        self.assertEqual(after_opponent_goal.outcome.reason, "GOAL")

        before_limit = GameState(
            ply=0,
            to_move=Player.A,
            pieces=(InitialPiece(Player.A, "hunter", (1, 0)),),
        )
        after_limit = apply_action(
            definition,
            before_limit,
            Action.move_capture((1, 0), (1, 1)),
        )
        self.assertIsNone(after_limit.outcome.winner)
        self.assertEqual(after_limit.outcome.reason, "PLY_LIMIT")

        raw["max_plies"] = 2
        stuck_definition = parse_definition(raw)
        after_stuck = apply_action(
            stuck_definition,
            before_limit,
            Action.move_capture((1, 0), (1, 1)),
        )
        self.assertEqual(after_stuck.outcome.winner, Player.A)
        self.assertEqual(after_stuck.outcome.reason, "NO_LEGAL_ACTION")

    def test_v4_move_capture_keeps_vector_d4_static_and_simplicity_behavior(
        self,
    ) -> None:
        self.assertIn(ActionKind.MOVE_CAPTURE, MOVEMENT_ACTION_KINDS)
        self.assertIn(ActionKind.MOVE_CAPTURE, VECTOR_ACTION_KINDS)

        raw = move_capture_definition()
        raw["name"] = "Asymmetric move capture reuse fixture"
        raw["board_size"] = 5
        raw["roles"]["A"]["action"]["vectors"] = [
            [-1, -1],
            [-1, 0],
            [0, 1],
        ]
        raw["initial_pieces"] = [
            {"owner": "A", "piece": "hunter", "position": [4, 1]},
            {"owner": "B", "piece": "runner", "position": [4, 4]},
        ]
        asymmetric = parse_definition(raw)
        expected_vectors = {
            "I": ((-1, -1), (-1, 0), (0, 1)),
            "R90": ((-1, 1), (0, 1), (1, 0)),
            "R180": ((0, -1), (1, 0), (1, 1)),
            "R270": ((-1, 0), (0, -1), (1, -1)),
            "FLR": ((-1, 0), (-1, 1), (0, -1)),
            "FTB": ((0, 1), (1, -1), (1, 0)),
            "FD": ((-1, -1), (0, -1), (1, 0)),
            "FA": ((-1, 0), (0, 1), (1, 1)),
        }
        baseline = d4_canonical_hash(asymmetric)
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(asymmetric, transform)
                self.assertIs(
                    transformed.role(Player.A).action.kind,
                    ActionKind.MOVE_CAPTURE,
                )
                self.assertEqual(
                    transformed.role(Player.A).action.vectors,
                    expected_vectors[transform],
                )
                self.assertEqual(d4_canonical_hash(transformed), baseline)

        reachable_raw = move_capture_definition()
        reachable_raw["roles"]["A"]["action"]["vectors"] = [[-1, 0]]
        reachable_raw["roles"]["A"]["goal"]["edge"] = "TOP"
        reachable_raw["roles"]["B"]["action"]["vectors"] = [[-1, 0]]
        reachable_raw["initial_pieces"] = [
            {"owner": "A", "piece": "hunter", "position": [2, 1]},
            {"owner": "B", "piece": "runner", "position": [2, 2]},
        ]
        reachable_report = analyze_definition(parse_definition(reachable_raw))
        self.assertNotIn(
            FailureCode.UNREACHABLE_WIN_CONDITION,
            reachable_report.failure_codes,
        )

        unreachable_raw = move_capture_definition()
        unreachable_raw["roles"]["A"]["goal"]["edge"] = "TOP"
        unreachable_raw["roles"]["B"]["action"]["vectors"] = [[-1, 0]]
        unreachable_raw["initial_pieces"] = [
            {"owner": "A", "piece": "hunter", "position": [2, 0]},
            {"owner": "B", "piece": "runner", "position": [2, 2]},
        ]
        unreachable_report = analyze_definition(parse_definition(unreachable_raw))
        self.assertIn(
            FailureCode.UNREACHABLE_WIN_CONDITION,
            unreachable_report.failure_codes,
        )
        self.assertTrue(
            any(
                diagnostic.code is FailureCode.UNREACHABLE_WIN_CONDITION
                and "A" in diagnostic.detail
                for diagnostic in unreachable_report.diagnostics
            )
        )

        ordinary_raw = move_capture_definition()
        ordinary_raw["roles"]["A"]["action"]["kind"] = "MOVE"
        ordinary = evaluate_simplicity(parse_definition(ordinary_raw))
        capture = evaluate_simplicity(
            parse_definition(move_capture_definition())
        )
        self.assertEqual(
            capture.structural.primitive_concepts,
            ordinary.structural.primitive_concepts + 1,
        )
        self.assertEqual(
            capture.description.independent_statements,
            ordinary.description.independent_statements + 1,
        )
        self.assertEqual(
            capture.description.conditional_clauses,
            ordinary.description.conditional_clauses + 1,
        )
        self.assertEqual(
            capture.description.learned_concepts,
            ordinary.description.learned_concepts + 1,
        )
        self.assertEqual(
            capture.structural.action_substeps,
            ordinary.structural.action_substeps,
        )
        self.assertEqual(capture.operational, ordinary.operational)

        capture_rules = describe_rules(parse_definition(move_capture_definition()))
        self.assertTrue(any("may also move" in statement for statement in capture_rules))
        self.assertFalse(any("must capture" in statement for statement in capture_rules))


if __name__ == "__main__":
    unittest.main()
