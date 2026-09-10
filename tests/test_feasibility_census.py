import ast
import copy
import inspect
import json
import unittest
from itertools import islice
from pathlib import Path

import parity_forge.feasibility_census as census_module
from parity_forge.feasibility import (
    compile_feasibility_definition_v1,
    feasibility_domain_hash_v1,
    parse_feasibility_input_v1,
)
from parity_forge.feasibility_census import (
    FEASIBILITY_CENSUS_EVIDENCE_DIGEST_V1,
    FEASIBILITY_ORDERED_CASE_TO_D4_ROOT_V1,
    FEASIBILITY_SORTED_ELIGIBLE_D4_ROOT_V1,
    build_feasibility_census_v1,
    canonical_feasibility_census_json_v1,
    derive_feasibility_case_descriptor_v1,
    enumerate_feasibility_case_descriptors_v1,
    feasibility_census_hash_v1,
    validate_feasibility_census_v1,
)
from parity_forge.symmetry import D4_TRANSFORMS, transform_definition


ORTHOGONAL_4 = "ORTHOGONAL_4"
KING_8 = "KING_8"


def _case_mapping(
    family_id="push-hop-race-v1",
    goal_frame="REACH_REACH_SAME",
    *,
    first_player="A",
    a_profile=ORTHOGONAL_4,
    b_profile=KING_8,
    a_positions=None,
    b_positions=None
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
            "A": [[1, 0], [2, 0]] if a_positions is None else a_positions,
            "B": [[1, 2], [2, 2]] if b_positions is None else b_positions,
        },
    }


def _descriptor(**kwargs):
    return derive_feasibility_case_descriptor_v1(
        parse_feasibility_input_v1(_case_mapping(**kwargs))
    )


def _nested_keys(value):
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from _nested_keys(child)
    elif type(value) is list:
        for child in value:
            yield from _nested_keys(child)


def _nested_list_lengths(value):
    if type(value) is dict:
        for child in value.values():
            yield from _nested_list_lengths(child)
    elif type(value) is list:
        yield len(value)
        for child in value:
            yield from _nested_list_lengths(child)


def _is_sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


