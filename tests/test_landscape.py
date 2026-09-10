import hashlib
import json
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from parity_forge.dsl import definition_hash, parse_definition
from parity_forge.landscape import build_landscape_manifest
from parity_forge.symmetry import canonicalize_d4, d4_canonical_hash, mechanical_json


ROOT = Path(__file__).resolve().parents[1]
KNOWN_RUNS = (
    ROOT / "experiments/runs/20260830T154155824053Z-batch-g20260831/run.json",
    ROOT / "experiments/runs/20260830T154309225370Z-batch-g20260831/run.json",
    ROOT / "experiments/runs/20260830T184008717197Z-strong-g20260901/run.json",
)


def load_known_definitions():
    definitions = []
    for path in KNOWN_RUNS:
        with path.open("r", encoding="utf-8") as source:
            record = json.load(source)
        definitions.extend(
            parse_definition(candidate["definition"])
            for candidate in record["results"]["candidates"]
        )
    return tuple(definitions)


class LandscapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.known = load_known_definitions()
        cls.source_metadata = {
            "run_ids": [path.parent.name for path in KNOWN_RUNS]
        }
        cls.provenance = {"protocol": "plan-0006", "outcome_accessed": False}
        cls.manifest = build_landscape_manifest(
            cls.known, cls.source_metadata, cls.provenance
        )

    def test_census_matches_the_predeclared_landscape(self) -> None:
        census = self.manifest["census"]
        self.assertEqual(census["raw_definition_count"], 36720)
        self.assertEqual(census["raw_d4_orbit_count"], 4776)
        self.assertEqual(census["matched_known_d4_orbit_count"], 55)
        self.assertEqual(census["d4_orbit_count_after_known_exclusion"], 4721)
        self.assertEqual(census["raw_vector_count_8_d4_orbit_count"], 24)
        self.assertEqual(
            census["structurally_excluded_vector_count_8_d4_orbit_count"], 19
        )
        self.assertEqual(census["eligible_d4_orbit_count"], 4702)
        self.assertEqual(census["stratum_count"], 96)
        self.assertEqual(census["quota_per_stratum"], 4)
        self.assertEqual(census["minimum_eligible_d4_orbits_per_stratum"], 19)
        self.assertEqual(census["maximum_eligible_d4_orbits_per_stratum"], 92)
        self.assertEqual(census["selected_case_count"], 384)

    def test_every_stratum_has_four_distinct_canonical_orbits(self) -> None:
        cases = self.manifest["cases"]
        counts = Counter(
            tuple(sorted(case["stratum"].items())) for case in cases
        )
        self.assertEqual(len(counts), 96)
        self.assertEqual(set(counts.values()), {4})
        self.assertEqual(len({case["case_id"] for case in cases}), 384)
        self.assertEqual(len({case["d4_canonical_hash"] for case in cases}), 384)
        self.assertNotIn(8, {case["vector_count"] for case in cases})

    def test_selection_scores_ranks_hashes_and_orientation_are_exact(self) -> None:
        by_stratum = defaultdict(list)
        expected_case_keys = {
            "case_id",
            "stratum",
            "vector_count",
            "selection_score",
            "selection_rank",
            "definition_hash",
            "d4_canonical_hash",
            "definition",
        }
        for case in self.manifest["cases"]:
            self.assertEqual(set(case), expected_case_keys)
            definition = parse_definition(case["definition"])
            self.assertEqual(definition_hash(definition), case["definition_hash"])
            self.assertEqual(
                d4_canonical_hash(definition), case["d4_canonical_hash"]
            )
            canonical = canonicalize_d4(definition)
            self.assertEqual(mechanical_json(definition), canonical.mechanical_json)
            expected_score = hashlib.sha256(
                ("landscape-v1:" + case["d4_canonical_hash"]).encode("ascii")
            ).hexdigest()
            self.assertEqual(case["selection_score"], expected_score)
            by_stratum[tuple(sorted(case["stratum"].items()))].append(case)

        for selected in by_stratum.values():
            self.assertEqual(
                [case["selection_rank"] for case in selected], [1, 2, 3, 4]
            )
            self.assertEqual(
                [case["selection_score"] for case in selected],
                sorted(case["selection_score"] for case in selected),
            )

    def test_known_orbits_are_excluded(self) -> None:
        known_orbits = {
            d4_canonical_hash(definition)
            for definition in self.known
            if definition.board_size == 3 and definition.max_plies in (6, 9, 18)
        }
        selected_orbits = {
            case["d4_canonical_hash"] for case in self.manifest["cases"]
        }
        self.assertTrue(known_orbits)
        self.assertTrue(known_orbits.isdisjoint(selected_orbits))

    def test_known_definition_input_order_does_not_change_manifest(self) -> None:
        reversed_manifest = build_landscape_manifest(
            tuple(reversed(self.known)), self.source_metadata, self.provenance
        )
        self.assertEqual(self.manifest, reversed_manifest)

    def test_ordered_case_selection_has_a_frozen_fingerprint(self) -> None:
        payload = json.dumps(
            self.manifest["cases"], sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "e9cf41f3827190765d447684aa668a2a9ffa88fc9e2c4e186e41b80bb71c8543",
        )


if __name__ == "__main__":
    unittest.main()
