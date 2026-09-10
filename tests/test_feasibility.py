import ast
import copy
import hashlib
import inspect
import itertools
import math
import unittest
from collections import Counter
from dataclasses import FrozenInstanceError
from pathlib import Path

import parity_forge.feasibility as feasibility_module
from parity_forge.dsl import (
    ActionKind,
    GoalKind,
    Player,
    canonical_json,
    definition_hash,
)
from parity_forge.family import (
    ActionPrimitive,
    GoalPrimitive,
    canonical_family_signature_json,
)
from parity_forge.feasibility import (
    FEASIBILITY_DOMAIN_VERSION,
    FEASIBILITY_INPUT_COUNT_V1,
    FEASIBILITY_INPUT_VERSION,
    FeasibilityInputV1,
    GoalFrameV1,
    VectorProfileV1,
    build_derivation_witness_v1,
    build_feasibility_domain_v1,
    build_state_work_proof_v1,
    compile_feasibility_definition_v1,
    enumerate_feasibility_inputs_v1,
    feasibility_domain_hash_v1,
    parse_feasibility_input_v1,
    project_definition_family_signature_v1,
    provisional_case_input_hash_v1,
    provisional_family_signature_v1,
    validate_derivation_witness_v1,
    validate_provisional_domain_descriptor_v1,
    validate_state_work_proof_v1,
)
from parity_forge.symmetry import D4_TRANSFORMS, d4_canonical_hash, transform_definition


ORTHOGONAL_4 = ((-1, 0), (0, -1), (0, 1), (1, 0))
KING_8 = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)

FAMILY_EXPECTATIONS = {
    "push-hop-race-v1": (
        ActionPrimitive.PUSH,
        GoalPrimitive.REACH_EDGE,
        ActionPrimitive.HOP,
        GoalPrimitive.REACH_EDGE,
        GoalFrameV1.REACH_REACH_SAME,
    ),
    "swap-hop-network-v1": (
        ActionPrimitive.SWAP,
        GoalPrimitive.CONNECT_EDGES,
        ActionPrimitive.HOP,
        GoalPrimitive.REACH_EDGE,
        GoalFrameV1.CONNECT_REACH_ALIGNED,
    ),
    "convert-push-front-v1": (
        ActionPrimitive.CONVERT,
        GoalPrimitive.CONNECT_EDGES,
        ActionPrimitive.PUSH,
        GoalPrimitive.REACH_EDGE,
        GoalFrameV1.CONNECT_REACH_PERPENDICULAR,
    ),
    "capture-hop-hunt-v1": (
        ActionPrimitive.MOVE_CAPTURE,
        GoalPrimitive.ELIMINATE,
        ActionPrimitive.HOP,
        GoalPrimitive.REACH_EDGE,
        GoalFrameV1.ELIMINATE_REACH,
    ),
    "convert-capture-duel-v1": (
        ActionPrimitive.CONVERT,
        GoalPrimitive.ELIMINATE,
        ActionPrimitive.MOVE_CAPTURE,
        GoalPrimitive.ELIMINATE,
        GoalFrameV1.ELIMINATE_ELIMINATE,
    ),
    "push-swap-networks-v1": (
        ActionPrimitive.PUSH,
        GoalPrimitive.CONNECT_EDGES,
        ActionPrimitive.SWAP,
        GoalPrimitive.CONNECT_EDGES,
        GoalFrameV1.CONNECT_CONNECT_PERPENDICULAR,
    ),
}


def case_mapping(
    family_id="push-hop-race-v1",
    goal_frame="REACH_REACH_SAME",
    *,
    first_player="A",
    a_profile="ORTHOGONAL_4",
    b_profile="KING_8",
    a_positions=None,
    b_positions=None,
):
    return {
        "case_input_version": 1,
        "dsl_schema_version": 4,
        "family_id": family_id,
        "board_size": 3,
        "first_player": first_player,
        "max_plies": 18,
        "vector_profiles": {"A": a_profile, "B": b_profile},
        "goal_frame": goal_frame,
        "initial_positions": {
            "A": [[0, 0], [1, 1]] if a_positions is None else a_positions,
            "B": [[0, 2], [2, 0]] if b_positions is None else b_positions,
        },
    }