class FeasibilityCaseDescriptorTests(unittest.TestCase):
    def test_optimized_batch_descriptors_match_the_public_authority(self):
        for setup_count in (2, 3):
            observed = list(
                islice(
                    enumerate_feasibility_case_descriptors_v1(setup_count),
                    9,
                )
            )
            self.assertEqual(len(observed), 9)
            for case, descriptor in observed:
                self.assertEqual(len(case.a_positions), setup_count)
                self.assertEqual(
                    descriptor,
                    derive_feasibility_case_descriptor_v1(case),
                )

        for invalid in (True, 0, 1, 4, "3"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    next(enumerate_feasibility_case_descriptors_v1(invalid))

    def test_descriptor_schema_identity_and_absolute_density_are_exact(self):
        descriptor = _descriptor()
        self.assertEqual(
            set(descriptor),
            {
                "descriptor_version",
                "case_input_hash",
                "family_id",
                "stratum_id",
                "stratum",
                "definition_hash",
                "d4_canonical_hash",
                "gate",
                "descriptors",
                "descriptor_digest",
            },
        )
        self.assertEqual(descriptor["descriptor_version"], 1)
        for key in (
            "case_input_hash",
            "stratum_id",
            "definition_hash",
            "d4_canonical_hash",
            "descriptor_digest",
        ):
            self.assertTrue(_is_sha256(descriptor[key]))
        self.assertEqual(
            descriptor["descriptors"]["initial_occupancy_fraction"],
            {"numerator": 4, "denominator": 9},
        )
        self.assertFalse(
            any(
                type(value) is float
                for value in descriptor["descriptors"].values()
            )
        )

    def test_initial_goal_truth_table_is_role_explicit(self):
        cases = (
            (
                "NONE",
                [[1, 0], [2, 0]],
                [[1, 2], [2, 2]],
                False,
                False,
                [],
            ),
            (
                "A_ONLY",
                [[0, 0], [2, 0]],
                [[1, 2], [2, 2]],
                True,
                False,
                ["INITIAL_GOAL_A"],
            ),
            (
                "B_ONLY",
                [[1, 0], [2, 0]],
                [[0, 2], [2, 2]],
                False,
                True,
                ["INITIAL_GOAL_B"],
            ),
            (
                "BOTH",
                [[0, 0], [2, 0]],
                [[0, 2], [2, 2]],
                True,
                True,
                ["INITIAL_GOAL_A", "INITIAL_GOAL_B"],
            ),
        )
        for (
            label,
            a_positions,
            b_positions,
            expected_a,
            expected_b,
            expected_reasons,
        ) in cases:
            with self.subTest(label=label):
                descriptor = _descriptor(
                    a_positions=a_positions,
                    b_positions=b_positions,
                )
                goals = descriptor["gate"]["initial_goals"]
                self.assertEqual(goals["A"], expected_a)
                self.assertEqual(goals["B"], expected_b)
                self.assertEqual(goals["any"], expected_a or expected_b)
                self.assertEqual(
                    any(
                        "INITIAL_GOAL" in reason
                        for reason in descriptor["gate"]["rejection_reasons"]
                    ),
                    expected_a or expected_b,
                )
                self.assertEqual(
                    descriptor["gate"]["rejection_reasons"], expected_reasons
                )

    def test_initial_mobility_is_measured_for_both_roles(self):
        both_mobile = _descriptor()
        self.assertEqual(both_mobile["gate"]["initial_mobile"]["A"], True)
        self.assertEqual(both_mobile["gate"]["initial_mobile"]["B"], True)
        self.assertEqual(both_mobile["gate"]["initial_mobile"]["both"], True)
        self.assertGreater(
            both_mobile["gate"]["initial_legal_action_counts"]["A"], 0
        )
        self.assertGreater(
            both_mobile["gate"]["initial_legal_action_counts"]["B"], 0
        )

        converter_stuck = _descriptor(
            family_id="convert-push-front-v1",
            goal_frame="CONNECT_REACH_PERPENDICULAR",
            a_profile=ORTHOGONAL_4,
            b_profile=ORTHOGONAL_4,
            a_positions=[[0, 0], [0, 1]],
            b_positions=[[2, 0], [2, 1]],
        )
        self.assertEqual(
            converter_stuck["gate"]["initial_legal_action_counts"]["A"], 0
        )
        self.assertGreater(
            converter_stuck["gate"]["initial_legal_action_counts"]["B"], 0
        )
        self.assertFalse(converter_stuck["gate"]["initial_mobile"]["A"])
        self.assertTrue(converter_stuck["gate"]["initial_mobile"]["B"])
        self.assertFalse(converter_stuck["gate"]["initial_mobile"]["both"])
        self.assertTrue(
            any(
                "IMMOBIL" in reason
                for reason in converter_stuck["gate"]["rejection_reasons"]
            )
        )

    def test_first_player_does_not_hide_other_role_mobility_or_goals(self):
        arguments = {
            "family_id": "convert-push-front-v1",
            "goal_frame": "CONNECT_REACH_PERPENDICULAR",
            "a_profile": ORTHOGONAL_4,
            "b_profile": ORTHOGONAL_4,
            "a_positions": [[0, 0], [0, 1]],
            "b_positions": [[2, 0], [2, 1]],
        }
        a_first = _descriptor(first_player="A", **arguments)
        b_first = _descriptor(first_player="B", **arguments)
        self.assertEqual(a_first["stratum"]["first_player"], "A")
        self.assertEqual(b_first["stratum"]["first_player"], "B")
        self.assertNotEqual(a_first["stratum_id"], b_first["stratum_id"])
        self.assertNotEqual(
            a_first["d4_canonical_hash"], b_first["d4_canonical_hash"]
        )
        for key in (
            "initial_goals",
            "connection_material",
            "initial_legal_action_counts",
            "initial_mobile",
            "rejection_reasons",
            "eligible",
        ):
            with self.subTest(key=key):
                self.assertEqual(a_first["gate"][key], b_first["gate"][key])

    def test_connection_material_is_action_aware(self):
        fixed_two = _descriptor(
            family_id="swap-hop-network-v1",
            goal_frame="CONNECT_REACH_ALIGNED",
            a_profile=ORTHOGONAL_4,
            b_profile=KING_8,
        )
        convertible_two = _descriptor(
            family_id="convert-push-front-v1",
            goal_frame="CONNECT_REACH_PERPENDICULAR",
            a_profile=ORTHOGONAL_4,
            b_profile=KING_8,
        )
        fixed_both_two = _descriptor(
            family_id="push-swap-networks-v1",
            goal_frame="CONNECT_CONNECT_PERPENDICULAR",
            a_profile=ORTHOGONAL_4,
            b_profile=KING_8,
        )
        fixed_both_three = _descriptor(
            family_id="push-swap-networks-v1",
            goal_frame="CONNECT_CONNECT_PERPENDICULAR",
            a_profile=ORTHOGONAL_4,
            b_profile=KING_8,
            a_positions=[[0, 0], [1, 0], [2, 0]],
            b_positions=[[0, 2], [1, 2], [2, 2]],
        )
        self.assertFalse(
            fixed_two["gate"]["connection_material"]["A"]["supported"]
        )
        self.assertTrue(
            convertible_two["gate"]["connection_material"]["A"]["supported"]
        )
        self.assertFalse(
            fixed_both_two["gate"]["connection_material"]["A"]["supported"]
        )
        self.assertFalse(
            fixed_both_two["gate"]["connection_material"]["B"]["supported"]
        )
        self.assertFalse(
            fixed_both_two["gate"]["connection_material"]["both_supported"]
        )
        self.assertTrue(
            fixed_both_three["gate"]["connection_material"]["A"]["supported"]
        )
        self.assertTrue(
            fixed_both_three["gate"]["connection_material"]["B"]["supported"]
        )
        self.assertTrue(
            fixed_both_three["gate"]["connection_material"]["both_supported"]
        )

    def test_initial_dependency_and_direct_effect_counts_are_distinct(self):
        hop = _descriptor()
        hop_observation = hop["descriptors"]["initial_action_observations"]["B"]
        self.assertGreater(hop_observation["occupied_dependency_action_count"], 0)
        self.assertEqual(hop_observation["direct_effect_action_count"], 0)

        interacting_cases = (
            (
                "push-hop-race-v1",
                "REACH_REACH_SAME",
            ),
            (
                "swap-hop-network-v1",
                "CONNECT_REACH_ALIGNED",
            ),
            (
                "convert-push-front-v1",
                "CONNECT_REACH_PERPENDICULAR",
            ),
            (
                "capture-hop-hunt-v1",
                "ELIMINATE_REACH",
            ),
        )
        for family_id, goal_frame in interacting_cases:
            with self.subTest(family_id=family_id):
                descriptor = _descriptor(
                    family_id=family_id,
                    goal_frame=goal_frame,
                    a_profile=KING_8,
                    b_profile=KING_8,
                    a_positions=[[1, 0], [2, 0]],
                    b_positions=[[1, 1], [2, 2]],
                )
                observation = descriptor["descriptors"][
                    "initial_action_observations"
                ]["A"]
                self.assertGreater(
                    observation["occupied_dependency_action_count"], 0
                )
                self.assertGreater(observation["direct_effect_action_count"], 0)
                self.assertEqual(
                    observation["legal_action_count"],
                    descriptor["gate"]["initial_legal_action_counts"]["A"],
                )

    def test_all_eight_d4_transforms_preserve_semantic_descriptor(self):
        source = parse_feasibility_input_v1(
            _case_mapping(
                family_id="convert-capture-duel-v1",
                goal_frame="ELIMINATE_ELIMINATE",
                a_profile=KING_8,
                b_profile=KING_8,
                a_positions=[[0, 0], [1, 2]],
                b_positions=[[0, 2], [2, 1]],
            )
        )
        definition = compile_feasibility_definition_v1(source)
        expected = derive_feasibility_case_descriptor_v1(source)
        expected_projection = dict(expected)
        expected_projection.pop("case_input_hash")
        expected_projection.pop("definition_hash")
        expected_projection.pop("descriptor_digest")

        for transform in D4_TRANSFORMS:
            with self.subTest(transform=transform):
                transformed = transform_definition(definition, transform)
                positions = {"A": [], "B": []}
                for piece in transformed.initial_pieces:
                    positions[piece.owner.value].append(list(piece.position))
                mapping = source.to_dict()
                mapping["initial_positions"] = positions
                observed = derive_feasibility_case_descriptor_v1(
                    parse_feasibility_input_v1(mapping)
                )
                observed_projection = dict(observed)
                observed_projection.pop("case_input_hash")
                observed_projection.pop("definition_hash")
                observed_projection.pop("descriptor_digest")
                self.assertEqual(observed_projection, expected_projection)


class FeasibilityCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This is the only uncached full-domain reconstruction in this module.
        cls.report = build_feasibility_census_v1()
        cls.canonical = canonical_feasibility_census_json_v1()
        cls.validated = validate_feasibility_census_v1(cls.report)

    def test_full_reconstruction_and_fixed_global_counts(self):
        self.assertEqual(self.validated, self.report)
        self.assertEqual(json.loads(self.canonical), self.report)
        self.assertEqual(
            self.report["protocol"]["domain_hash"], feasibility_domain_hash_v1()
        )
        self.assertEqual(
            self.report["domain"],
            {
                "domain_hash": feasibility_domain_hash_v1(),
                "ordered_input_root": (
                    "e3011f74256fe39881eda3636533ec4352f7b4d2c4386e12d775ccc031b6d2e8"
                ),
                "case_input_count": 214_368,
            },
        )
        self.assertEqual(
            self.report["roots"]["ordered_input_root"],
            self.report["domain"]["ordered_input_root"],
        )
        self.assertEqual(
            self.report["global"]["case_counts"],
            {"raw": 214_368, "eligible": 71_384},
        )
        self.assertEqual(
            self.report["global"]["d4_orbit_counts"],
            {"raw": 102_336, "eligible": 24_208},
        )
        self.assertEqual(len(self.report["strata"]), 176)

    def test_family_partitions_and_aggregate_sums_are_exact(self):
        expected = {
            "push-hop-race-v1": (58_464, 39_456, 5_064, 3_528),
            "swap-hop-network-v1": (38_976, 19_968, 6_128, 3_168),
            "convert-push-front-v1": (38_976, 19_968, 10_640, 5_504),
            "capture-hop-hunt-v1": (19_488, 9_984, 5_720, 2_976),
            "convert-capture-duel-v1": (19_488, 2_688, 18_824, 2_576),
            "push-swap-networks-v1": (38_976, 10_272, 25_008, 6_456),
        }
        observed = {}
        for family in self.report["families"]:
            observed[family["family_id"]] = (
                family["case_counts"]["raw"],
                family["d4_orbit_counts"]["raw"],
                family["case_counts"]["eligible"],
                family["d4_orbit_counts"]["eligible"],
            )
            self.assertEqual(
                sum(
                    counts["exact"]
                    for counts in family["initial_goal_masks"].values()
                ),
                family["case_counts"]["raw"],
            )
            self.assertEqual(
                sum(
                    counts["d4_orbits"]
                    for counts in family["initial_goal_masks"].values()
                ),
                family["d4_orbit_counts"]["raw"],
            )
            self.assertEqual(
                sum(
                    counts["exact"]
                    for counts in family["initial_mobility_masks"].values()
                ),
                family["case_counts"]["raw"],
            )
            self.assertEqual(
                sum(
                    counts["d4_orbits"]
                    for counts in family["initial_mobility_masks"].values()
                ),
                family["d4_orbit_counts"]["raw"],
            )
        self.assertEqual(observed, expected)
        self.assertEqual(
            sum(item[2] for item in observed.values()),
            self.report["global"]["case_counts"]["eligible"],
        )
        self.assertEqual(
            sum(item[3] for item in observed.values()),
            self.report["global"]["d4_orbit_counts"]["eligible"],
        )
        multiplicities = self.report["global"][
            "d4_orbit_multiplicity_histogram"
        ]
        self.assertEqual(
            sum(multiplicities.values()),
            self.report["global"]["d4_orbit_counts"]["raw"],
        )
        self.assertEqual(
            sum(int(size) * count for size, count in multiplicities.items()),
            self.report["global"]["case_counts"]["raw"],
        )

        self.assertEqual(
            sum(stratum["case_counts"]["raw"] for stratum in self.report["strata"]),
            self.report["global"]["case_counts"]["raw"],
        )
        self.assertEqual(
            sum(
                stratum["d4_orbit_counts"]["raw"]
                for stratum in self.report["strata"]
            ),
            self.report["global"]["d4_orbit_counts"]["raw"],
        )
        self.assertEqual(
            sum(
                stratum["case_counts"]["eligible"] > 0
                for stratum in self.report["strata"]
            ),
            144,
        )
        expected_support = {
            "push-hop-race-v1": (48, 12, 131),
            "swap-hop-network-v1": (16, 194, 202),
            "convert-push-front-v1": (32, 138, 201),
            "capture-hop-hunt-v1": (16, 164, 208),
            "convert-capture-duel-v1": (16, 89, 227),
            "push-swap-networks-v1": (16, 402, 405),
        }
        observed_support = {}
        for family_id in expected_support:
            supply = [
                stratum["d4_orbit_counts"]["eligible"]
                for stratum in self.report["strata"]
                if stratum["family_id"] == family_id
                and stratum["d4_orbit_counts"]["eligible"] > 0
            ]
            observed_support[family_id] = (
                len(supply),
                min(supply),
                max(supply),
            )
        self.assertEqual(observed_support, expected_support)

    def test_roots_digest_and_d4_cross_check_are_complete(self):
        cross_check = self.report["d4_cross_check"]
        checked_cases = cross_check["authoritative_identity_case_count"]
        self.assertEqual(checked_cases, 391)
        self.assertTrue(cross_check["all_invariant"])
        self.assertEqual(cross_check["invariant_case_count"], 214_368)
        self.assertEqual(
            cross_check["authoritative_identity_stratum_count"], 176
        )
        self.assertEqual(
            cross_check["checked_transform_count"],
            214_368 * 8,
        )
        self.assertEqual(cross_check["violation_count"], 0)
        self.assertTrue(_is_sha256(cross_check["measurement_evidence_root"]))
        self.assertEqual(
            cross_check["measurement_evidence_root"],
            "e77c7e9cdebdab1251969bcbb5b8c7507849b560c3bf822937362e584960aebe",
        )
        self.assertEqual(
            cross_check["authoritative_identity_transform_count"],
            checked_cases * 8,
        )
        self.assertEqual(cross_check["authoritative_identity_mismatch_count"], 0)
        self.assertTrue(
            _is_sha256(cross_check["authoritative_identity_evidence_root"])
        )
        self.assertEqual(
            cross_check["authoritative_identity_evidence_root"],
            "d85deecaeb6ff1f2847573e7e925f23bb887935104ff7d73f66b19638181384a",
        )
        self.assertEqual(
            self.report["roots"],
            {
                "ordered_input_root": (
                    "e3011f74256fe39881eda3636533ec4352f7b4d2c4386e12d775ccc031b6d2e8"
                ),
                "ordered_stratum_root": (
                    "e022c0ac9e47a07e0ccc9aac1071bc9138eb7f18e8df2418ac4a5aa4d6ebb4bc"
                ),
                "ordered_case_to_d4_root": (
                    "e016d4644645595030914f496372c7d07cf2658def25b6c18394a339589100a6"
                ),
                "sorted_d4_orbit_witness_root": (
                    "3eccec7f3eb54a9eb7cb69ad707a7c6831426682fdcac9648c3f388919008853"
                ),
            },
        )
        for key, value in self.report["roots"].items():
            with self.subTest(root=key):
                self.assertTrue(_is_sha256(value))
        self.assertEqual(
            self.report["global"]["roots"],
            {
                "ordered_raw_case_input_root": (
                    "f8f486f5f20f55e9e5c2c65e10430af30e8f3b54faf4ea90161259a843351238"
                ),
                "ordered_eligible_case_input_root": (
                    "c63260e4a39e93505194c0c9eaf0db29a3718c81435a90fd43d995867b64e7b1"
                ),
                "ordered_raw_definition_root": (
                    "a535f9756f2f0cd84865ff65de350a7c1514a1564e81cc973d31a31ead443f07"
                ),
                "ordered_eligible_definition_root": (
                    "85fe7e43a97c466fff81e81d66cdf0768e05c3144e13d9608dfb81736aa71582"
                ),
                "ordered_raw_case_descriptor_root": (
                    "55b0f26cdb887b73a59548f47dc7f00a0e348b17a32a63fcde842b23d843f4cb"
                ),
                "ordered_eligible_case_descriptor_root": (
                    "a15d5b8a46d05425372e01779552581b81c429185c429a4f96c3c6b3d52e4b1c"
                ),
                "sorted_raw_d4_root": (
                    "f17e0b2781c7424fc5fda510c8687982dbc6b2a93041c87392867cf85a7dcc23"
                ),
                "sorted_eligible_d4_root": (
                    "6b96cf4ee19d708c61c941c5759c46db0fb0420f2f820959584dd5f1e34d0108"
                ),
            },
        )
        for key, value in self.report["global"]["roots"].items():
            with self.subTest(global_root=key):
                self.assertTrue(_is_sha256(value))
        self.assertTrue(_is_sha256(self.report["evidence_digest"]))
        self.assertEqual(
            self.report["evidence_digest"],
            FEASIBILITY_CENSUS_EVIDENCE_DIGEST_V1,
        )
        self.assertEqual(feasibility_census_hash_v1(), self.report["evidence_digest"])
        self.assertEqual(
            self.report["roots"]["ordered_case_to_d4_root"],
            FEASIBILITY_ORDERED_CASE_TO_D4_ROOT_V1,
        )
        self.assertEqual(
            self.report["global"]["roots"]["sorted_eligible_d4_root"],
            FEASIBILITY_SORTED_ELIGIBLE_D4_ROOT_V1,
        )

    def test_global_gate_and_descriptor_distributions_are_complete(self):
        global_record = self.report["global"]
        self.assertEqual(
            global_record["initial_goal_masks"],
            {
                "NEITHER": {"exact": 89_712, "d4_orbits": 30_496},
                "A_ONLY": {"exact": 13_552, "d4_orbits": 8_728},
                "B_ONLY": {"exact": 80_472, "d4_orbits": 42_712},
                "BOTH": {"exact": 30_632, "d4_orbits": 20_400},
            },
        )
        self.assertEqual(
            global_record["initial_mobility_masks"],
            {
                "BOTH": {"exact": 212_376, "d4_orbits": 101_504},
                "A_ONLY": {"exact": 0, "d4_orbits": 0},
                "B_ONLY": {"exact": 1_992, "d4_orbits": 832},
                "NEITHER": {"exact": 0, "d4_orbits": 0},
            },
        )
        self.assertEqual(
            global_record["gate_counts"]["connection_material_supported"],
            {"exact": 190_176, "d4_orbits": 92_832},
        )
        self.assertEqual(
            global_record["structural_state_upper_bounds"]["raw"]["exact"],
            {
                "14364": 42_336,
                "19836": 6_048,
                "26334": 12_096,
                "31920": 94_080,
                "40603": 6_048,
                "67032": 40_320,
                "181051": 13_440,
            },
        )
        self.assertEqual(
            global_record["structural_state_upper_bounds"]["eligible"]["exact"],
            {
                "14364": 2_992,
                "19836": 2_520,
                "26334": 4_536,
                "31920": 33_208,
                "40603": 5_432,
                "67032": 9_304,
                "181051": 13_392,
            },
        )
        expected_legal_sums = {
            "raw": {"A": 1_099_392, "B": 1_238_496},
            "eligible": {"A": 329_468, "B": 482_360},
        }
        for population, roles in expected_legal_sums.items():
            for role, expected_sum in roles.items():
                with self.subTest(population=population, role=role):
                    observation = global_record["initial_action_observations"][
                        population
                    ]["exact"][role]["legal_action_count"]
                    self.assertEqual(observation["sum"], expected_sum)
                    self.assertEqual(
                        observation["observation_count"],
                        global_record["case_counts"][population],
                    )

    def test_rejection_reason_combinations_partition_every_scope(self):
        reason_order = {
            reason: index
            for index, reason in enumerate(
                (
                    "INITIAL_GOAL_A",
                    "INITIAL_GOAL_B",
                    "INSUFFICIENT_CONNECTION_MATERIAL_A",
                    "INSUFFICIENT_CONNECTION_MATERIAL_B",
                    "INITIAL_IMMOBILITY_A",
                    "INITIAL_IMMOBILITY_B",
                )
            )
        }
        scopes = [
            self.report["global"],
            *self.report["families"],
            *self.report["strata"],
        ]
        for scope in scopes:
            combinations = scope["rejection_reason_combinations"]
            reason_tuples = [tuple(item["reasons"]) for item in combinations]
            with self.subTest(
                scope=scope.get(
                    "stratum_id", scope.get("family_id", "global")
                )
            ):
                self.assertEqual(len(reason_tuples), len(set(reason_tuples)))
                for reasons in reason_tuples:
                    self.assertEqual(
                        reasons,
                        tuple(sorted(reasons, key=reason_order.__getitem__)),
                    )
                self.assertEqual(
                    sum(item["exact"] for item in combinations),
                    scope["case_counts"]["raw"],
                )
                self.assertEqual(
                    sum(item["d4_orbits"] for item in combinations),
                    scope["d4_orbit_counts"]["raw"],
                )
                accepted = next(
                    (item for item in combinations if not item["reasons"]),
                    {"exact": 0, "d4_orbits": 0},
                )
                self.assertEqual(accepted["exact"], scope["case_counts"]["eligible"])
                self.assertEqual(
                    accepted["d4_orbits"],
                    scope["d4_orbit_counts"]["eligible"],
                )
                for reason, counts in scope["rejection_reason_counts"].items():
                    self.assertEqual(
                        sum(
                            item["exact"]
                            for item in combinations
                            if reason in item["reasons"]
                        ),
                        counts["exact"],
                    )
                    self.assertEqual(
                        sum(
                            item["d4_orbits"]
                            for item in combinations
                            if reason in item["reasons"]
                        ),
                        counts["d4_orbits"],
                    )
        self.assertEqual(
            self.report["global"]["rejection_reason_combinations"],
            [
                {"reasons": [], "exact": 71_384, "d4_orbits": 24_208},
                {
                    "reasons": ["INITIAL_GOAL_A"],
                    "exact": 13_544,
                    "d4_orbits": 8_720,
                },
                {
                    "reasons": ["INITIAL_GOAL_A", "INITIAL_GOAL_B"],
                    "exact": 30_608,
                    "d4_orbits": 20_384,
                },
                {
                    "reasons": [
                        "INITIAL_GOAL_A",
                        "INITIAL_GOAL_B",
                        "INITIAL_IMMOBILITY_A",
                    ],
                    "exact": 24,
                    "d4_orbits": 16,
                },
                {
                    "reasons": ["INITIAL_GOAL_A", "INITIAL_IMMOBILITY_A"],
                    "exact": 8,
                    "d4_orbits": 8,
                },
                {
                    "reasons": ["INITIAL_GOAL_B"],
                    "exact": 72_648,
                    "d4_orbits": 38_688,
                },
                {
                    "reasons": ["INITIAL_GOAL_B", "INITIAL_IMMOBILITY_A"],
                    "exact": 768,
                    "d4_orbits": 408,
                },
                {
                    "reasons": [
                        "INITIAL_GOAL_B",
                        "INSUFFICIENT_CONNECTION_MATERIAL_A",
                    ],
                    "exact": 7_056,
                    "d4_orbits": 3_616,
                },
                {
                    "reasons": ["INITIAL_IMMOBILITY_A"],
                    "exact": 1_192,
                    "d4_orbits": 400,
                },
                {
                    "reasons": ["INSUFFICIENT_CONNECTION_MATERIAL_A"],
                    "exact": 5_040,
                    "d4_orbits": 2_624,
                },
                {
                    "reasons": [
                        "INSUFFICIENT_CONNECTION_MATERIAL_A",
                        "INSUFFICIENT_CONNECTION_MATERIAL_B",
                    ],
                    "exact": 12_096,
                    "d4_orbits": 3_264,
                },
            ],
        )

    def test_validator_rejects_tampering_and_nonexact_types(self):
        mutations = (
            lambda value: value.update({"unknown": True}),
            lambda value: value.__setitem__("census_version", True),
            lambda value: value["global"]["case_counts"].__setitem__(
                "raw", True
            ),
            lambda value: value["families"][0].__setitem__(
                "case_counts",
                {
                    "raw": value["families"][0]["case_counts"]["raw"],
                    "eligible": value["families"][0]["case_counts"][
                        "eligible"
                    ]
                    + 1,
                },
            ),
            lambda value: value["roots"].__setitem__(
                next(iter(value["roots"])), "f" * 64
            ),
            lambda value: value.__setitem__("evidence_digest", "f" * 64),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(self.report)
                mutation(altered)
                with self.assertRaises((TypeError, ValueError)):
                    validate_feasibility_census_v1(altered)

        with self.assertRaises(TypeError):
            validate_feasibility_census_v1(
                type("DictSubclass", (dict,), {})(self.report)
            )

    def test_cached_build_and_validator_outputs_are_mutation_isolated(self):
        altered = build_feasibility_census_v1()
        altered["global"]["case_counts"]["raw"] = 1
        rebuilt = build_feasibility_census_v1()
        self.assertEqual(rebuilt, self.report)

        validated = validate_feasibility_census_v1(self.report)
        validated["families"][0]["family_id"] = "changed"
        self.assertEqual(validate_feasibility_census_v1(self.report), self.report)

    def test_artifact_is_compact_and_contains_no_case_definitions_or_results(self):
        encoded = self.canonical.encode("utf-8")
        self.assertEqual(len(encoded), 1_055_162)
        self.assertLess(len(encoded), 1_500_000)
        self.assertNotIn("cases", self.report)
        self.assertLessEqual(max(_nested_list_lengths(self.report)), 176)
        keys = {key.lower() for key in _nested_keys(self.report)}
        self.assertTrue(keys.isdisjoint({"cases", "definition", "definitions"}))
        forbidden = {"outcome", "outcomes", "result", "results", "winner", "winners"}
        self.assertTrue(keys.isdisjoint(forbidden))
        self.assertFalse(
            any(
                fragment in key
                for key in keys
                for fragment in ("outcome", "winner", "result")
            )
        )


class FeasibilityCensusPurityTests(unittest.TestCase):
    def test_module_is_python39_syntax_and_avoids_forbidden_project_layers(self):
        source_path = Path(inspect.getsourcefile(census_module))
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, feature_version=(3, 9))
        project_imports = set()
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_names.update(alias.name for alias in node.names)
                if node.level:
                    if node.module:
                        project_imports.add(node.module.split(".", 1)[0])
                    else:
                        project_imports.update(alias.name for alias in node.names)
                elif node.module and node.module.startswith("parity_forge"):
                    parts = node.module.split(".")
                    if len(parts) > 1:
                        project_imports.add(parts[1])
                    else:
                        project_imports.update(
                            alias.name for alias in node.names
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("parity_forge"):
                        project_imports.add(alias.name.split(".", 1)[-1])
        self.assertTrue(
            project_imports.isdisjoint(
                {"agents", "solver", "play", "agency", "analysis", "replay"}
            )
        )
        self.assertNotIn("Outcome", imported_names)

    def test_module_never_enters_gameplay_or_terminal_construction(self):
        source_path = Path(inspect.getsourcefile(census_module))
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        forbidden_calls = {
            "apply_action",
            "initial_state",
            "play_game",
            "replay",
            "solve",
            "solve_exact",
            "solve_game",
        }
        observed = set()
        game_state_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                observed.add(node.func.id)
                if node.func.id == "GameState":
                    game_state_calls.append(node)
            elif isinstance(node.func, ast.Attribute):
                observed.add(node.func.attr)
        self.assertTrue(observed.isdisjoint(forbidden_calls))
        self.assertTrue(game_state_calls)
        for call in game_state_calls:
            self.assertLessEqual(len(call.args), 3)
            outcome_keywords = [
                keyword for keyword in call.keywords if keyword.arg == "outcome"
            ]
            self.assertTrue(
                all(
                    isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is None
                    for keyword in outcome_keywords
                )
            )


if __name__ == "__main__":
    unittest.main()
