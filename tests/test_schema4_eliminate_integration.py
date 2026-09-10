import itertools
import json
import unittest

from parity_forge.analysis import (
    FailureCode,
    analyze_definition,
)
from parity_forge.dsl import (
    ActionKind,
    GoalKind,
    InitialPiece,
    Player,
    definition_hash,
    parse_definition,
)
from parity_forge.engine import goal_satisfied
from parity_forge.simplicity import evaluate_simplicity
from parity_forge.symmetry import (
    D4_TRANSFORMS,
    d4_canonical_hash,
    mechanical_json,
    transform_definition,
)


ELIMINATE_DEFINITION_HASH = (
    "a3a1761e1a04e62f95d69e0190d7368936842fdaf40a123f02a0f5696ec8f0a2"
)
ELIMINATE_D4_HASH = (
    "3a104109d52a633fb2b698fdfffa7f7189f373ad357d5796e7accba923013030"
)


def _action(kind, piece, vector):
    result = {"kind": kind, "piece": piece}
    if kind != "PLACE":
        result["vectors"] = [list(vector)]
    return result


def static_definition(action_kind, *, actor=True, target=True):
    pieces = [
        {"owner": "B", "piece": "runner", "position": [2, 0]},
    ]
    if actor:
        pieces.append(
            {"owner": "A", "piece": "hunter", "position": [2, 1]}
        )
    if target:
        pieces.append(
            {"owner": "B", "piece": "quarry", "position": [1, 1]}
        )
    return parse_definition(
        {
            "schema_version": 4,
            "name": "Eliminate static relaxation",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 20,
            "roles": {
                "A": {
                    "action": _action(action_kind, "hunter", (-1, 0)),
                    "goal": {"kind": "ELIMINATE", "piece": "quarry"},
                },
                "B": {
                    "action": _action("HOP", "runner", (-1, 0)),
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "runner",
                        "edge": "TOP",
                    },
                },
            },
            "initial_pieces": pieces,
        }
    )


def d4_definition():
    return parse_definition(
        {
            "schema_version": 4,
            "name": "Asymmetric eliminate D4 fixture",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 19,
            "roles": {
                "A": {
                    "action": {
                        "kind": "CONVERT",
                        "piece": "hunter",
                        "vectors": [[-1, 0], [0, 1]],
                    },
                    "goal": {"kind": "ELIMINATE", "piece": "quarry"},
                },
                "B": {
                    "action": {
                        "kind": "MOVE_CAPTURE",
                        "piece": "quarry",
                        "vectors": [[0, -1], [1, 0]],
                    },
                    "goal": {"kind": "ELIMINATE", "piece": "hunter"},
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "hunter", "position": [2, 0]},
                {"owner": "B", "piece": "quarry", "position": [0, 1]},
            ],
        }
    )


def occupancy_oracle_definition():
    return parse_definition(
        {
            "schema_version": 4,
            "name": "Eliminate exhaustive goal oracle",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 9,
            "roles": {
                "A": {
                    "action": {
                        "kind": "MOVE_CAPTURE",
                        "piece": "target",
                        "vectors": [[0, 1]],
                    },
                    "goal": {"kind": "ELIMINATE", "piece": "target"},
                },
                "B": {
                    "action": {
                        "kind": "MOVE_CAPTURE",
                        "piece": "target",
                        "vectors": [[0, -1]],
                    },
                    "goal": {"kind": "ELIMINATE", "piece": "target"},
                },
            },
            "initial_pieces": [],
        }
    )


