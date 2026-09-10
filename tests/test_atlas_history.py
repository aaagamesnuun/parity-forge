import ast
import copy
import hashlib
import json
import runpy
import subprocess
import unittest
from pathlib import Path

import parity_forge.atlas_history as history
from parity_forge.atlas_projection import (
    ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1,
    ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1,
    validate_atlas_identity_projection_v1,
)


REPOSITORY = Path(__file__).resolve().parents[1]


def _keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


class AtlasHistoryProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = {
            source_path: (REPOSITORY / source_path).read_bytes()
            for source_path, _, _ in history.ATLAS_HISTORY_INVENTORY_V1
        }
        cls.projection = history.build_prior_gameplay_exposure_projection_v1(
            cls.raw
        )

    def test_frozen_inventory_and_projection_census(self):
        inventory = history.ATLAS_HISTORY_INVENTORY_V1
        self.assertEqual(len(inventory), history.ATLAS_HISTORY_SOURCE_COUNT_V1)
        self.assertEqual(
            [record[0] for record in inventory],
            sorted({record[0] for record in inventory}),
        )
        for source_path, expected_digest, expected_bytes in inventory:
            raw = self.raw[source_path]
            self.assertEqual(len(raw), expected_bytes)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_digest)

        projection = self.projection
        self.assertEqual(
            projection["exposure_kind"], ATLAS_PRIOR_GAMEPLAY_EXPOSURE_KIND_V1
        )
        self.assertEqual(
            projection["cutoff_id"], history.ATLAS_HISTORY_CUTOFF_ID_V1
        )
        self.assertEqual(projection["source_count"], 66)
        self.assertEqual(projection["definition_occurrence_count"], 2_243)
        self.assertEqual(projection["malformed_definition_like_count"], 1)
        self.assertEqual(projection["unique_definition_count"], 1_172)
        self.assertEqual(projection["unique_d4_count"], 1_168)
        self.assertEqual(
            projection["source_attestation_root"],
            history.ATLAS_HISTORY_SOURCE_ATTESTATION_ROOT_V1,
        )
        self.assertEqual(
            projection["unique_definition_root"],
            history.ATLAS_HISTORY_UNIQUE_DEFINITION_ROOT_V1,
        )
        self.assertEqual(
            projection["unique_d4_root"],
            history.ATLAS_HISTORY_UNIQUE_D4_ROOT_V1,
        )
        self.assertEqual(
            projection["projection_root"],
            history.ATLAS_HISTORY_PROJECTION_ROOT_V1,
        )
        self.assertEqual(
            validate_atlas_identity_projection_v1(projection), projection
        )

    def test_inventory_is_exactly_the_declared_cutoff_tree_json_set(self):
        tree = subprocess.check_output(
            [
                "git",
                "show",
                "-s",
                "--format=%T",
                history.ATLAS_HISTORY_CUTOFF_COMMIT_V1,
            ],
            cwd=REPOSITORY,
            text=True,
        ).strip()
        self.assertEqual(tree, history.ATLAS_HISTORY_CUTOFF_TREE_V1)
        tracked = subprocess.check_output(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                history.ATLAS_HISTORY_CUTOFF_COMMIT_V1,
                "--",
                "experiments",
            ],
            cwd=REPOSITORY,
            text=True,
        ).splitlines()
        expected = [
            source_path
            for source_path, _, _ in history.ATLAS_HISTORY_INVENTORY_V1
        ]
        self.assertEqual([item for item in tracked if item.endswith(".json")], expected)
        for source_path, expected_digest, expected_bytes in (
            history.ATLAS_HISTORY_INVENTORY_V1
        ):
            cutoff_bytes = subprocess.check_output(
                [
                    "git",
                    "show",
                    "{}:{}".format(
                        history.ATLAS_HISTORY_CUTOFF_COMMIT_V1,
                        source_path,
                    ),
                ],
                cwd=REPOSITORY,
            )
            self.assertEqual(len(cutoff_bytes), expected_bytes)
            self.assertEqual(
                hashlib.sha256(cutoff_bytes).hexdigest(), expected_digest
            )
            self.assertEqual(cutoff_bytes, self.raw[source_path])

    def test_all_sources_cross_only_the_identity_boundary(self):
        forbidden = {
            "definition",
            "outcome",
            "result",
            "results",
            "winner",
            "status",
            "trace",
            "actions",
            "principal_variation",
            "timing",
        }
        self.assertFalse(set(_keys(self.projection)) & forbidden)
        self.assertEqual(
            [carrier["carrier_id"] for carrier in self.projection["carriers"]],
            [record[0] for record in history.ATLAS_HISTORY_INVENTORY_V1],
        )
        bearing = sum(
            bool(
                carrier["definition_occurrence_count"]
                or carrier["malformed_definition_like_count"]
            )
            for carrier in self.projection["carriers"]
        )
        self.assertEqual(
            bearing, history.ATLAS_HISTORY_DEFINITION_BEARING_SOURCE_COUNT_V1
        )
        self.assertEqual(
            len(self.projection["carriers"]) - bearing,
            history.ATLAS_HISTORY_ZERO_DEFINITION_SOURCE_COUNT_V1,
        )
        self.assertEqual(
            history.ATLAS_HISTORY_SCHEMA_OCCURRENCE_COUNTS_V1,
            ((1, 1_665), (2, 258), (3, 320)),
        )
        self.assertEqual(
            history.ATLAS_HISTORY_DEFINITION_HASH_REFERENCE_COUNT_V1, 5_297
        )
        self.assertEqual(
            history.ATLAS_HISTORY_UNIQUE_DEFINITION_HASH_REFERENCE_COUNT_V1,
            1_172,
        )
        self.assertEqual(history.ATLAS_HISTORY_D4_HASH_REFERENCE_COUNT_V1, 2_951)
        self.assertEqual(
            history.ATLAS_HISTORY_UNIQUE_D4_HASH_REFERENCE_COUNT_V1, 896
        )

    def test_raw_capability_requires_the_exact_path_set_and_immutable_bytes(self):
        missing = dict(self.raw)
        missing.pop(next(iter(missing)))
        with self.assertRaisesRegex(ValueError, "path set mismatch"):
            history.build_prior_gameplay_exposure_projection_v1(missing)

        extra = dict(self.raw)
        extra["experiments/runs/unreviewed/run.json"] = b"{}"
        with self.assertRaisesRegex(ValueError, "path set mismatch"):
            history.build_prior_gameplay_exposure_projection_v1(extra)

        wrong_container = list(self.raw.items())
        with self.assertRaisesRegex(TypeError, "exact path-to-bytes"):
            history.build_prior_gameplay_exposure_projection_v1(wrong_container)

        wrong_value = dict(self.raw)
        source_path = history.ATLAS_HISTORY_INVENTORY_V1[2][0]
        wrong_value[source_path] = bytearray(wrong_value[source_path])
        with self.assertRaisesRegex(TypeError, "exact bytes"):
            history.build_prior_gameplay_exposure_projection_v1(wrong_value)

        changed = dict(self.raw)
        source_path = history.ATLAS_HISTORY_INVENTORY_V1[2][0]
        changed[source_path] = changed[source_path][:-1] + b" "
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            history.build_prior_gameplay_exposure_projection_v1(changed)

    def test_strict_json_loader_rejects_duplicate_nonfinite_and_non_utf8(self):
        for raw, message in (
            (b'{"x":1,"x":2}', "duplicate key"),
            (b'{"x":NaN}', "non-finite"),
            (b'{"x":Infinity}', "non-finite"),
            (b'{"x":1e400}', "finite"),
            (b"\xff", "UTF-8"),
        ):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, message):
                    history._load_strict_json_bytes(raw, "fixture")
        with self.assertRaisesRegex(TypeError, "immutable bytes"):
            history._load_strict_json_bytes(bytearray(b"{}"), "fixture")

    def test_projection_is_independent_of_surrounding_result_state(self):
        source = json.loads(
            self.raw["experiments/corpora/static-v1/corpus.json"].decode("utf-8")
        )["cases"][0]["definition"]
        completed = {
            "status": "COMPLETED",
            "result": {"winner": "A"},
            "definition": source,
        }
        failed = {
            "status": "FAILED",
            "result": {"winner": "B", "censored": True},
            "definition": copy.deepcopy(source),
        }
        completed_scan = history._scan_document(completed, "completed.json")
        failed_scan = history._scan_document(failed, "failed.json")
        self.assertEqual(completed_scan[0], failed_scan[0])
        self.assertEqual(completed_scan[1], failed_scan[1])
        self.assertEqual(completed_scan[3], failed_scan[3])


class AtlasSyntheticFixtureProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        benchmark = runpy.run_path(str(REPOSITORY / "tests/test_agency_benchmark.py"))
        cls.definitions = {
            fixture["fixture_id"]: copy.deepcopy(fixture["definition"])
            for fixture in benchmark["FIXTURES"]
        }
        cls.projection = history.build_synthetic_fixture_exposure_projection_v1()

    def test_frozen_identity_projection_binds_the_plan0012_benchmark_parent(self):
        projection = self.projection
        self.assertEqual(
            projection["exposure_kind"],
            ATLAS_SYNTHETIC_FIXTURE_EXPOSURE_KIND_V1,
        )
        self.assertIn(
            history.PLAN0012_SYNTHETIC_BENCHMARK_ROOT_V1,
            projection["cutoff_id"],
        )
        self.assertEqual(projection["source_count"], 7)
        self.assertEqual(projection["definition_occurrence_count"], 7)
        self.assertEqual(projection["malformed_definition_like_count"], 0)
        self.assertEqual(projection["unique_definition_count"], 7)
        self.assertEqual(projection["unique_d4_count"], 7)
        self.assertEqual(
            projection["source_attestation_root"],
            history.ATLAS_SYNTHETIC_SOURCE_ATTESTATION_ROOT_V1,
        )
        self.assertEqual(
            projection["unique_definition_root"],
            history.ATLAS_SYNTHETIC_UNIQUE_DEFINITION_ROOT_V1,
        )
        self.assertEqual(
            projection["unique_d4_root"],
            history.ATLAS_SYNTHETIC_UNIQUE_D4_ROOT_V1,
        )
        self.assertEqual(
            projection["projection_root"],
            history.ATLAS_SYNTHETIC_PROJECTION_ROOT_V1,
        )

    def test_canonical_fixture_definitions_rederive_the_same_projection(self):
        before = copy.deepcopy(self.definitions)
        rebuilt = history.build_synthetic_fixture_exposure_projection_v1(
            self.definitions
        )
        self.assertEqual(rebuilt, self.projection)
        self.assertEqual(self.definitions, before)

    def test_fixture_definition_identity_and_shape_fail_closed(self):
        missing = copy.deepcopy(self.definitions)
        missing.pop(next(iter(missing)))
        with self.assertRaisesRegex(ValueError, "ID set"):
            history.build_synthetic_fixture_exposure_projection_v1(missing)

        renamed = copy.deepcopy(self.definitions)
        fixture_id = "initial-stuck-zero-v1"
        renamed[fixture_id]["name"] += " changed"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            history.build_synthetic_fixture_exposure_projection_v1(renamed)

        non_json = copy.deepcopy(self.definitions)
        fixture_id = "swap-both-roles-repeat-v1"
        non_json[fixture_id]["initial_pieces"] = tuple(
            non_json[fixture_id]["initial_pieces"]
        )
        with self.assertRaisesRegex(TypeError, "exact JSON"):
            history.build_synthetic_fixture_exposure_projection_v1(non_json)

    def test_synthetic_and_prior_gameplay_identity_sets_are_disjoint(self):
        gameplay = getattr(AtlasHistoryProjectionTests, "projection", None)
        if gameplay is None:
            raw = {
                source_path: (REPOSITORY / source_path).read_bytes()
                for source_path, _, _ in history.ATLAS_HISTORY_INVENTORY_V1
            }
            gameplay = history.build_prior_gameplay_exposure_projection_v1(raw)
        self.assertFalse(
            set(gameplay["unique_definition_hashes"])
            & set(self.projection["unique_definition_hashes"])
        )
        self.assertFalse(
            set(gameplay["unique_d4_hashes"])
            & set(self.projection["unique_d4_hashes"])
        )

    def test_production_module_is_python39_and_does_not_import_tests(self):
        source_path = Path(history.__file__)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path), feature_version=(3, 9))
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertFalse(any(name.startswith("tests") for name in imported))
        self.assertNotIn("test_agency_benchmark", source)
        forbidden_imports = {
            "agents",
            "agency",
            "evaluation",
            "experiments",
            "glob",
            "os",
            "pathlib",
            "play",
            "random",
            "solver",
            "subprocess",
            "time",
        }
        self.assertFalse(
            {
                name.split(".")[-1]
                for name in imported
            }
            & forbidden_imports
        )


if __name__ == "__main__":
    unittest.main()
