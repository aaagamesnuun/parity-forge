import copy
import json
import unittest

from parity_forge.analysis import FailureCode, analyze_definition
from parity_forge.asymmetry import evaluate_asymmetry
from parity_forge.dsl import (
    ActionKind,
    MOVEMENT_ACTION_KINDS,
    Player,
    VECTOR_ACTION_KINDS,
    definition_hash,
    parse_definition,
)
from parity_forge.simplicity import evaluate_simplicity
from parity_forge.symmetry import (
    D4_TRANSFORMS,
    d4_canonical_hash,
    mechanical_json,
    transform_definition,
)

from tests.support import crossing_definition


CONVERT_D4_HASH = "64f7f012a33713f90276d2cd2ecfdc5bef8c5966295632c575a64c8dcbbc1f0f"


def asymmetric_action_definition(kind):
    raw = crossing_definition()
    raw["schema_version"] = 4
    raw["name"] = "Asymmetric {} D4 fixture".format(kind.lower())
    raw["board_size"] = 5
    raw["max_plies"] = 15
    raw["initial_pieces"][0]["position"] = [4, 1]
    raw["roles"]["B"]["action"]["kind"] = kind
    raw["roles"]["B"]["action"]["vectors"] = [
        [-1, -1],
        [-1, 0],
        [0, 1],
    ]
    return parse_definition(raw)


def comparison_definition(first_kind, second_kind, second_vectors=None):
    raw = {
        "schema_version": 4,
        "name": "Convert simplicity comparison",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 20,
        "roles": {
            "A": {
                "action": {
                    "kind": first_kind,
                    "piece": "seed",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "seed",
                    "edge": "TOP",
                },
            },
            "B": {
                "action": {
                    "kind": second_kind,
                    "piece": "runner",
                    "vectors": second_vectors or [[0, -1]],
                },
                "goal": {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "TOP",
                },
            },
        },
        "initial_pieces": [
            {"owner": "A", "piece": "seed", "position": [1, 0]},
            {"owner": "B", "piece": "runner", "position": [1, 1]},
        ],
    }
    return parse_definition(raw)