def representative_cases():
    for family_id, expectation in FAMILY_EXPECTATIONS.items():
        yield parse_feasibility_input_v1(
            case_mapping(
                family_id,
                expectation[4].value,
                a_profile="ORTHOGONAL_4",
                b_profile="KING_8",
            )
        )


def nested_keys(value):
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from nested_keys(child)
    elif type(value) is list:
        for child in value:
            yield from nested_keys(child)


class FeasibilityDomainTests(unittest.TestCase):
    def test_exact_domain_combinatorics_are_independently_reconstructable(self):
        setup_counts = (
            math.comb(9, 2) * math.comb(7, 2),
            math.comb(9, 3) * math.comb(6, 3),
        )
        self.assertEqual(setup_counts, (756, 1_680))
        self.assertEqual(sum(setup_counts), 2_436)

        descriptor = build_feasibility_domain_v1()
        self.assertEqual(FEASIBILITY_DOMAIN_VERSION, 1)
        self.assertEqual(FEASIBILITY_INPUT_VERSION, 1)
        self.assertEqual(FEASIBILITY_INPUT_COUNT_V1, 214_368)
        self.assertEqual(
            descriptor["combinatorics"],
            {
                "board_cell_count": 9,
                "setup_arrangement_count": 2_436,
                "goal_frame_count": 11,
                "ordered_vector_profile_pair_count": 4,
                "first_player_count": 2,
                "raw_case_input_count": 214_368,
            },
        )
        self.assertEqual(2_436 * 11 * 4 * 2, 214_368)

    def test_complete_enumeration_has_fixed_order_endpoints_and_family_counts(self):
        expected_counts = {
            "push-hop-race-v1": 58_464,
            "swap-hop-network-v1": 38_976,
            "convert-push-front-v1": 38_976,
            "capture-hop-hunt-v1": 19_488,
            "convert-capture-duel-v1": 19_488,
            "push-swap-networks-v1": 38_976,
        }
        observed = Counter()
        case_hashes = set()
        ordered_root = hashlib.sha256(
            b"parity-forge:plan0012:ordered-case-inputs:v1\0"
        )
        first = None
        last = None
        count = 0
        for case in enumerate_feasibility_inputs_v1():
            if first is None:
                first = case
            last = case
            count += 1
            observed[case.family_id] += 1
            case_hash = provisional_case_input_hash_v1(case)
            case_hashes.add(case_hash)
            ordered_root.update(case_hash.encode("ascii"))
            ordered_root.update(b"\n")

        self.assertEqual(count, 214_368)
        self.assertEqual(len(case_hashes), count)
        self.assertEqual(
            ordered_root.hexdigest(),
            "e3011f74256fe39881eda3636533ec4352f7b4d2c4386e12d775ccc031b6d2e8",
        )
        self.assertEqual(dict(observed), expected_counts)
        self.assertIsNotNone(first)
        self.assertIsNotNone(last)
        self.assertEqual(
            first.to_dict(),
            case_mapping(
                b_profile="ORTHOGONAL_4",
                a_positions=[[0, 0], [0, 1]],
                b_positions=[[0, 2], [1, 0]],
            ),
        )
        self.assertEqual(
            last.to_dict(),
            case_mapping(
                "push-swap-networks-v1",
                "CONNECT_CONNECT_PERPENDICULAR",
                first_player="B",
                a_profile="KING_8",
                b_profile="KING_8",
                a_positions=[[2, 0], [2, 1], [2, 2]],
                b_positions=[[1, 0], [1, 1], [1, 2]],
            ),
        )
        self.assertEqual(next(enumerate_feasibility_inputs_v1()), first)

    def test_domain_descriptor_is_exact_hashed_detached_and_reconstructed(self):
        descriptor = build_feasibility_domain_v1()
        self.assertEqual(
            descriptor["setup_count_pairs"],
            [
                {"A_count": 2, "B_count": 2, "disjoint_arrangement_count": 756},
                {
                    "A_count": 3,
                    "B_count": 3,
                    "disjoint_arrangement_count": 1_680,
                },
            ],
        )
        self.assertEqual(descriptor["first_players"], ["A", "B"])
        self.assertEqual(descriptor["max_plies"], [18])
        self.assertEqual(
            descriptor["vector_profiles"],
            {
                "ORTHOGONAL_4": [list(vector) for vector in ORTHOGONAL_4],
                "KING_8": [list(vector) for vector in KING_8],
            },
        )
        digest = feasibility_domain_hash_v1()
        self.assertEqual(
            digest,
            "3456b5873dadfd177639b4c0d062bad6717d328a7ebee88a71f4294f9a5b0bc5",
        )
        self.assertEqual(digest, feasibility_domain_hash_v1())
        self.assertNotEqual(
            feasibility_domain_hash_v1(),
            hashlib.sha256(
                feasibility_module.canonical_provisional_domain_json_v1().encode(
                    "utf-8"
                )
            ).hexdigest(),
        )

        rebuilt = validate_provisional_domain_descriptor_v1(descriptor)
        self.assertEqual(rebuilt, descriptor)
        self.assertIsNot(rebuilt, descriptor)
        rebuilt["families"][0]["family_id"] = "changed"
        self.assertEqual(
            validate_provisional_domain_descriptor_v1(descriptor), descriptor
        )

        tampered = copy.deepcopy(descriptor)
        tampered["combinatorics"]["raw_case_input_count"] += 1
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_provisional_domain_descriptor_v1(tampered)
        unknown = copy.deepcopy(descriptor)
        unknown["unknown"] = True
        with self.assertRaisesRegex(ValueError, "does not reconstruct"):
            validate_provisional_domain_descriptor_v1(unknown)
        with self.assertRaises(TypeError):
            validate_provisional_domain_descriptor_v1(
                type("DictSubclass", (dict,), {})(descriptor)
            )


