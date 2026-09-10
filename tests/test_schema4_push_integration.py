import json
import unittest

from parity_forge.analysis import FailureCode, analyze_definition
from parity_forge.asymmetry import evaluate_asymmetry
from parity_forge.dsl import (
    ActionKind,
    DefinitionError,
    Player,
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


def push_definition():
    raw = crossing_definition()
    raw["schema_version"] = 4
    raw["name"] = "Asymmetric push D4 fixture"
    raw["board_size"] = 5
    raw["max_plies"] = 15
    raw["initial_pieces"][0]["position"] = [4, 1]
    raw["roles"]["B"]["action"]["kind"] = "PUSH"
    raw["roles"]["B"]["action"]["vectors"] = [
        [-1, -1],
        [-1, 0],
        [0, 1],
    ]
    return parse_definition(raw)


def legacy_definition(schema_version):
    raw = crossing_definition()
    raw["schema_version"] = schema_version
    if schema_version == 2:
        raw["terminal_policy"] = {"no_legal_action": "DRAW"}
    elif schema_version == 3:
        raw["roles"]["B"]["action"]["kind"] = "MOVE_CAPTURE"
    return parse_definition(raw)


def schema4_push_pair(second_kind):
    raw = crossing_definition()
    raw["schema_version"] = 4
    raw["initial_pieces"].append(
        {"owner": "A", "piece": "seed", "position": [1, 1]}
    )
    raw["roles"]["A"]["action"] = {
        "kind": "PUSH",
        "piece": "seed",
        "vectors": [[0, -1], [0, 1]],
    }
    raw["roles"]["B"]["action"]["kind"] = second_kind
    return parse_definition(raw)


class Schema4PushIntegrationTests(unittest.TestCase):
    def test_d4_transforms_push_vectors_and_preserves_v4_identity(self) -> None:
        definition = push_definition()
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
            "656981777ffbe417479a6cd6b84eddaeea199dd18a57e41e99f48355535ef802",
        )

        self.assertNotEqual(
            definition_hash(definition),
            definition_hash(transform_definition(definition, "R90")),
        )
        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(definition, transform)
                self.assertEqual(transformed.schema_version, 4)
                self.assertIs(
                    transformed.role(Player.B).action.kind,
                    ActionKind.PUSH,
                )
                self.assertEqual(
                    transformed.role(Player.B).action.vectors,
                    expected_vectors[transform],
                )
                self.assertEqual(d4_canonical_hash(transformed), baseline)

        payload = json.loads(mechanical_json(definition))
        self.assertEqual(payload["schema_version"], 4)
        self.assertEqual(payload["roles"]["B"]["action"]["kind"], "PUSH")

    def test_d4_boundaries_reject_forged_or_mutated_definitions(self) -> None:
        definition = push_definition()
        role_b = definition.role(Player.B)
        object.__setattr__(
            role_b.action,
            "vectors",
            tuple(reversed(role_b.action.vectors)),
        )
        for operation in (
            mechanical_json,
            d4_canonical_hash,
            lambda value: transform_definition(value, "I"),
        ):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(DefinitionError, "parser-normalized"):
                    operation(definition)

        class FakeDefinition:
            board_size = 5

            def to_dict(self):
                return push_definition().to_dict()

        with self.assertRaises(TypeError):
            d4_canonical_hash(FakeDefinition())  # type: ignore[arg-type]

    def test_push_simplicity_counts_step_and_conditional_displacement(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["roles"]["B"]["action"]["kind"] = "PUSH"
        push = evaluate_simplicity(parse_definition(raw))
        ordinary = evaluate_simplicity(legacy_definition(1))

        self.assertEqual(push.structural.action_types, ordinary.structural.action_types)
        self.assertEqual(push.structural.piece_types, ordinary.structural.piece_types)
        self.assertEqual(
            push.structural.numeric_parameters,
            ordinary.structural.numeric_parameters,
        )
        self.assertEqual(
            push.structural.action_substeps,
            ordinary.structural.action_substeps + 1,
        )
        self.assertEqual(
            push.structural.primitive_concepts,
            ordinary.structural.primitive_concepts + 1,
        )
        self.assertEqual(
            push.description.conditional_clauses,
            ordinary.description.conditional_clauses + 3,
        )
        self.assertEqual(
            push.description.learned_concepts,
            ordinary.description.learned_concepts + 3,
        )
        self.assertEqual(
            push.description.independent_statements,
            ordinary.description.independent_statements + 4,
        )
        self.assertEqual(push.operational, ordinary.operational)

    def test_each_push_role_adds_its_special_rule_cost_within_schema_v4(self) -> None:
        one_push = evaluate_simplicity(schema4_push_pair("MOVE"))
        two_pushes = evaluate_simplicity(schema4_push_pair("PUSH"))

        self.assertEqual(
            two_pushes.structural.action_substeps,
            one_push.structural.action_substeps + 1,
        )
        self.assertEqual(
            two_pushes.structural.primitive_concepts,
            one_push.structural.primitive_concepts,
        )
        self.assertEqual(
            two_pushes.description.independent_statements,
            one_push.description.independent_statements + 1,
        )
        self.assertEqual(
            two_pushes.description.conditional_clauses,
            one_push.description.conditional_clauses + 1,
        )
        self.assertEqual(
            two_pushes.description.learned_concepts,
            one_push.description.learned_concepts,
        )
        self.assertEqual(two_pushes.operational, one_push.operational)

    def test_static_and_asymmetry_treat_push_as_movement(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 4
        raw["roles"]["B"]["action"]["kind"] = "PUSH"
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

    def test_schema_v1_to_v3_d4_and_simplicity_golden_vectors_are_unchanged(self) -> None:
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