def convert_static_definition(goal_kind, *, actor, matching_piece):
    action_piece = "seed" if matching_piece else "ink"
    goal = {"kind": goal_kind, "piece": "seed"}
    if goal_kind == "REACH_EDGE":
        goal["edge"] = "TOP"
    else:
        goal["edges"] = ["TOP", "BOTTOM"]

    pieces = [{"owner": "B", "piece": "runner", "position": [1, 1]}]
    if actor:
        pieces.append(
            {"owner": "A", "piece": action_piece, "position": [2, 1]}
        )
    if not matching_piece:
        pieces.append({"owner": "A", "piece": "seed", "position": [1, 0]})

    return parse_definition(
        {
            "schema_version": 4,
            "name": "Convert static relaxation",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 20,
            "roles": {
                "A": {
                    "action": {
                        "kind": "CONVERT",
                        "piece": action_piece,
                        "vectors": [[-1, 0]],
                    },
                    "goal": goal,
                },
                "B": {
                    "action": {
                        "kind": "HOP",
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
            "initial_pieces": pieces,
        }
    )


def special_dsl_definition(kind):
    raw = crossing_definition()
    raw["schema_version"] = 4
    raw["name"] = {
        "PUSH": "Pushing Crossing",
        "SWAP": "Swapping Crossing",
        "HOP": "Hopping Crossing",
    }[kind]
    raw["roles"]["A"]["action"] = {
        "kind": kind,
        "piece": "seed",
        "vectors": [[1, 0], [0, 1], [-1, 0], [0, -1]],
    }
    return parse_definition(raw)


def legacy_definition(schema_version):
    raw = crossing_definition()
    raw["schema_version"] = schema_version
    if schema_version == 2:
        raw["terminal_policy"] = {"no_legal_action": "DRAW"}
    elif schema_version == 3:
        raw["roles"]["B"]["action"]["kind"] = "MOVE_CAPTURE"
    return parse_definition(raw)


class Schema4ConvertIntegrationTests(unittest.TestCase):
    def test_convert_is_vector_bearing_but_not_movement(self) -> None:
        self.assertIn(ActionKind.CONVERT, VECTOR_ACTION_KINDS)
        self.assertNotIn(ActionKind.CONVERT, MOVEMENT_ACTION_KINDS)

        definition = comparison_definition("CONVERT", "PUSH", [[0, 1]])
        report = evaluate_asymmetry(definition)
        self.assertTrue(report.action_primitives_differ)
        self.assertFalse(report.placement_rights_differ)
        self.assertTrue(report.mobility_rights_differ)
        self.assertFalse(report.goal_primitives_differ)
        self.assertFalse(report.action_arity_differs)
        self.assertFalse(report.initial_mobility_counts_differ)
        self.assertEqual(report.distinct_dimensions, 2)
        self.assertTrue(report.qualifies)

    def test_d4_transforms_convert_vectors_and_preserves_eight_member_orbit(self) -> None:
        definition = asymmetric_action_definition("CONVERT")
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
        baseline = d4_canonical_hash(definition)
        self.assertEqual(baseline, CONVERT_D4_HASH)
        self.assertEqual(
            mechanical_json(transform_definition(definition, "I")),
            mechanical_json(definition),
        )
        self.assertNotEqual(
            definition_hash(definition),
            definition_hash(transform_definition(definition, "R90")),
        )

        orbit = set()
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(definition, transform)
                orbit.add(mechanical_json(transformed))
                self.assertIs(
                    transformed.role(Player.B).action.kind,
                    ActionKind.CONVERT,
                )
                self.assertEqual(
                    transformed.role(Player.B).action.vectors,
                    expected_vectors[transform],
                )
                self.assertEqual(d4_canonical_hash(transformed), baseline)
        self.assertEqual(len(orbit), 8)

        rotated = definition
        for _ in range(4):
            rotated = transform_definition(rotated, "R90")
        self.assertEqual(mechanical_json(rotated), mechanical_json(definition))
        for reflection in ("FLR", "FTB", "FD", "FA"):
            with self.subTest(reflection=reflection):
                reflected_twice = transform_definition(
                    transform_definition(definition, reflection), reflection
                )
                self.assertEqual(
                    mechanical_json(reflected_twice),
                    mechanical_json(definition),
                )

    def test_convert_adds_only_its_standalone_shared_concept(self) -> None:
        ordinary = evaluate_simplicity(comparison_definition("PUSH", "MOVE"))
        convert = evaluate_simplicity(comparison_definition("PUSH", "CONVERT"))

        self.assertEqual(
            convert.to_dict(),
            {
                "structural": {
                    "action_types": 2,
                    "piece_types": 2,
                    "state_variables": 4,
                    "numeric_parameters": 6,
                    "victory_clauses": 2,
                    "exception_clauses": 0,
                    "phases": 1,
                    "action_substeps": 5,
                    "primitive_concepts": 4,
                },
                "description": {
                    "independent_statements": 13,
                    "conditional_clauses": 6,
                    "exception_clauses": 0,
                    "learned_concepts": 10,
                },
                "operational": {
                    "max_action_parameters": 4,
                    "tracked_fields": 5,
                    "initial_legal_actions": 1,
                },
            },
        )

        self.assertEqual(convert.structural.action_types, ordinary.structural.action_types)
        self.assertEqual(convert.structural.piece_types, ordinary.structural.piece_types)
        self.assertEqual(
            convert.structural.numeric_parameters,
            ordinary.structural.numeric_parameters,
        )
        self.assertEqual(
            convert.structural.action_substeps,
            ordinary.structural.action_substeps,
        )
        self.assertEqual(
            convert.structural.primitive_concepts,
            ordinary.structural.primitive_concepts + 1,
        )
        self.assertEqual(
            convert.description.independent_statements,
            ordinary.description.independent_statements,
        )
        self.assertEqual(
            convert.description.conditional_clauses,
            ordinary.description.conditional_clauses,
        )
        self.assertEqual(
            convert.description.learned_concepts,
            ordinary.description.learned_concepts + 1,
        )
        self.assertEqual(convert.operational, ordinary.operational)

    def test_two_convert_roles_share_one_primitive_without_a_move_base(self) -> None:
        one_convert = evaluate_simplicity(
            comparison_definition("CONVERT", "MOVE")
        )
        two_converts = evaluate_simplicity(
            comparison_definition("CONVERT", "CONVERT")
        )

        self.assertEqual(
            two_converts.to_dict(),
            {
                "structural": {
                    "action_types": 1,
                    "piece_types": 2,
                    "state_variables": 4,
                    "numeric_parameters": 6,
                    "victory_clauses": 2,
                    "exception_clauses": 0,
                    "phases": 1,
                    "action_substeps": 4,
                    "primitive_concepts": 2,
                },
                "description": {
                    "independent_statements": 12,
                    "conditional_clauses": 5,
                    "exception_clauses": 0,
                    "learned_concepts": 8,
                },
                "operational": {
                    "max_action_parameters": 4,
                    "tracked_fields": 5,
                    "initial_legal_actions": 1,
                },
            },
        )

        self.assertEqual(
            two_converts.structural.action_types,
            one_convert.structural.action_types - 1,
        )
        self.assertEqual(
            two_converts.structural.primitive_concepts,
            one_convert.structural.primitive_concepts - 1,
        )
        self.assertEqual(
            two_converts.description.learned_concepts,
            one_convert.description.learned_concepts - 1,
        )
        self.assertEqual(
            two_converts.structural.numeric_parameters,
            one_convert.structural.numeric_parameters,
        )
        self.assertEqual(
            two_converts.structural.action_substeps,
            one_convert.structural.action_substeps,
        )
        self.assertEqual(
            two_converts.description.independent_statements,
            one_convert.description.independent_statements,
        )
        self.assertEqual(
            two_converts.description.conditional_clauses,
            one_convert.description.conditional_clauses,
        )
        self.assertEqual(two_converts.operational, one_convert.operational)

    def test_each_convert_vector_contributes_two_numeric_parameters(self) -> None:
        one_vector = evaluate_simplicity(
            comparison_definition("PUSH", "CONVERT", [[0, -1]])
        ).to_dict()
        two_vectors = evaluate_simplicity(
            comparison_definition("PUSH", "CONVERT", [[0, -1], [1, 0]])
        ).to_dict()

        expected = copy.deepcopy(one_vector)
        expected["structural"]["numeric_parameters"] += 2
        self.assertEqual(two_vectors, expected)

    def test_convert_relaxes_reach_and_connection_when_a_goal_actor_exists(self) -> None:
        for goal_kind in ("REACH_EDGE", "CONNECT_EDGES"):
            with self.subTest(goal_kind=goal_kind):
                report = analyze_definition(
                    convert_static_definition(
                        goal_kind,
                        actor=True,
                        matching_piece=True,
                    )
                )
                self.assertNotIn(
                    FailureCode.UNREACHABLE_WIN_CONDITION,
                    report.failure_codes,
                )

    def test_convert_relaxation_requires_an_actor_and_matching_goal_piece(self) -> None:
        for goal_kind in ("REACH_EDGE", "CONNECT_EDGES"):
            for actor, matching_piece in ((False, True), (True, False)):
                with self.subTest(
                    goal_kind=goal_kind,
                    actor=actor,
                    matching_piece=matching_piece,
                ):
                    report = analyze_definition(
                        convert_static_definition(
                            goal_kind,
                            actor=actor,
                            matching_piece=matching_piece,
                        )
                    )
                    self.assertIn(
                        FailureCode.UNREACHABLE_WIN_CONDITION,
                        report.failure_codes,
                    )

    def test_push_swap_hop_goldens_are_unchanged(self) -> None:
        expected_dsl_hashes = {
            "PUSH": "e81605ebb3709c1b97069b141ea2ee70e58c3c74130f0403293493e0a9fe1c3f",
            "SWAP": "c8dba41bb2e97e5fcc5dd119a415da2ee74b68e196f38c70d2aada292de73ba2",
            "HOP": "4ad5598c0b5a15cb24fa9b79747634c7a8ea87fa909f40cb23ad2181528015ce",
        }
        expected_d4_hashes = {
            "PUSH": "656981777ffbe417479a6cd6b84eddaeea199dd18a57e41e99f48355535ef802",
            "SWAP": "aae4af10c105a9e498277a0df32024f3bdbd4baf91ef95368ba2d9985030c4b0",
            "HOP": "94d8d41c58a35f6882846ebefe0fb7a19ab2787238819e83e61773fc54266b95",
        }
        expected_report = {
            "structural": {
                "action_types": 2,
                "piece_types": 2,
                "state_variables": 4,
                "numeric_parameters": 10,
                "victory_clauses": 2,
                "exception_clauses": 0,
                "phases": 1,
                "action_substeps": 4,
                "primitive_concepts": 5,
            },
            "description": {
                "independent_statements": 13,
                "conditional_clauses": 6,
                "exception_clauses": 0,
                "learned_concepts": 11,
            },
            "operational": {
                "max_action_parameters": 4,
                "tracked_fields": 5,
                "initial_legal_actions": 8,
            },
        }

        for kind in ("PUSH", "SWAP", "HOP"):
            with self.subTest(kind=kind):
                self.assertEqual(
                    definition_hash(special_dsl_definition(kind)),
                    expected_dsl_hashes[kind],
                )
                self.assertEqual(
                    d4_canonical_hash(asymmetric_action_definition(kind)),
                    expected_d4_hashes[kind],
                )
                raw = crossing_definition()
                raw["schema_version"] = 4
                raw["roles"]["B"]["action"]["kind"] = kind
                self.assertEqual(
                    evaluate_simplicity(parse_definition(raw)).to_dict(),
                    expected_report,
                )

    def test_schema_v1_to_v3_d4_and_simplicity_goldens_are_unchanged(self) -> None:
        expected_definition_hashes = {
            1: "1c478ea40b8c950ab23e6eb31d46a21b247a2f44d01adcb7adb418022ea0e465",
            2: "84058248624548bff2a0a7f3289cfeebe9e15854888faf2c2233a1133f279173",
            3: "8eff6699c4baa64cfd20ae3e2e9ba4fe3f5a16c1e2686ca8025fb6ba41fa59eb",
        }
        expected_hashes = {
            1: "fffbc3b49d6c040eb4318597955c140dbbabae9903a35d85132b6d040a1b1a97",
            2: "48b2a77b63f450cac992b24ad8be3354666896cbbd0e7c50805f3be494677ea3",
            3: "e2b589b08d050a679d9eef418c336976011bc541e6ca83f7d95b39da1fedf1d9",
        }
        common = {
            "structural": {
                "action_types": 2,
                "piece_types": 2,
                "state_variables": 4,
                "numeric_parameters": 10,
                "victory_clauses": 2,
                "exception_clauses": 0,
                "phases": 1,
                "action_substeps": 3,
                "primitive_concepts": 4,
            },
            "description": {
                "independent_statements": 9,
                "conditional_clauses": 3,
                "exception_clauses": 0,
                "learned_concepts": 8,
            },
            "operational": {
                "max_action_parameters": 4,
                "tracked_fields": 5,
                "initial_legal_actions": 8,
            },
        }

        for schema_version in (1, 2, 3):
            with self.subTest(schema_version=schema_version):
                definition = legacy_definition(schema_version)
                expected_report = json.loads(json.dumps(common))
                if schema_version == 3:
                    expected_report["structural"]["primitive_concepts"] = 5
                    expected_report["description"]["independent_statements"] = 10
                    expected_report["description"]["conditional_clauses"] = 4
                    expected_report["description"]["learned_concepts"] = 9
                self.assertEqual(
                    definition_hash(definition),
                    expected_definition_hashes[schema_version],
                )
                self.assertEqual(
                    d4_canonical_hash(definition),
                    expected_hashes[schema_version],
                )
                self.assertEqual(
                    evaluate_simplicity(definition).to_dict(),
                    expected_report,
                )


if __name__ == "__main__":
    unittest.main()
