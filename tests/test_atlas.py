import ast
import copy
import hashlib
import inspect
import json
import unittest
from collections import Counter
from pathlib import Path

import parity_forge.atlas as atlas_module
import parity_forge.atlas_history as atlas_history_module
from parity_forge.atlas import (
    ATLAS_CANONICAL_SELECTION_SHA256_V1,
    ATLAS_CANDIDATE_DEFINITION_COUNT_V1,
    ATLAS_CANDIDATE_PAIR_COUNT_V1,
    ATLAS_COLLISION_ROOT_V1,
    ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
    ATLAS_DEVELOPMENT_PAIR_COUNT_V1,
    ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1,
    ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1,
    ATLAS_FINAL_REGISTRY_ROOT_V1,
    ATLAS_HISTORY_BINDING_ROOT_V1,
    ATLAS_PAIRED_STRATUM_COUNT_V1,
    ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1,
    ATLAS_RAW_EXACT_SETUP_PAIR_COUNT_V1,
    ATLAS_SEARCH_ENVELOPE_ROOT_V1,
    ATLAS_SELECTION_PARTITION_ROOT_V1,
    build_atlas_family_registry_v1,
    build_atlas_paired_universe_v1,
    build_atlas_search_envelope_v1,
    build_atlas_selection_snapshot_v1,
    build_frozen_atlas_selection_snapshot_v1,
    canonical_frozen_atlas_selection_json_v1,
    validate_atlas_paired_universe_v1,
    validate_atlas_search_envelope_v1,
    validate_atlas_selection_snapshot_v1,
    validate_frozen_atlas_selection_snapshot_v1,
)
from parity_forge.atlas_projection import (
    ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
    ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1,
    build_atlas_identity_projection_v1,
)
from parity_forge.dsl import definition_hash, parse_definition
from parity_forge.family import family_registry_hash
from parity_forge.feasibility import build_state_work_proof_v1
from parity_forge.feasibility_census import (
    enumerate_feasibility_case_descriptors_v1,
)
from parity_forge.symmetry import (
    D4_TRANSFORMS,
    canonicalize_d4,
    transform_definition,
)


def _sha(label):
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _projection(kind, pairs=(), *, cutoff, malformed=0, label="fixture"):
    identities = sorted(
        (
            {
                "definition_hash": definition_digest,
                "d4_canonical_hash": d4_digest,
            }
            for definition_digest, d4_digest in pairs
        ),
        key=lambda item: (
            item["definition_hash"], item["d4_canonical_hash"]
        ),
    )
    carriers = []
    if identities or malformed:
        carriers.append(
            {
                "carrier_id": "test-{}-carrier".format(label),
                "carrier_kind": "TEST_DEFINITION_EXPOSURE",
                "source_digest": _sha("source-" + label),
                "source_bytes": len(
                    json.dumps(identities, sort_keys=True).encode("utf-8")
                ),
                "definition_occurrence_count": len(identities),
                "malformed_definition_like_count": malformed,
                "identity_pairs": identities,
            }
        )
    return build_atlas_identity_projection_v1(
        projection_id="test-{}-projection".format(label),
        exposure_kind=kind,
        cutoff_id=cutoff,
        carriers=carriers,
    )


def _empty_prior():
    # The real reviewed historical graph deliberately contains one invalid
    # static fixture.  The selector retains that authenticated projection fact
    # and does not reinterpret it as a selector error.
    return _projection(
        ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
        cutoff="test-prior-git-tree",
        malformed=1,
        label="prior-empty",
    )


def _empty_synthetic():
    return _projection(
        ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1,
        cutoff="test-synthetic-benchmark-root",
        label="synthetic-empty",
    )


def _without_name_and_first(definition):
    value = definition.to_dict()
    value.pop("name")
    value.pop("first_player")
    return value


def _nested_keys(value):
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from _nested_keys(child)
    elif type(value) is list:
        for child in value:
            yield from _nested_keys(child)


class AtlasPureSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = build_atlas_family_registry_v1()
        cls.envelope = build_atlas_search_envelope_v1()
        cls.universe = build_atlas_paired_universe_v1()
        cls.prior = _empty_prior()
        cls.synthetic = _empty_synthetic()
        cls.selection = build_atlas_selection_snapshot_v1(
            cls.prior, cls.synthetic
        )

    def test_final_registry_and_common_support_envelope_are_exact(self):
        self.assertEqual(
            self.registry.family_ids,
            (
                "push-hop-race-v1",
                "swap-hop-network-v1",
                "convert-push-front-v1",
                "capture-hop-hunt-v1",
                "convert-capture-duel-v1",
                "push-swap-networks-v1",
            ),
        )
        self.assertEqual(
            family_registry_hash(self.registry), ATLAS_FINAL_REGISTRY_ROOT_V1
        )
        self.assertEqual(len(self.envelope["families"]), 6)
        self.assertEqual(
            self.envelope["search_envelope_root"],
            ATLAS_SEARCH_ENVELOPE_ROOT_V1,
        )
        self.assertEqual(
            len(self.envelope["paired_strata"]),
            ATLAS_PAIRED_STRATUM_COUNT_V1,
        )
        self.assertTrue(
            all(
                family["development_pair_count"] == 24
                and family["candidate_pair_count"] == 24
                for family in self.envelope["families"]
            )
        )
        self.assertTrue(
            all(
                "first_player" not in record["stratum"]
                and record["stratum"]["setup"]
                == {"A_count": 3, "B_count": 3}
                for record in self.envelope["paired_strata"]
            )
        )
        deferred = self.envelope["deferred_two_plus_two"]
        self.assertEqual(
            deferred["status"], "ALL_ELIGIBLE_TWO_PLUS_TWO_DEFERRED"
        )
        self.assertEqual(
            deferred["census"],
            {
                "raw_exact_setup_pair_count": 33_264,
                "raw_exact_setup_definition_count": 66_528,
                "eligible_exact_setup_pair_count": 7_740,
                "eligible_exact_setup_definition_count": 15_480,
                "eligible_paired_d4_count": 3_250,
                "eligible_paired_d4_definition_count": 6_500,
                "deferred_eligible_pair_count": 3_250,
                "deferred_eligible_definition_count": 6_500,
                "supported_paired_stratum_count": 28,
                "supported_member_stratum_count": 56,
                "unsupported_paired_stratum_count": 16,
                "unsupported_member_stratum_count": 32,
            },
        )
        self.assertEqual(
            deferred["full_parent_reconstruction"],
            {
                "raw_exact_setup_pair_count": 107_184,
                "raw_exact_setup_definition_count": 214_368,
                "eligible_exact_setup_pair_count": 35_692,
                "eligible_exact_setup_definition_count": 71_384,
                "eligible_paired_d4_count": 12_104,
                "eligible_paired_d4_definition_count": 24_208,
            },
        )
        unsupported_pairs = deferred["ordered_unsupported_paired_strata"]
        unsupported_members = deferred["ordered_unsupported_member_strata"]
        self.assertEqual(len(unsupported_pairs), 16)
        self.assertEqual(len(unsupported_members), 32)
        self.assertEqual(
            Counter(member["family_id"] for member in unsupported_members),
            {"swap-hop-network-v1": 16, "push-swap-networks-v1": 16},
        )
        self.assertTrue(
            all(
                member["stratum"]["setup"]
                == {"A_count": 2, "B_count": 2}
                and member["eligible_exact_definition_count"] == 0
                and member["eligible_d4_definition_count"] == 0
                and member["parent_feasibility_stratum_id"]
                and all(
                    reason.startswith("INSUFFICIENT_CONNECTION_MATERIAL_")
                    for reason in member["universal_rejection_reasons"]
                )
                for member in unsupported_members
            )
        )
        validate_atlas_search_envelope_v1(self.envelope)

    def test_envelope_validator_rejects_unknown_tamper_and_inner_resign(self):
        unknown = copy.deepcopy(self.envelope)
        unknown["unknown"] = True
        with self.assertRaises(ValueError):
            validate_atlas_search_envelope_v1(unknown)

        resigned = copy.deepcopy(self.envelope)
        resigned["fixed_domain"]["board_size"] = 4
        unsigned = dict(resigned)
        unsigned.pop("search_envelope_root")
        resigned["search_envelope_root"] = atlas_module._domain_digest(
            atlas_module._ENVELOPE_ROOT_DOMAIN_V1, unsigned
        )
        with self.assertRaises(ValueError):
            validate_atlas_search_envelope_v1(resigned)

        deep_resigned = copy.deepcopy(self.envelope)
        deferred = deep_resigned["deferred_two_plus_two"]
        deferred["ordered_unsupported_member_strata"][0][
            "universal_rejection_reasons"
        ] = ["INITIAL_IMMOBILITY_A"]
        deferred["unsupported_member_strata_root"] = (
            atlas_module._domain_digest(
                atlas_module._DEFERRED_MEMBER_STRATA_ROOT_DOMAIN_V1,
                {
                    "parent_census_roots": deferred["parent_census_roots"],
                    "ordered_unsupported_member_strata": deferred[
                        "ordered_unsupported_member_strata"
                    ],
                },
            )
        )
        deferred_unsigned = dict(deferred)
        deferred_unsigned.pop("deferred_two_plus_two_root")
        deferred["deferred_two_plus_two_root"] = atlas_module._domain_digest(
            atlas_module._DEFERRED_TWO_PLUS_TWO_ROOT_DOMAIN_V1,
            deferred_unsigned,
        )
        envelope_unsigned = dict(deep_resigned)
        envelope_unsigned.pop("search_envelope_root")
        deep_resigned["search_envelope_root"] = atlas_module._domain_digest(
            atlas_module._ENVELOPE_ROOT_DOMAIN_V1, envelope_unsigned
        )
        with self.assertRaises(ValueError):
            validate_atlas_search_envelope_v1(deep_resigned)

    def test_paired_universe_reproduces_all_supply_and_member_multiplicity(self):
        census = self.universe["census"]
        self.assertEqual(
            census["raw_exact_setup_pair_count"],
            ATLAS_RAW_EXACT_SETUP_PAIR_COUNT_V1,
        )
        self.assertEqual(
            census["eligible_exact_setup_pair_count"],
            ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1,
        )
        self.assertEqual(
            census["eligible_paired_d4_count"],
            ATLAS_ELIGIBLE_PAIRED_D4_COUNT_V1,
        )
        self.assertEqual(
            self.universe["paired_universe_witness_root"],
            ATLAS_PAIRED_UNIVERSE_WITNESS_ROOT_V1,
        )
        self.assertEqual(census["paired_stratum_count"], 44)
        self.assertEqual(census["minimum_eligible_pairs_per_stratum"], 12)
        self.assertEqual(census["maximum_eligible_pairs_per_stratum"], 405)
        self.assertEqual(
            census["orbit_multiplicity_histogram"],
            {"1": 688, "2": 4236, "4": 3162, "8": 768},
        )
        self.assertEqual(
            sum(pair["orbit_multiplicity"] for pair in self.universe["pairs"]),
            ATLAS_ELIGIBLE_EXACT_SETUP_PAIR_COUNT_V1,
        )
        for pair in self.universe["pairs"]:
            multiplicity = pair["orbit_multiplicity"]
            exact_pair_witnesses = pair["domain_exact_pair_witnesses"]
            self.assertEqual(
                pair["domain_exact_pair_witness_count"], multiplicity
            )
            self.assertEqual(len(exact_pair_witnesses), multiplicity)
            self.assertEqual(
                len(
                    {
                        witness["paired_input_identity"]
                        for witness in exact_pair_witnesses
                    }
                ),
                multiplicity,
            )
            self.assertEqual(
                pair["domain_exact_pair_witness_root"],
                atlas_module._domain_digest(
                    atlas_module._PAIR_EXACT_WITNESS_ROOT_DOMAIN_V1,
                    exact_pair_witnesses,
                ),
            )
            for member in pair["members"].values():
                self.assertEqual(
                    member["domain_exact_definition_count"], multiplicity
                )
                self.assertEqual(
                    len(member["domain_exact_definition_hashes"]), multiplicity
                )
                self.assertEqual(
                    member["domain_exact_definition_hashes"],
                    sorted(set(member["domain_exact_definition_hashes"])),
                )
                self.assertEqual(
                    len(member["representative_d4_slot_definition_hashes"]),
                    8,
                )
                self.assertEqual(
                    member["representative_d4_slot_definition_hashes"][0],
                    member["representative_definition_hash"],
                )
                self.assertEqual(
                    member["representative_d4_slot_definition_root"],
                    atlas_module._domain_digest(
                        atlas_module._MEMBER_D4_SLOT_ROOT_DOMAIN_V1,
                        {
                            "first_player": member["first_player"],
                            "ordered_transforms": list(D4_TRANSFORMS),
                            "exact_definition_hashes": member[
                                "representative_d4_slot_definition_hashes"
                            ],
                        },
                    ),
                )
            self.assertEqual(
                {
                    witness["ordered_exact_definition_hashes"]["A_FIRST"]
                    for witness in exact_pair_witnesses
                },
                set(
                    pair["members"]["A_FIRST"][
                        "domain_exact_definition_hashes"
                    ]
                ),
            )
            self.assertEqual(
                {
                    witness["ordered_exact_definition_hashes"]["B_FIRST"]
                    for witness in exact_pair_witnesses
                },
                set(
                    pair["members"]["B_FIRST"][
                        "domain_exact_definition_hashes"
                    ]
                ),
            )

        representative = parse_definition(
            self.universe["pairs"][0]["members"]["A_FIRST"][
                "representative_definition"
            ]
        )
        expected_slots = [
            definition_hash(
                transform_definition(
                    representative,
                    transform,
                    name=representative.name,
                )
            )
            for transform in D4_TRANSFORMS
        ]
        self.assertEqual(
            self.universe["pairs"][0]["members"]["A_FIRST"][
                "representative_d4_slot_definition_hashes"
            ],
            expected_slots,
        )

    def test_state_work_proof_is_first_player_independent(self):
        descriptors = iter(enumerate_feasibility_case_descriptors_v1(3))
        a_case, _a_descriptor = next(descriptors)
        b_case, _b_descriptor = next(descriptors)
        self.assertEqual(a_case.first_player.value, "A")
        self.assertEqual(b_case.first_player.value, "B")
        self.assertEqual(
            atlas_module._case_pair_key(a_case),
            atlas_module._case_pair_key(b_case),
        )
        self.assertEqual(
            json.dumps(
                build_state_work_proof_v1(a_case),
                sort_keys=True,
                separators=(",", ":"),
            ),
            json.dumps(
                build_state_work_proof_v1(b_case),
                sort_keys=True,
                separators=(",", ":"),
            ),
        )

    def test_pair_identity_binds_neutral_mechanics_and_ordered_members(self):
        pair = self.universe["pairs"][0]
        member_a = pair["members"]["A_FIRST"]
        member_b = pair["members"]["B_FIRST"]
        definition_a = parse_definition(member_a["representative_definition"])
        definition_b = parse_definition(member_b["representative_definition"])
        self.assertEqual(definition_a.first_player.value, "A")
        self.assertEqual(definition_b.first_player.value, "B")
        self.assertEqual(
            _without_name_and_first(definition_a),
            _without_name_and_first(definition_b),
        )
        self.assertIn(
            pair["paired_mechanical_d4_identity"][:24], definition_a.name
        )
        self.assertIn(
            pair["paired_mechanical_d4_identity"][:24], definition_b.name
        )
        canonical_a = canonicalize_d4(definition_a)
        canonical_b = canonicalize_d4(definition_b)
        self.assertEqual(canonical_a.transform, "I")
        self.assertEqual(canonical_b.transform, "I")
        self.assertEqual(canonical_a.canonical_hash, member_a["d4_canonical_hash"])
        self.assertEqual(canonical_b.canonical_hash, member_b["d4_canonical_hash"])

        neutral = json.loads(canonical_a.mechanical_json)
        neutral.pop("first_player")
        payload = {
            "family_signature_hash": pair["family_signature_hash"],
            "neutral_mechanical_digest": hashlib.sha256(
                atlas_module._canonical_bytes(neutral)
            ).hexdigest(),
            "neutral_mechanical_definition": neutral,
            "member_d4_identities": {
                "A_FIRST": member_a["d4_canonical_hash"],
                "B_FIRST": member_b["d4_canonical_hash"],
            },
        }
        self.assertEqual(
            atlas_module._domain_digest(
                atlas_module._PAIR_D4_ID_DOMAIN_V1, payload
            ),
            pair["paired_mechanical_d4_identity"],
        )
        payload["member_d4_identities"] = {
            "A_FIRST": member_b["d4_canonical_hash"],
            "B_FIRST": member_a["d4_canonical_hash"],
        }
        self.assertNotEqual(
            atlas_module._domain_digest(
                atlas_module._PAIR_D4_ID_DOMAIN_V1, payload
            ),
            pair["paired_mechanical_d4_identity"],
        )

    def test_universe_validator_rebuilds_instead_of_trusting_resigned_fields(self):
        validate_atlas_paired_universe_v1(self.universe)
        resigned = copy.deepcopy(self.universe)
        resigned["census"]["eligible_paired_d4_count"] -= 1
        # This top root deliberately remains internally valid because the
        # changed summary is derivable rather than an input to the witness root.
        # Reconstruction must still reject it.
        with self.assertRaises(ValueError):
            validate_atlas_paired_universe_v1(resigned)

    def test_universe_validator_rejects_resigned_exact_pair_permutation(self):
        resigned = copy.deepcopy(self.universe)
        target = next(
            pair
            for pair in resigned["pairs"]
            if pair["domain_exact_pair_witness_count"] >= 2
        )
        first, second = target["domain_exact_pair_witnesses"][:2]
        for field in (
            "ordered_case_input_hashes",
            "ordered_exact_definition_hashes",
        ):
            first[field]["B_FIRST"], second[field]["B_FIRST"] = (
                second[field]["B_FIRST"],
                first[field]["B_FIRST"],
            )
        target["domain_exact_pair_witness_root"] = atlas_module._domain_digest(
            atlas_module._PAIR_EXACT_WITNESS_ROOT_DOMAIN_V1,
            target["domain_exact_pair_witnesses"],
        )
        target["pair_witness_digest"] = atlas_module._domain_digest(
            atlas_module._PAIR_WITNESS_DOMAIN_V1,
            atlas_module._pair_witness_payload(target),
        )
        stratum_id = target["paired_stratum_id"]
        stratum_pairs = [
            pair
            for pair in resigned["pairs"]
            if pair["paired_stratum_id"] == stratum_id
        ]
        stratum = next(
            record
            for record in resigned["paired_strata"]
            if record["paired_stratum_id"] == stratum_id
        )
        stratum["ordered_pair_root"] = atlas_module._domain_digest(
            atlas_module._STRATUM_UNIVERSE_DOMAIN_V1,
            [
                {
                    "rank_digest": pair["rank_digest"],
                    "paired_mechanical_d4_identity": pair[
                        "paired_mechanical_d4_identity"
                    ],
                    "pair_witness_digest": pair["pair_witness_digest"],
                }
                for pair in stratum_pairs
            ],
        )
        resigned["paired_universe_witness_root"] = atlas_module._domain_digest(
            atlas_module._UNIVERSE_ROOT_DOMAIN_V1,
            {
                "search_envelope_root": resigned["search_envelope_root"],
                "ordered_pair_witnesses": [
                    {
                        "paired_stratum_id": pair["paired_stratum_id"],
                        "rank_digest": pair["rank_digest"],
                        "paired_mechanical_d4_identity": pair[
                            "paired_mechanical_d4_identity"
                        ],
                        "pair_witness_digest": pair["pair_witness_digest"],
                    }
                    for pair in resigned["pairs"]
                ],
            },
        )
        with self.assertRaises(ValueError):
            validate_atlas_paired_universe_v1(resigned)

    def test_empty_history_selects_disjoint_equal_family_blocks(self):
        selection = self.selection
        census = selection["census"]
        self.assertEqual(
            census["development_pair_count"], ATLAS_DEVELOPMENT_PAIR_COUNT_V1
        )
        self.assertEqual(
            census["development_definition_count"],
            ATLAS_DEVELOPMENT_DEFINITION_COUNT_V1,
        )
        self.assertEqual(
            census["candidate_pair_count"], ATLAS_CANDIDATE_PAIR_COUNT_V1
        )
        self.assertEqual(
            census["candidate_definition_count"],
            ATLAS_CANDIDATE_DEFINITION_COUNT_V1,
        )
        self.assertEqual(census["untouched_residual_pair_count"], 8566)
        self.assertEqual(selection["history"]["excluded_pair_count"], 0)
        self.assertEqual(
            selection["history"][
                "prior_gameplay_malformed_definition_like_count"
            ],
            1,
        )
        self.assertEqual(
            selection["history"]["prior_gameplay_cutoff_id"],
            "test-prior-git-tree",
        )
        self.assertEqual(
            selection["history"]["synthetic_fixture_cutoff_id"],
            "test-synthetic-benchmark-root",
        )
        development_ids = {
            pair["paired_mechanical_d4_identity"]
            for pair in selection["development_pairs"]
        }
        candidate_ids = {
            pair["paired_mechanical_d4_identity"]
            for pair in selection["confirmation_candidate_pairs"]
        }
        self.assertFalse(development_ids & candidate_ids)
        self.assertEqual(
            Counter(pair["family_id"] for pair in selection["development_pairs"]),
            {family_id: 24 for family_id in self.registry.family_ids},
        )
        self.assertEqual(
            Counter(
                pair["family_id"]
                for pair in selection["confirmation_candidate_pairs"]
            ),
            {family_id: 24 for family_id in self.registry.family_ids},
        )
        validate_atlas_selection_snapshot_v1(
            selection, self.prior, self.synthetic
        )

    def test_production_surface_requires_frozen_projection_roots(self):
        self.assertIn(
            "build_frozen_atlas_selection_snapshot_v1",
            atlas_module.__all__,
        )
        self.assertIn(
            "validate_frozen_atlas_selection_snapshot_v1",
            atlas_module.__all__,
        )
        self.assertIn(
            "canonical_frozen_atlas_selection_json_v1",
            atlas_module.__all__,
        )
        self.assertNotIn("build_atlas_selection_snapshot_v1", atlas_module.__all__)
        self.assertNotIn(
            "validate_atlas_selection_snapshot_v1", atlas_module.__all__
        )
        self.assertNotIn(
            "canonical_atlas_selection_json_v1", atlas_module.__all__
        )
        with self.assertRaises(ValueError):
            build_frozen_atlas_selection_snapshot_v1(
                self.prior, self.synthetic
            )

    def test_frozen_production_selection_reconstructs_from_real_cutoff(self):
        repository = Path(__file__).resolve().parents[1]
        raw_history = {
            source_path: (repository / source_path).read_bytes()
            for source_path, _digest, _byte_count in (
                atlas_history_module.ATLAS_HISTORY_INVENTORY_V1
            )
        }
        prior = (
            atlas_history_module.build_prior_gameplay_exposure_projection_v1(
                raw_history
            )
        )
        synthetic = (
            atlas_history_module.build_synthetic_fixture_exposure_projection_v1()
        )
        self.assertEqual(
            prior["projection_root"],
            atlas_history_module.ATLAS_HISTORY_PROJECTION_ROOT_V1,
        )
        self.assertEqual(
            synthetic["projection_root"],
            atlas_history_module.ATLAS_SYNTHETIC_PROJECTION_ROOT_V1,
        )

        selection = build_frozen_atlas_selection_snapshot_v1(
            prior, synthetic
        )
        self.assertEqual(
            selection["history"]["history_binding_root"],
            ATLAS_HISTORY_BINDING_ROOT_V1,
        )
        self.assertEqual(
            selection["history"]["collision_root"],
            ATLAS_COLLISION_ROOT_V1,
        )
        self.assertEqual(
            selection["selection_partition_root"],
            ATLAS_SELECTION_PARTITION_ROOT_V1,
        )
        self.assertEqual(selection["history"]["excluded_pair_count"], 0)
        validate_frozen_atlas_selection_snapshot_v1(
            selection, prior, synthetic
        )
        canonical = canonical_frozen_atlas_selection_json_v1(
            prior, synthetic, selection
        )
        self.assertEqual(
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            ATLAS_CANONICAL_SELECTION_SHA256_V1,
        )

    def test_every_reported_pair_population_has_twice_the_definitions(self):
        def visit(value):
            if type(value) is list:
                for child in value:
                    visit(child)
                return
            if type(value) is not dict:
                return
            for key, count in value.items():
                definition_key = None
                if key.endswith("_pair_count"):
                    definition_key = key[: -len("_pair_count")] + (
                        "_definition_count"
                    )
                elif key.endswith("_paired_d4_count"):
                    definition_key = key[: -len("_count")] + (
                        "_definition_count"
                    )
                elif key.endswith("_pairs_per_stratum"):
                    definition_key = key.replace(
                        "_pairs_per_stratum", "_definitions_per_stratum"
                    )
                elif key in (
                    "minimum_eligible_pairs_per_stratum",
                    "maximum_eligible_pairs_per_stratum",
                ):
                    definition_key = key.replace("pairs", "definitions")
                elif key == "pair_quota":
                    definition_key = "definition_quota"
                if definition_key is not None:
                    self.assertIn(definition_key, value, key)
                    self.assertEqual(value[definition_key], 2 * count, key)
            if "family_paired_d4_counts" in value:
                self.assertEqual(
                    value["family_paired_d4_definition_counts"],
                    {
                        family_id: 2 * count
                        for family_id, count in value[
                            "family_paired_d4_counts"
                        ].items()
                    },
                )
            if "collision_class_counts" in value:
                self.assertEqual(
                    value["collision_class_definition_counts"],
                    {
                        label: 2 * count
                        for label, count in value[
                            "collision_class_counts"
                        ].items()
                    },
                )
            for child in value.values():
                visit(child)

        visit(self.envelope)
        visit(self.universe)
        visit(self.selection)

    def test_exact_collision_excludes_whole_pair_without_reshuffling_rank(self):
        r90_index = list(D4_TRANSFORMS).index("R90")
        target, target_member = next(
            (pair, pair["members"]["A_FIRST"])
            for pair in self.universe["pairs"]
            if pair["members"]["A_FIRST"][
                "representative_d4_slot_definition_hashes"
            ][r90_index]
            not in set(
                pair["members"]["A_FIRST"][
                    "domain_exact_definition_hashes"
                ]
            )
        )
        # R90 is deliberately outside the canonical goal-frame quotient here.
        # It must still be an exact collision carrier for the retained member.
        exact_hash = target_member[
            "representative_d4_slot_definition_hashes"
        ][r90_index]
        self.assertNotEqual(
            exact_hash, target_member["representative_definition_hash"]
        )
        self.assertNotIn(
            exact_hash, target_member["domain_exact_definition_hashes"]
        )
        prior = _projection(
            ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
            [(exact_hash, _sha("unrelated-d4"))],
            cutoff="injected-prior",
            label="exact-a",
        )
        synthetic = _projection(
            ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1,
            cutoff="separate-synthetic",
            label="no-synthetic",
        )
        selected = build_atlas_selection_snapshot_v1(prior, synthetic)
        self.assertEqual(selected["history"]["excluded_pair_count"], 1)
        exclusion = selected["history"]["excluded_pairs"][0]
        self.assertEqual(exclusion["collision_class"], "A_FIRST_ONLY")
        self.assertTrue(exclusion["members"]["A_FIRST"]["exact_collision"])
        self.assertFalse(exclusion["members"]["A_FIRST"]["d4_collision"])
        self.assertFalse(exclusion["members"]["B_FIRST"]["collides"])

        stratum_id = target["paired_stratum_id"]
        expected = [
            pair["paired_mechanical_d4_identity"]
            for pair in self.universe["pairs"]
            if pair["paired_stratum_id"] == stratum_id
            and pair["paired_mechanical_d4_identity"]
            != target["paired_mechanical_d4_identity"]
        ][:2]
        observed = [
            pair["paired_mechanical_d4_identity"]
            for pair in selected["development_pairs"]
            if pair["paired_stratum_id"] == stratum_id
        ]
        self.assertEqual(observed, expected)
        self.assertEqual(
            selected["paired_universe_witness_root"],
            self.selection["paired_universe_witness_root"],
        )
        self.assertNotEqual(
            selected["selection_partition_root"],
            self.selection["selection_partition_root"],
        )

    def test_d4_collision_classes_b_member_and_both_members(self):
        target = self.universe["pairs"][1]
        a_member = target["members"]["A_FIRST"]
        b_member = target["members"]["B_FIRST"]
        prior = _projection(
            ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
            [(_sha("unrelated-exact-b"), b_member["d4_canonical_hash"])],
            cutoff="prior-d4-b",
            label="d4-b",
        )
        selected = build_atlas_selection_snapshot_v1(prior, self.synthetic)
        exclusion = selected["history"]["excluded_pairs"][0]
        self.assertEqual(exclusion["collision_class"], "B_FIRST_ONLY")
        self.assertTrue(exclusion["members"]["B_FIRST"]["d4_collision"])

        both = _projection(
            ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
            [
                (_sha("unrelated-exact-a"), a_member["d4_canonical_hash"]),
                (_sha("unrelated-exact-b2"), b_member["d4_canonical_hash"]),
            ],
            cutoff="prior-d4-both",
            label="d4-both",
        )
        selected_both = build_atlas_selection_snapshot_v1(both, self.synthetic)
        exclusion_both = selected_both["history"]["excluded_pairs"][0]
        self.assertEqual(exclusion_both["collision_class"], "BOTH")
        self.assertTrue(exclusion_both["members"]["A_FIRST"]["d4_collision"])
        self.assertTrue(exclusion_both["members"]["B_FIRST"]["d4_collision"])

    def test_history_shortfall_fails_closed_without_backfill(self):
        limiting = next(
            stratum
            for stratum in self.universe["paired_strata"]
            if stratum["eligible_pair_count"] == 12
        )
        pairs = [
            pair
            for pair in self.universe["pairs"]
            if pair["paired_stratum_id"] == limiting["paired_stratum_id"]
        ]
        identities = [
            (_sha("shortfall-exact-{}".format(index)), pair["members"]["A_FIRST"]["d4_canonical_hash"])
            for index, pair in enumerate(pairs[:9])
        ]
        prior = _projection(
            ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
            identities,
            cutoff="shortfall-prior",
            label="shortfall",
        )
        with self.assertRaisesRegex(ValueError, "below both-block quota"):
            build_atlas_selection_snapshot_v1(prior, self.synthetic)

    def test_selection_validator_and_caches_are_mutation_isolated(self):
        tampered = copy.deepcopy(self.selection)
        tampered["census"]["development_pair_count"] = 143
        with self.assertRaises(ValueError):
            validate_atlas_selection_snapshot_v1(
                tampered, self.prior, self.synthetic
            )

        envelope = build_atlas_search_envelope_v1()
        universe = build_atlas_paired_universe_v1()
        selection = build_atlas_selection_snapshot_v1(
            self.prior, self.synthetic
        )
        envelope["families"][0]["family_id"] = "mutated"
        universe["pairs"][0]["family_id"] = "mutated"
        selection["development_pairs"][0]["family_id"] = "mutated"
        self.assertNotEqual(
            build_atlas_search_envelope_v1()["families"][0]["family_id"],
            "mutated",
        )
        self.assertNotEqual(
            build_atlas_paired_universe_v1()["pairs"][0]["family_id"],
            "mutated",
        )
        self.assertNotEqual(
            build_atlas_selection_snapshot_v1(self.prior, self.synthetic)[
                "development_pairs"
            ][0]["family_id"],
            "mutated",
        )

    def test_rank_has_no_history_or_display_name_input(self):
        parameters = tuple(
            inspect.signature(atlas_module._pair_rank_digest).parameters
        )
        self.assertEqual(
            parameters,
            (
                "family_signature_digest",
                "neutral_stratum",
                "pair_d4_identity",
            ),
        )
        self.assertNotIn("history", inspect.getsource(atlas_module._pair_rank_digest))
        self.assertNotIn("family_id", inspect.getsource(atlas_module._pair_rank_digest))

    def test_module_is_python39_and_has_no_evaluator_or_execution_import(self):
        source = Path(atlas_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source, feature_version=(3, 9))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        forbidden = {
            "glob",
            "importlib",
            "os",
            "pathlib",
            "random",
            "subprocess",
            "time",
            "parity_forge.agency",
            "parity_forge.agents",
            "parity_forge.engine",
            "parity_forge.experiments",
            "parity_forge.play",
            "parity_forge.solver",
            "agency",
            "agents",
            "engine",
            "experiments",
            "play",
            "solver",
        }
        self.assertFalse(imports & forbidden)
        forbidden_calls = {"open", "eval", "exec", "__import__"}
        observed_calls = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                observed_calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                observed_calls.add(node.func.attr)
        self.assertFalse(observed_calls & forbidden_calls)
        self.assertTrue(
            all(
                not name.endswith("_evaluation")
                and not name.endswith("_experiments")
                for name in imports
            )
        )
        forbidden_keys = {
            "assessment",
            "results",
            "score",
            "winner",
            "outcome",
            "result",
            "utility",
            "agent",
            "trace",
            "timing",
        }
        for report in (self.envelope, self.universe, self.selection):
            self.assertFalse(set(_nested_keys(report)) & forbidden_keys)


if __name__ == "__main__":
    unittest.main()
