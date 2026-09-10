import copy
import unittest
from unittest import mock

import parity_forge.atlas_projection as projection_module
from parity_forge.atlas_projection import (
    ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
    build_atlas_identity_projection_v1,
    validate_atlas_identity_projection_v1,
)


def _hash(character):
    return character * 64


def _carriers():
    return [
        {
            "carrier_id": "artifact-a",
            "carrier_kind": "RUN",
            "source_digest": _hash("1"),
            "source_bytes": 10,
            "definition_occurrence_count": 2,
            "malformed_definition_like_count": 0,
            "identity_pairs": [
                {
                    "definition_hash": _hash("2"),
                    "d4_canonical_hash": _hash("3"),
                },
                {
                    "definition_hash": _hash("4"),
                    "d4_canonical_hash": _hash("5"),
                },
            ],
        },
        {
            "carrier_id": "artifact-b",
            "carrier_kind": "ATTEMPT",
            "source_digest": _hash("6"),
            "source_bytes": 8,
            "definition_occurrence_count": 1,
            "malformed_definition_like_count": 1,
            "identity_pairs": [
                {
                    "definition_hash": _hash("2"),
                    "d4_canonical_hash": _hash("3"),
                }
            ],
        },
    ]


class AtlasIdentityProjectionTests(unittest.TestCase):
    def setUp(self):
        self.carriers = _carriers()
        self.projection = build_atlas_identity_projection_v1(
            projection_id="test-history-v1",
            exposure_kind=ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
            cutoff_id="test-cutoff",
            carriers=self.carriers,
        )

    def test_projection_is_identity_only_complete_and_detached(self):
        self.assertEqual(self.projection["source_count"], 2)
        self.assertEqual(self.projection["definition_occurrence_count"], 3)
        self.assertEqual(self.projection["malformed_definition_like_count"], 1)
        self.assertEqual(self.projection["unique_definition_count"], 2)
        self.assertEqual(self.projection["unique_d4_count"], 2)
        self.carriers[0]["identity_pairs"][0]["definition_hash"] = _hash("f")
        self.assertEqual(
            self.projection["unique_definition_hashes"],
            [_hash("2"), _hash("4")],
        )
        validated = validate_atlas_identity_projection_v1(self.projection)
        validated["carriers"][0]["carrier_id"] = "changed"
        self.assertEqual(self.projection["carriers"][0]["carrier_id"], "artifact-a")

        forbidden = {
            "outcome",
            "result",
            "winner",
            "score",
            "utility",
            "assessment",
            "definition",
            "trace",
        }

        def keys(value):
            if type(value) is dict:
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif type(value) is list:
                for child in value:
                    yield from keys(child)

        self.assertTrue(forbidden.isdisjoint(keys(self.projection)))

    def test_projection_rejects_tamper_even_after_outer_resigning(self):
        def resign(value, carrier_index=None):
            if carrier_index is not None:
                carrier = dict(value["carriers"][carrier_index])
                carrier.pop("carrier_root")
                value["carriers"][carrier_index]["carrier_root"] = (
                    projection_module._domain_digest(
                        projection_module._CARRIER_DOMAIN_V1, carrier
                    )
                )
            unsigned_value = dict(value)
            unsigned_value.pop("projection_root")
            value["projection_root"] = projection_module._domain_digest(
                projection_module._PROJECTION_DOMAIN_V1, unsigned_value
            )

        changed = copy.deepcopy(self.projection)
        changed["unique_definition_count"] += 1
        resign(changed)
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            validate_atlas_identity_projection_v1(changed)

        changed = copy.deepcopy(self.projection)
        changed["carriers"][0]["identity_pairs"].reverse()
        resign(changed, 0)
        with self.assertRaisesRegex(ValueError, "ordered"):
            validate_atlas_identity_projection_v1(changed)

        changed = copy.deepcopy(self.projection)
        changed["carriers"][0]["identity_pairs"][0]["unexpected"] = 1
        resign(changed, 0)
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            validate_atlas_identity_projection_v1(changed)

    def test_validator_seals_input_before_late_caller_mutation(self):
        original_digest = projection_module._domain_digest
        mutated = False

        def mutating_digest(domain, value):
            nonlocal mutated
            if not mutated:
                self.projection["projection_id"] = "changed-after-seal"
                mutated = True
            return original_digest(domain, value)

        with mock.patch.object(
            projection_module, "_domain_digest", side_effect=mutating_digest
        ):
            with self.assertRaisesRegex(ValueError, "changed during validation"):
                validate_atlas_identity_projection_v1(self.projection)

    def test_builder_rejects_nonexact_or_open_inputs(self):
        invalid = _carriers()
        invalid.reverse()
        with self.assertRaisesRegex(ValueError, "carrier IDs"):
            build_atlas_identity_projection_v1(
                projection_id="test-history-v1",
                exposure_kind=ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
                cutoff_id="test-cutoff",
                carriers=invalid,
            )

        invalid = _carriers()
        invalid[0]["source_bytes"] = True
        with self.assertRaisesRegex(TypeError, "nonnegative exact integer"):
            build_atlas_identity_projection_v1(
                projection_id="test-history-v1",
                exposure_kind=ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
                cutoff_id="test-cutoff",
                carriers=invalid,
            )

        invalid = _carriers()
        invalid[0]["callback"] = lambda: None
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            build_atlas_identity_projection_v1(
                projection_id="test-history-v1",
                exposure_kind=ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
                cutoff_id="test-cutoff",
                carriers=invalid,
            )

        invalid = _carriers()
        invalid[1]["identity_pairs"][0]["d4_canonical_hash"] = _hash("7")
        with self.assertRaisesRegex(ValueError, "multiple D4 identities"):
            build_atlas_identity_projection_v1(
                projection_id="test-history-v1",
                exposure_kind=ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
                cutoff_id="test-cutoff",
                carriers=invalid,
            )


if __name__ == "__main__":
    unittest.main()