def simplicity_definition(first_goal, second_goal, *, first_piece="token"):
    def goal(kind, edge):
        result = {"kind": kind, "piece": first_piece if edge == "LEFT" else "token"}
        if kind == "REACH_EDGE":
            result["edge"] = edge
        return result

    return parse_definition(
        {
            "schema_version": 4,
            "name": "Eliminate simplicity comparison",
            "board_size": 5,
            "first_player": "A",
            "max_plies": 20,
            "roles": {
                "A": {
                    "action": {
                        "kind": "PUSH",
                        "piece": "token",
                        "vectors": [[0, 1]],
                    },
                    "goal": goal(first_goal, "LEFT"),
                },
                "B": {
                    "action": {
                        "kind": "HOP",
                        "piece": "token",
                        "vectors": [[0, -1]],
                    },
                    "goal": goal(second_goal, "RIGHT"),
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "token", "position": [2, 1]},
                {"owner": "B", "piece": "token", "position": [2, 3]},
            ],
        }
    )


def _transform_position(position, transform):
    row, column = position
    maximum = 2
    return {
        "I": (row, column),
        "R90": (column, maximum - row),
        "R180": (maximum - row, maximum - column),
        "R270": (maximum - column, row),
        "FLR": (row, maximum - column),
        "FTB": (maximum - row, column),
        "FD": (column, row),
        "FA": (maximum - column, maximum - row),
    }[transform]


