import json
import unittest

from parity_forge.analysis import FailureCode, analyze_definition
from parity_forge.asymmetry import evaluate_asymmetry
from parity_forge.dsl import ActionKind, Player, definition_hash, parse_definition
from parity_forge.simplicity import evaluate_simplicity
from parity_forge.symmetry import (
    D4_TRANSFORMS,
    d4_canonical_hash,
    mechanical_json,
    transform_definition,
)

from tests.support import crossing_definition


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


def schema4_movement_pair(first_kind, second_kind):
    raw = crossing_definition()
    raw["schema_version"] = 4
    raw["initial_pieces"].append(
        {"owner": "A", "piece": "seed", "position": [1, 1]}
    )
    raw["roles"]["A"]["action"] = {
        "kind": first_kind,
        "piece": "seed",
        "vectors": [[0, -1], [0, 1]],
    }
    raw["roles"]["B"]["action"]["kind"] = second_kind
    return parse_definition(raw)


def special_dsl_definition(kind):
    raw = crossing_definition()
    raw["schema_version"] = 4
    raw["name"] = {
        "PUSH": "Pushing Crossing",
        "SWAP": "Swapping Crossing",
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


class Schema4HopIntegrationTests(unittest.TestCase):
    def test_d4_transforms_hop_vectors_and_preserves_eight_member_orbit(self) -> None:
        definition = asymmetric_action_definition("HOP")
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
        self.assertEqual(
            baseline,
            "94d8d41c58a35f6882846ebefe0fb7a19ab2787238819e83e61773fc54266b95",
        )
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
                self.assertEqual(transformed.schema_version, 4)
                self.assertIs(
                    transformed.role(Player.B).action.kind,
                    ActionKind.HOP,
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

        payload = json.loads(mechanical_json(definition))
        self.assertEqual(payload["schema_version"], 4)
        self.assertEqual(payload["roles"]["B"]["action"]["kind"], "HOP")

    def test_static_and_asymmetry_treat_hop_as_movement(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["roles"]["B"]["action"]["kind"] = "HOP"
        definition = parse_definition(raw)

        static = analyze_definition(definition)
        asymmetry = evaluate_asymmetry(definition)

        self.assertNotIn(
            FailureCode.UNREACHABLE_WIN_CONDITION,
            static.failure_codes,
        )
        self.assertTrue(asymmetry.action_primitives_differ)
        self.assertTrue(asymmetry.mobility_rights_differ)
        self.assertTrue(asymmetry.qualifies)

    def test_hop_adds_move_based_special_cost_within_schema_v4(self) -> None:
        ordinary = evaluate_simplicity(schema4_movement_pair("PUSH", "MOVE"))
        hop = evaluate_simplicity(schema4_movement_pair("PUSH", "HOP"))

        self.assertEqual(hop.structural.action_types, ordinary.structural.action_types)
        self.assertEqual(hop.structural.piece_types, ordinary.structural.piece_types)
        self.assertEqual(
            hop.structural.numeric_parameters,
            ordinary.structural.numeric_parameters,
        )
        self.assertEqual(
            hop.structural.action_substeps,
            ordinary.structural.action_substeps + 1,
        )
        self.assertEqual(
            hop.structural.primitive_concepts,
            ordinary.structural.primitive_concepts + 1,
        )
        self.assertEqual(
            hop.description.independent_statements,
            ordinary.description.independent_statements + 1,
        )
        self.assertEqual(
            hop.description.conditional_clauses,
            ordinary.description.conditional_clauses + 1,
        )
        self.assertEqual(
            hop.description.learned_concepts,
            ordinary.description.learned_concepts + 1,
        )
        self.assertEqual(hop.operational, ordinary.operational)

    def test_each_hop_role_adds_cost_without_relearning_shared_primitive(self) -> None:
        one_hop = evaluate_simplicity(schema4_movement_pair("HOP", "MOVE"))
        two_hops = evaluate_simplicity(schema4_movement_pair("HOP", "HOP"))

        self.assertEqual(
            two_hops.structural.action_substeps,
            one_hop.structural.action_substeps + 1,
        )
        self.assertEqual(
            two_hops.structural.primitive_concepts,
            one_hop.structural.primitive_concepts,
        )
        self.assertEqual(
            two_hops.description.independent_statements,
            one_hop.description.independent_statements + 1,
        )
        self.assertEqual(
            two_hops.description.conditional_clauses,
            one_hop.description.conditional_clauses + 1,
        )
        self.assertEqual(
            two_hops.description.learned_concepts,
            one_hop.description.learned_concepts,
        )
        self.assertEqual(two_hops.operational, one_hop.operational)

    def test_push_and_swap_dsl_d4_and_simplicity_goldens_are_unchanged(self) -> None:
        expected_dsl_hashes = {
            "PUSH": "e81605ebb3709c1b97069b141ea2ee70e58c3c74130f0403293493e0a9fe1c3f",
            "SWAP": "c8dba41bb2e97e5fcc5dd119a415da2ee74b68e196f38c70d2aada292de73ba2",
        }
        expected_d4_hashes = {
            "PUSH": "656981777ffbe417479a6cd6b84eddaeea199dd18a57e41e99f48355535ef802",
            "SWAP": "aae4af10c105a9e498277a0df32024f3bdbd4baf91ef95368ba2d9985030c4b0",
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

        for kind in ("PUSH", "SWAP"):
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
                    d4_canonical_hash(definition),
                    expected_hashes[schema_version],
                )
                self.assertEqual(
                    evaluate_simplicity(definition).to_dict(),
                    expected_report,
                )


if __name__ == "__main__":
    unittest.main()