class FeasibilityInputBoundaryTests(unittest.TestCase):
    def test_input_roundtrip_is_strict_canonical_and_detached(self):
        source = case_mapping()
        case = parse_feasibility_input_v1(source)
        expected = copy.deepcopy(source)
        source["vector_profiles"]["A"] = "KING_8"
        source["initial_positions"]["A"].reverse()
        self.assertEqual(case.to_dict(), expected)
        self.assertEqual(parse_feasibility_input_v1(case.to_dict()), case)
        self.assertEqual(
            provisional_case_input_hash_v1(case),
            "57e0c6dbb770b06b1c66fc104b854b71911865a8e47069182d267252db52bdbd",
        )
        with self.assertRaises(FrozenInstanceError):
            case.family_id = "changed"

    def test_input_rejects_unknown_missing_nested_and_nonexact_objects(self):
        for mutation in ("unknown", "missing", "nested_unknown", "nested_missing"):
            with self.subTest(mutation=mutation):
                value = case_mapping()
                if mutation == "unknown":
                    value["outcome"] = None
                elif mutation == "missing":
                    del value["board_size"]
                elif mutation == "nested_unknown":
                    value["vector_profiles"]["C"] = "KING_8"
                else:
                    del value["initial_positions"]["B"]
                with self.assertRaises((TypeError, ValueError)):
                    parse_feasibility_input_v1(value)

        with self.assertRaises(TypeError):
            parse_feasibility_input_v1(type("DictSubclass", (dict,), {})(case_mapping()))
        nested_subclass = case_mapping()
        nested_subclass["vector_profiles"] = type(
            "NestedDictSubclass", (dict,), {}
        )(nested_subclass["vector_profiles"])
        with self.assertRaises(TypeError):
            parse_feasibility_input_v1(nested_subclass)

    def test_input_rejects_type_order_count_bounds_and_overlap_violations(self):
        invalid_values = []
        for field in (
            "case_input_version",
            "dsl_schema_version",
            "board_size",
            "max_plies",
        ):
            value = case_mapping()
            value[field] = True
            invalid_values.append(value)

        value = case_mapping()
        value["first_player"] = Player.A
        invalid_values.append(value)
        value = case_mapping()
        value["vector_profiles"]["A"] = VectorProfileV1.ORTHOGONAL_4
        invalid_values.append(value)
        value = case_mapping()
        value["initial_positions"]["A"] = [[1, 1], [0, 0]]
        invalid_values.append(value)
        value = case_mapping()
        value["initial_positions"]["A"] = [[0, 0], [0, 0]]
        invalid_values.append(value)
        value = case_mapping()
        value["initial_positions"]["A"] = [[0, 0], [3, 0]]
        invalid_values.append(value)
        value = case_mapping()
        value["initial_positions"]["A"] = [[0, 0], [True, 1]]
        invalid_values.append(value)
        value = case_mapping()
        value["initial_positions"]["A"] = [[0, 0]]
        invalid_values.append(value)
        value = case_mapping()
        value["initial_positions"]["B"] = [[0, 0], [2, 0]]
        invalid_values.append(value)
        value = case_mapping()
        value["family_id"] = "unknown-family"
        invalid_values.append(value)
        value = case_mapping()
        value["goal_frame"] = "ELIMINATE_ELIMINATE"
        invalid_values.append(value)

        for index, value in enumerate(invalid_values):
            with self.subTest(index=index):
                with self.assertRaises((TypeError, ValueError)):
                    parse_feasibility_input_v1(value)

    def test_direct_input_construction_and_hidden_field_mutation_fail_closed(self):
        case = parse_feasibility_input_v1(case_mapping())
        kwargs = dict(vars(case))
        kwargs["case_input_version"] = True
        with self.assertRaises(TypeError):
            FeasibilityInputV1(**kwargs)
        kwargs = dict(vars(case))
        kwargs["a_positions"] = [list(position) for position in case.a_positions]
        with self.assertRaises(TypeError):
            FeasibilityInputV1(**kwargs)

        forged = parse_feasibility_input_v1(case_mapping())
        object.__setattr__(forged, "hidden_result", "A_WIN")
        for operation in (
            forged.to_dict,
            lambda: provisional_case_input_hash_v1(forged),
            lambda: compile_feasibility_definition_v1(forged),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises((TypeError, ValueError)):
                    operation()


class FeasibilityCompilerTests(unittest.TestCase):
    def test_six_family_compilation_and_projection_are_exact(self):
        for case in representative_cases():
            with self.subTest(family_id=case.family_id):
                expected = FAMILY_EXPECTATIONS[case.family_id]
                definition = compile_feasibility_definition_v1(case)
                signature = provisional_family_signature_v1(case.family_id)
                projected = project_definition_family_signature_v1(definition)

                self.assertEqual(definition.schema_version, 4)
                self.assertEqual(definition.board_size, 3)
                self.assertEqual(definition.max_plies, 18)
                self.assertIs(definition.first_player, Player.A)
                self.assertTrue(
                    definition.name.startswith("pf12-{}-".format(case.family_id))
                )
                self.assertEqual(len(definition.name.rsplit("-", 1)[1]), 20)
                self.assertEqual(
                    canonical_family_signature_json(projected),
                    canonical_family_signature_json(signature),
                )
                self.assertIs(signature.role_a.action_primitive, expected[0])
                self.assertIs(signature.role_a.goal_primitive, expected[1])
                self.assertIs(signature.role_b.action_primitive, expected[2])
                self.assertIs(signature.role_b.goal_primitive, expected[3])
                self.assertIs(
                    definition.role(Player.A).action.kind,
                    ActionKind(expected[0].value),
                )
                self.assertIs(
                    definition.role(Player.B).action.kind,
                    ActionKind(expected[2].value),
                )
                self.assertIs(
                    definition.role(Player.A).goal.kind,
                    GoalKind(expected[1].value),
                )
                self.assertIs(
                    definition.role(Player.B).goal.kind,
                    GoalKind(expected[3].value),
                )
                self.assertEqual(
                    [(piece.owner.value, piece.piece) for piece in definition.initial_pieces],
                    [("A", "a"), ("B", "b"), ("A", "a"), ("B", "b")],
                )
                self.assertEqual(canonical_json(definition), canonical_json(
                    compile_feasibility_definition_v1(case.to_dict())
                ))

    def test_every_goal_frame_maps_to_its_exact_ordered_role_goals(self):
        expected = {
            ("push-hop-race-v1", "REACH_REACH_SAME"): (
                {"kind": "REACH_EDGE", "piece": "a", "edge": "TOP"},
                {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"},
            ),
            ("push-hop-race-v1", "REACH_REACH_OPPOSITE"): (
                {"kind": "REACH_EDGE", "piece": "a", "edge": "TOP"},
                {"kind": "REACH_EDGE", "piece": "b", "edge": "BOTTOM"},
            ),
            ("push-hop-race-v1", "REACH_REACH_ADJACENT"): (
                {"kind": "REACH_EDGE", "piece": "a", "edge": "TOP"},
                {"kind": "REACH_EDGE", "piece": "b", "edge": "RIGHT"},
            ),
            ("swap-hop-network-v1", "CONNECT_REACH_ALIGNED"): (
                {"kind": "CONNECT_EDGES", "piece": "a", "edges": ["BOTTOM", "TOP"]},
                {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"},
            ),
            ("swap-hop-network-v1", "CONNECT_REACH_PERPENDICULAR"): (
                {"kind": "CONNECT_EDGES", "piece": "a", "edges": ["BOTTOM", "TOP"]},
                {"kind": "REACH_EDGE", "piece": "b", "edge": "RIGHT"},
            ),
            ("convert-push-front-v1", "CONNECT_REACH_ALIGNED"): (
                {"kind": "CONNECT_EDGES", "piece": "a", "edges": ["BOTTOM", "TOP"]},
                {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"},
            ),
            ("convert-push-front-v1", "CONNECT_REACH_PERPENDICULAR"): (
                {"kind": "CONNECT_EDGES", "piece": "a", "edges": ["BOTTOM", "TOP"]},
                {"kind": "REACH_EDGE", "piece": "b", "edge": "RIGHT"},
            ),
            ("capture-hop-hunt-v1", "ELIMINATE_REACH"): (
                {"kind": "ELIMINATE", "piece": "b"},
                {"kind": "REACH_EDGE", "piece": "b", "edge": "TOP"},
            ),
            ("convert-capture-duel-v1", "ELIMINATE_ELIMINATE"): (
                {"kind": "ELIMINATE", "piece": "b"},
                {"kind": "ELIMINATE", "piece": "a"},
            ),
            ("push-swap-networks-v1", "CONNECT_CONNECT_SAME_AXIS"): (
                {"kind": "CONNECT_EDGES", "piece": "a", "edges": ["BOTTOM", "TOP"]},
                {"kind": "CONNECT_EDGES", "piece": "b", "edges": ["BOTTOM", "TOP"]},
            ),
            ("push-swap-networks-v1", "CONNECT_CONNECT_PERPENDICULAR"): (
                {"kind": "CONNECT_EDGES", "piece": "a", "edges": ["BOTTOM", "TOP"]},
                {"kind": "CONNECT_EDGES", "piece": "b", "edges": ["LEFT", "RIGHT"]},
            ),
        }
        self.assertEqual(len(expected), 11)
        for (family_id, frame), role_goals in expected.items():
            with self.subTest(family_id=family_id, frame=frame):
                definition = compile_feasibility_definition_v1(
                    case_mapping(family_id, frame)
                )
                self.assertEqual(definition.role(Player.A).goal.to_dict(), role_goals[0])
                self.assertEqual(definition.role(Player.B).goal.to_dict(), role_goals[1])

    def test_vector_profiles_are_mapped_independently_to_a_and_b(self):
        expected_vectors = {
            "ORTHOGONAL_4": ORTHOGONAL_4,
            "KING_8": KING_8,
        }
        for a_profile, b_profile in itertools.product(expected_vectors, repeat=2):
            with self.subTest(A=a_profile, B=b_profile):
                definition = compile_feasibility_definition_v1(
                    case_mapping(a_profile=a_profile, b_profile=b_profile)
                )
                self.assertEqual(
                    definition.role(Player.A).action.vectors,
                    expected_vectors[a_profile],
                )
                self.assertEqual(
                    definition.role(Player.B).action.vectors,
                    expected_vectors[b_profile],
                )

    def test_compiler_preserves_b_first_and_three_by_three_setup(self):
        definition = compile_feasibility_definition_v1(
            case_mapping(
                "convert-capture-duel-v1",
                "ELIMINATE_ELIMINATE",
                first_player="B",
                a_profile="KING_8",
                b_profile="ORTHOGONAL_4",
                a_positions=[[0, 0], [1, 1], [2, 2]],
                b_positions=[[0, 2], [1, 0], [2, 1]],
            )
        )
        self.assertIs(definition.first_player, Player.B)
        self.assertEqual(
            [piece.to_dict() for piece in definition.initial_pieces],
            [
                {"owner": "A", "piece": "a", "position": [0, 0]},
                {"owner": "B", "piece": "b", "position": [0, 2]},
                {"owner": "B", "piece": "b", "position": [1, 0]},
                {"owner": "A", "piece": "a", "position": [1, 1]},
                {"owner": "B", "piece": "b", "position": [2, 1]},
                {"owner": "A", "piece": "a", "position": [2, 2]},
            ],
        )

    def test_six_representatives_have_d4_invariant_identity_and_family_projection(self):
        for case in representative_cases():
            definition = compile_feasibility_definition_v1(case)
            expected_hash = d4_canonical_hash(definition)
            expected_signature = canonical_family_signature_json(
                provisional_family_signature_v1(case.family_id)
            )
            for transform in D4_TRANSFORMS:
                with self.subTest(family_id=case.family_id, transform=transform):
                    transformed = transform_definition(definition, transform)
                    self.assertEqual(d4_canonical_hash(transformed), expected_hash)
                    self.assertEqual(
                        canonical_family_signature_json(
                            project_definition_family_signature_v1(transformed)
                        ),
                        expected_signature,
                    )


class FeasibilityProofAndWitnessTests(unittest.TestCase):
    def test_state_work_proof_reconstructs_combinatorial_formulas_for_both_setups(self):
        classes = {
            "push-hop-race-v1": "FIXED_COUNTS",
            "swap-hop-network-v1": "FIXED_COUNTS",
            "convert-push-front-v1": "A_CONVERTS_B_COUNTS",
            "capture-hop-hunt-v1": "A_CAPTURES_B_COUNTS",
            "convert-capture-duel-v1": "A_CONVERTS_B_B_CAPTURES_A_COUNTS",
            "push-swap-networks-v1": "FIXED_COUNTS",
        }
        expected_state_bounds = {
            "FIXED_COUNTS": {2: 14_364, 3: 31_920},
            "A_CONVERTS_B_COUNTS": {2: 26_334, 3: 67_032},
            "A_CAPTURES_B_COUNTS": {2: 19_836, 3: 67_032},
            "A_CONVERTS_B_B_CAPTURES_A_COUNTS": {2: 40_603, 3: 181_051},
        }

        def count_classes(bound_class, count):
            if bound_class == "FIXED_COUNTS":
                return ((count, count),)
            if bound_class == "A_CONVERTS_B_COUNTS":
                return tuple(
                    (a_count, 2 * count - a_count)
                    for a_count in range(count, 2 * count + 1)
                )
            if bound_class == "A_CAPTURES_B_COUNTS":
                return tuple((count, b_count) for b_count in range(count + 1))
            return tuple(
                (a_count, b_count)
                for b_count in range(count + 1)
                for a_count in range(2 * count - b_count + 1)
            )

        for family_id, expectation in FAMILY_EXPECTATIONS.items():
            for piece_count in (2, 3):
                with self.subTest(family_id=family_id, piece_count=piece_count):
                    positions_a = [[0, column] for column in range(piece_count)]
                    positions_b = [[2, column] for column in range(piece_count)]
                    case = parse_feasibility_input_v1(
                        case_mapping(
                            family_id,
                            expectation[4].value,
                            a_positions=positions_a,
                            b_positions=positions_b,
                            a_profile="ORTHOGONAL_4",
                            b_profile="KING_8",
                        )
                    )
                    proof = build_state_work_proof_v1(case)
                    bound_class = classes[family_id]
                    expected_layers = []
                    for a_count, b_count in count_classes(
                        bound_class, piece_count
                    ):
                        arrangements = math.comb(9, a_count) * math.comb(
                            9 - a_count, b_count
                        )
                        expected_layers.append(
                            {
                                "A_count": a_count,
                                "B_count": b_count,
                                "occupied_count": a_count + b_count,
                                "board_configuration_upper_bound": arrangements,
                            }
                        )
                    expected_board_bound = sum(
                        item["board_configuration_upper_bound"]
                        for item in expected_layers
                    )
                    expected_state_bound = expected_state_bounds[bound_class][
                        piece_count
                    ]
                    maximum_a = (
                        2 * piece_count
                        if bound_class
                        in (
                            "A_CONVERTS_B_COUNTS",
                            "A_CONVERTS_B_B_CAPTURES_A_COUNTS",
                        )
                        else piece_count
                    )
                    candidate_bounds = {
                        "A": maximum_a * 4,
                        "B": piece_count * 8,
                    }

                    self.assertEqual(proof["state_bound_class"], bound_class)
                    self.assertEqual(
                        proof["per_role_initial_piece_count"], piece_count
                    )
                    self.assertEqual(
                        proof["occupancy_layer_bounds"], expected_layers
                    )
                    self.assertEqual(
                        proof["board_configuration_upper_bound"],
                        expected_board_bound,
                    )
                    self.assertEqual(proof["ply_layer_count"], 19)
                    self.assertEqual(proof["to_move_multiplier"], 1)
                    self.assertEqual(
                        proof["structural_state_upper_bound"], expected_state_bound
                    )
                    self.assertEqual(
                        proof["role_vector_counts"], {"A": 4, "B": 8}
                    )
                    self.assertEqual(
                        proof["maximum_role_actor_counts"],
                        {"A": maximum_a, "B": piece_count},
                    )
                    self.assertEqual(
                        proof["role_action_candidate_upper_bounds"],
                        candidate_bounds,
                    )
                    max_candidates = max(candidate_bounds.values())
                    self.assertEqual(
                        proof["max_action_candidates_per_state"], max_candidates
                    )
                    self.assertEqual(
                        proof["state_action_candidate_evaluation_upper_bound"],
                        expected_state_bound * max_candidates,
                    )
                    self.assertEqual(
                        validate_state_work_proof_v1(proof, case), proof
                    )

    def test_state_work_proof_validator_rejects_claim_drift_and_extra_fields(self):
        case = parse_feasibility_input_v1(case_mapping())
        proof = build_state_work_proof_v1(case)
        mutations = []
        for field in (
            "proof_version",
            "board_cells",
            "per_role_initial_piece_count",
            "initial_occupied_count",
            "maximum_occupied_count",
            "board_configuration_upper_bound",
            "ply_layer_count",
            "to_move_multiplier",
            "structural_state_upper_bound",
            "max_action_candidates_per_state",
            "state_action_candidate_evaluation_upper_bound",
        ):
            changed = copy.deepcopy(proof)
            changed[field] += 1
            mutations.append(changed)
        changed = copy.deepcopy(proof)
        changed["reachable_owner_kind_labels"].reverse()
        mutations.append(changed)
        changed = copy.deepcopy(proof)
        changed["state_bound_class"] = "FIXED_COUNTS_CHANGED"
        mutations.append(changed)
        changed = copy.deepcopy(proof)
        changed["occupancy_layer_bounds"][0][
            "board_configuration_upper_bound"
        ] += 1
        mutations.append(changed)
        changed = copy.deepcopy(proof)
        changed["role_vector_counts"]["A"] += 1
        mutations.append(changed)
        changed = copy.deepcopy(proof)
        changed["maximum_role_actor_counts"]["A"] += 1
        mutations.append(changed)
        changed = copy.deepcopy(proof)
        changed["role_action_candidate_upper_bounds"]["B"] += 1
        mutations.append(changed)
        changed = copy.deepcopy(proof)
        changed["outcome"] = None
        mutations.append(changed)

        for index, changed in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    validate_state_work_proof_v1(changed, case)

    def test_derivation_witness_rebuilds_and_binds_every_claim(self):
        case = parse_feasibility_input_v1(case_mapping())
        witness = build_derivation_witness_v1(case)
        self.assertEqual(validate_derivation_witness_v1(witness), witness)
        self.assertEqual(witness["case_input"], case.to_dict())
        self.assertEqual(witness["case_input_hash"], provisional_case_input_hash_v1(case))
        self.assertEqual(witness["domain_hash"], feasibility_domain_hash_v1())
        self.assertEqual(
            witness["state_work_proof"], build_state_work_proof_v1(case)
        )
        self.assertEqual(
            definition_hash(compile_feasibility_definition_v1(case)),
            "efbf085a59f92bd71a1c5c04dcf345996d84b9b2a356a03db827a123b9ccbd7c",
        )
        self.assertEqual(
            witness["d4_canonical_hash"],
            "0af18dbfa50d462ab76275474ae833132d06f66e319a1f482ec9bc6944570af8",
        )
        self.assertEqual(
            witness["witness_digest"],
            "9981301a75b7b7d030d661916f71df13209ce44d19765921227edf54ee8d9263",
        )

        mutations = {}
        for field in witness:
            changed = copy.deepcopy(witness)
            if field == "witness_version":
                changed[field] += 1
            elif field == "case_input":
                changed[field]["first_player"] = "B"
            elif field == "family_signature":
                changed[field]["signature_version"] += 1
            elif field == "definition":
                changed[field]["name"] += "-changed"
            elif field == "state_work_proof":
                changed[field]["structural_state_upper_bound"] += 1
            else:
                changed[field] = "0" * 64
            mutations[field] = changed

        self.assertEqual(set(mutations), set(witness))
        for field, changed in mutations.items():
            with self.subTest(field=field):
                with self.assertRaises((TypeError, ValueError)):
                    validate_derivation_witness_v1(changed)

        unknown = copy.deepcopy(witness)
        unknown["result"] = "A_WIN"
        with self.assertRaisesRegex(ValueError, "unknown"):
            validate_derivation_witness_v1(unknown)
        missing = copy.deepcopy(witness)
        del missing["definition_hash"]
        with self.assertRaisesRegex(ValueError, "missing"):
            validate_derivation_witness_v1(missing)

    def test_witness_validation_returns_detached_data(self):
        witness = build_derivation_witness_v1(case_mapping())
        validated = validate_derivation_witness_v1(witness)
        validated["definition"]["name"] = "changed"
        self.assertNotEqual(validated, witness)
        self.assertEqual(validate_derivation_witness_v1(witness), witness)


class FeasibilityPurityTests(unittest.TestCase):
    def test_module_imports_only_the_allowed_project_layers(self):
        source_path = Path(inspect.getsourcefile(feasibility_module))
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        project_imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    project_imports.add(node.module)
                elif node.module and node.module.startswith("parity_forge"):
                    project_imports.add(node.module.split(".", 1)[-1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("parity_forge"):
                        project_imports.add(alias.name.split(".", 1)[-1])
        self.assertEqual(project_imports, {"dsl", "family", "symmetry"})
        self.assertTrue(
            project_imports.isdisjoint(
                {"engine", "agents", "solver", "play", "agency"}
            )
        )

    def test_module_has_no_gameplay_or_outcome_computation_calls(self):
        source_path = Path(inspect.getsourcefile(feasibility_module))
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        forbidden_calls = {
            "apply_action",
            "goal_satisfied",
            "initial_state",
            "legal_actions",
            "play_game",
            "replay",
            "solve",
            "solve_exact",
        }
        observed = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                observed.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                observed.add(node.func.attr)
        self.assertTrue(observed.isdisjoint(forbidden_calls))

    def test_public_artifacts_contain_no_result_or_outcome_fields(self):
        case = parse_feasibility_input_v1(case_mapping())
        values = (
            build_feasibility_domain_v1(),
            case.to_dict(),
            compile_feasibility_definition_v1(case).to_dict(),
            build_state_work_proof_v1(case),
            build_derivation_witness_v1(case),
        )
        forbidden = {"outcome", "outcomes", "result", "results", "winner", "winners"}
        for value in values:
            with self.subTest(value_type=type(value).__name__):
                keys = {key.lower() for key in nested_keys(value)}
                self.assertTrue(keys.isdisjoint(forbidden))
                self.assertFalse(any("outcome" in key or "winner" in key for key in keys))


if __name__ == "__main__":
    unittest.main()