class Schema4EliminateIntegrationTests(unittest.TestCase):
    def test_static_initial_zero_target_is_trivial_but_not_unreachable(self) -> None:
        definition = static_definition("MOVE_CAPTURE", target=False)
        report = analyze_definition(definition)

        self.assertTrue(
            goal_satisfied(definition, definition.initial_pieces, Player.A)
        )
        self.assertIn(FailureCode.TRIVIAL_FORCED_RESULT, report.failure_codes)
        self.assertNotIn(
            FailureCode.UNREACHABLE_WIN_CONDITION,
            report.failure_codes,
        )

    def test_static_eliminate_relaxes_only_capture_or_conversion_with_an_actor(self) -> None:
        for action_kind in ("MOVE_CAPTURE", "CONVERT"):
            with self.subTest(action_kind=action_kind):
                report = analyze_definition(static_definition(action_kind))
                self.assertNotIn(
                    FailureCode.UNREACHABLE_WIN_CONDITION,
                    report.failure_codes,
                )

        for action_kind in ("PLACE", "MOVE", "PUSH", "SWAP", "HOP"):
            with self.subTest(action_kind=action_kind):
                report = analyze_definition(static_definition(action_kind))
                self.assertIn(
                    FailureCode.UNREACHABLE_WIN_CONDITION,
                    report.failure_codes,
                )

    def test_static_eliminate_requires_matching_action_actor_not_target_kind(self) -> None:
        for action_kind in ("MOVE_CAPTURE", "CONVERT"):
            with self.subTest(action_kind=action_kind):
                without_actor = static_definition(action_kind, actor=False)
                self.assertIn(
                    FailureCode.UNREACHABLE_WIN_CONDITION,
                    analyze_definition(without_actor).failure_codes,
                )

                independent_kinds = static_definition(action_kind)
                role = independent_kinds.role(Player.A)
                self.assertEqual(role.action.piece, "hunter")
                self.assertEqual(role.goal.piece, "quarry")
                self.assertNotIn(
                    FailureCode.UNREACHABLE_WIN_CONDITION,
                    analyze_definition(independent_kinds).failure_codes,
                )

    def test_d4_keeps_eliminate_goals_non_spatial_and_hashes_the_full_definition(self) -> None:
        definition = d4_definition()
        exact_hash = definition_hash(definition)
        canonical_hash = d4_canonical_hash(definition)
        self.assertEqual(exact_hash, ELIMINATE_DEFINITION_HASH)
        self.assertEqual(canonical_hash, ELIMINATE_D4_HASH)

        source_goals = {
            player: definition.role(player).goal.to_dict() for player in Player
        }
        orbit = set()
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(definition, transform)
                orbit.add(mechanical_json(transformed))
                for player in Player:
                    self.assertIs(
                        transformed.role(player).goal.kind,
                        GoalKind.ELIMINATE,
                    )
                    self.assertEqual(
                        transformed.role(player).goal.to_dict(),
                        source_goals[player],
                    )
                self.assertEqual(
                    d4_canonical_hash(transformed),
                    canonical_hash,
                )

        self.assertGreater(len(orbit), 1)
        self.assertNotEqual(
            definition_hash(transform_definition(definition, "R90")),
            exact_hash,
        )
        payload = json.loads(mechanical_json(definition))
        self.assertNotIn("edge", payload["roles"]["A"]["goal"])
        self.assertNotIn("edges", payload["roles"]["A"]["goal"])

    def test_eliminate_goal_predicate_matches_all_occupancies_under_all_d4_maps(self) -> None:
        definition = occupancy_oracle_definition()
        transformed_definitions = {
            transform: transform_definition(definition, transform)
            for transform in D4_TRANSFORMS
        }
        positions = tuple(itertools.product(range(3), repeat=2))
        truth_histogram = {
            "neither": 0,
            "A_only": 0,
            "B_only": 0,
            "both": 0,
        }
        predicate_checks = 0

        for assignment in itertools.product((0, 1, 2), repeat=9):
            pieces = tuple(
                InitialPiece(
                    owner=Player.A if occupant == 1 else Player.B,
                    piece="target",
                    position=position,
                )
                for position, occupant in zip(positions, assignment)
                if occupant
            )
            expected_a = 2 not in assignment
            expected_b = 1 not in assignment
            label = (
                "both"
                if expected_a and expected_b
                else "A_only"
                if expected_a
                else "B_only"
                if expected_b
                else "neither"
            )
            truth_histogram[label] += 1

            for transform in D4_TRANSFORMS:
                transformed_pieces = tuple(
                    InitialPiece(
                        owner=piece.owner,
                        piece=piece.piece,
                        position=_transform_position(piece.position, transform),
                    )
                    for piece in pieces
                )
                transformed = transformed_definitions[transform]
                self.assertEqual(
                    goal_satisfied(transformed, transformed_pieces, Player.A),
                    expected_a,
                )
                self.assertEqual(
                    goal_satisfied(transformed, transformed_pieces, Player.B),
                    expected_b,
                )
                predicate_checks += 2

        self.assertEqual(
            truth_histogram,
            {"neither": 18660, "A_only": 511, "B_only": 511, "both": 1},
        )
        self.assertEqual(predicate_checks, 314928)

    def test_one_eliminate_goal_adds_only_one_shared_learned_primitive(self) -> None:
        reach = evaluate_simplicity(
            simplicity_definition("REACH_EDGE", "REACH_EDGE")
        ).to_dict()
        one_eliminate = evaluate_simplicity(
            simplicity_definition("ELIMINATE", "REACH_EDGE")
        ).to_dict()

        expected = json.loads(json.dumps(reach))
        expected["structural"]["primitive_concepts"] += 1
        expected["description"]["learned_concepts"] += 1
        self.assertEqual(one_eliminate, expected)

    def test_two_eliminate_roles_share_one_goal_primitive(self) -> None:
        reach = evaluate_simplicity(
            simplicity_definition("REACH_EDGE", "REACH_EDGE")
        )
        eliminate = evaluate_simplicity(
            simplicity_definition("ELIMINATE", "ELIMINATE")
        )

        self.assertEqual(eliminate.to_dict(), reach.to_dict())

    def test_only_a_new_eliminate_target_identifier_adds_a_piece_type(self) -> None:
        existing = evaluate_simplicity(
            simplicity_definition("ELIMINATE", "ELIMINATE")
        )
        new_target = evaluate_simplicity(
            simplicity_definition(
                "ELIMINATE",
                "ELIMINATE",
                first_piece="quarry",
            )
        )

        self.assertEqual(
            new_target.structural.piece_types,
            existing.structural.piece_types + 1,
        )


if __name__ == "__main__":
    unittest.main()
