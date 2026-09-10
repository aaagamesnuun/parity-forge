import ast
import copy
import hashlib
import json
import runpy
import subprocess
import unittest
from pathlib import Path

from parity_forge import atlas_history as legacy
from parity_forge.dsl import parse_definition, canonical_json
from research.parity_forge_history import history_cutoff as cutoff
from research.parity_forge_history import history_identity as identity
from research.parity_forge_history import history_pins as pins


REPOSITORY = Path(__file__).resolve().parents[1]


def _keys(value):
    if type(value) is dict:
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif type(value) is list:
        for child in value:
            yield from _keys(child)


class HistoryIdentityProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = subprocess.check_output(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                cutoff.HISTORY_CUTOFF_COMMIT_V1,
                "--",
                "experiments",
            ],
            cwd=REPOSITORY,
            text=True,
        ).splitlines()
        paths = [path for path in paths if path.endswith(".json")]
        cls.classification = cutoff.classify_history_cutoff_paths_v1(
            paths,
            cutoff_commit=cutoff.HISTORY_CUTOFF_COMMIT_V1,
            cutoff_tree=cutoff.HISTORY_CUTOFF_TREE_V1,
            plan0013_subtree=cutoff.PLAN0013_SUBTREE_V1,
            plan0014_subtree=cutoff.PLAN0014_SUBTREE_V1,
        )
        cls.raw = {
            source_path: subprocess.check_output(
                [
                    "git",
                    "show",
                    "{}:{}".format(
                        legacy.ATLAS_HISTORY_CUTOFF_COMMIT_V1, source_path
                    ),
                ],
                cwd=REPOSITORY,
            )
            for source_path, _, _ in legacy.ATLAS_HISTORY_INVENTORY_V1
        }
        namespace = runpy.run_path(str(REPOSITORY / "tests/test_agency_benchmark.py"))
        cls.fixture_bytes = {
            row["fixture_id"]: canonical_json(parse_definition(row["definition"])).encode()
            for row in namespace["FIXTURES"]
        }
        cls.projection = identity.build_history_identity_projection_v1(
            cls.classification, cls.raw, cls.fixture_bytes
        )

    def test_complete_projection_closes_at_frozen_counts_and_roots(self):
        observed = self.projection
        self.assertEqual(observed["source_count"], 73)
        self.assertEqual(observed["definition_occurrence_count"], 2_250)
        self.assertEqual(observed["malformed_definition_like_count"], 1)
        self.assertEqual(observed["unique_definition_count"], 1_179)
        self.assertEqual(observed["unique_d4_count"], 1_175)
        self.assertEqual(observed["unique_role_neutral_count"], 1_175)
        self.assertEqual(observed["carrier_root"], identity.HISTORY_CARRIER_ROOT_V1)
        self.assertEqual(observed["identity_root"], identity.HISTORY_IDENTITY_ROOT_V1)
        self.assertEqual(
            observed["projection_root"], identity.HISTORY_PROJECTION_ROOT_V1
        )
        self.assertEqual(
            identity.validate_history_identity_projection_v1(observed), observed
        )

    def test_projection_contains_only_identity_and_provenance_fields(self):
        forbidden = {
            "action",
            "actions",
            "agent",
            "candidate",
            "definition",
            "metric",
            "outcome",
            "principal_variation",
            "result",
            "results",
            "score",
            "status",
            "timing",
            "trace",
            "winner",
        }
        self.assertFalse(set(_keys(self.projection)) & forbidden)
        self.assertEqual(self.projection["cutoff"]["plan0013"]["artifacts_opened"], 0)
        self.assertEqual(self.projection["cutoff"]["plan0014"]["artifacts_opened"], 0)

    def test_source_carrier_links_are_complete_and_exact(self):
        carriers = {
            row["carrier_id"]: row["carrier_identity"]
            for row in self.projection["carriers"]
        }
        self.assertEqual(len(carriers), 73)
        for row in self.projection["identities"]:
            self.assertEqual(
                row["source_carrier_identities"],
                sorted(carriers[source] for source in row["source_carrier_ids"]),
            )
            self.assertGreaterEqual(
                row["occurrence_count"], len(row["source_carrier_ids"])
            )
        self.assertEqual(
            sum(row["occurrence_count"] for row in self.projection["identities"]),
            2_250,
        )

    def test_cutoff_and_source_changes_fail_closed(self):
        changed_cutoff = copy.deepcopy(self.classification)
        changed_cutoff["plan0013"]["artifacts_opened"] = 1
        with self.assertRaisesRegex(identity.HistoryIdentityError, "cutoff mismatch"):
            identity.build_history_identity_projection_v1(
                changed_cutoff, self.raw, self.fixture_bytes
            )

        missing = dict(self.raw)
        missing.pop(next(iter(missing)))
        with self.assertRaisesRegex(ValueError, "path set mismatch"):
            identity.build_history_identity_projection_v1(
                self.classification, missing, self.fixture_bytes
            )

        changed = dict(self.raw)
        source = next(iter(changed))
        changed[source] = changed[source][:-1] + b" "
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            identity.build_history_identity_projection_v1(
                self.classification, changed, self.fixture_bytes
            )

    def test_validator_rejects_field_root_and_self_consistent_forgery(self):
        extra = copy.deepcopy(self.projection)
        extra["winner"] = "A"
        with self.assertRaisesRegex(identity.HistoryIdentityError, "keys mismatch"):
            identity.validate_history_identity_projection_v1(extra)

        changed = copy.deepcopy(self.projection)
        changed["identities"][0]["role_neutral_hash"] = "0" * 64
        with self.assertRaisesRegex(identity.HistoryIdentityError, "root mismatch"):
            identity.validate_history_identity_projection_v1(changed)

        resigned = copy.deepcopy(changed)
        resigned["identity_root"] = identity._digest(
            identity._IDENTITY_ROOT_DOMAIN_V1, resigned["identities"]
        )
        unsigned = dict(resigned)
        unsigned.pop("projection_root")
        resigned["projection_root"] = identity._digest(
            identity._PROJECTION_ROOT_DOMAIN_V1, unsigned
        )
        with self.assertRaisesRegex(identity.HistoryIdentityError, "frozen roots"):
            identity.validate_history_identity_projection_v1(resigned)

    def test_frozen_sources_rederive_the_same_detached_projection(self):
        definitions = dict(self.fixture_bytes)
        rebuilt = identity.build_history_identity_projection_v1(
            self.classification, self.raw, definitions
        )
        self.assertEqual(rebuilt, self.projection)
        self.assertEqual(definitions, self.fixture_bytes)
        rebuilt["identities"].clear()
        self.assertEqual(len(self.projection["identities"]), 1179)

    def test_all_role_neutral_rows_match_independent_legacy_oracle(self):
        from tests.test_history_wire_identity import _definition_values, _neutral_oracle

        definitions = {}
        for raw in self.raw.values():
            for value in _definition_values(json.loads(raw)):
                parsed = parse_definition(value)
                exact = hashlib.sha256(canonical_json(parsed).encode()).hexdigest()
                definitions[exact] = parsed.to_dict()
        for raw in self.fixture_bytes.values():
            definitions[hashlib.sha256(raw).hexdigest()] = json.loads(raw)
        self.assertEqual(len(definitions), 1179)
        for row in self.projection["identities"]:
            with self.subTest(exact=row["definition_hash"]):
                self.assertEqual(
                    row["role_neutral_hash"], _neutral_oracle(definitions[row["definition_hash"]])
                )

    def test_legacy_byte_pins_cover_the_later_cutoff_without_any_content_scan(self):
        paths = [row[0] for row in pins.ATLAS_HISTORY_INVENTORY_V1]
        records = [
            subprocess.check_output(
                ["git", "ls-tree", "-r", commit, "--"] + paths, cwd=REPOSITORY
            )
            for commit in (
                cutoff.LEGACY_HISTORY_CUTOFF_COMMIT_V1, cutoff.HISTORY_CUTOFF_COMMIT_V1
            )
        ]
        self.assertEqual(len(records[0].splitlines()), 66)
        self.assertEqual(records[0], records[1])
        for name in vars(pins):
            if name.startswith(("ATLAS_", "PLAN0012_", "_EXPECTED_MALFORMED_")):
                self.assertEqual(getattr(pins, name), getattr(legacy, name))

    def test_all_seven_fixture_wires_are_mandatory_and_byte_authenticated(self):
        variants = [None, {}, list(self.fixture_bytes.items())]
        source = next(iter(self.fixture_bytes))
        for replacement in (
            bytearray(self.fixture_bytes[source]),
            json.loads(self.fixture_bytes[source]),
            self.fixture_bytes[source] + b" ",
            self.fixture_bytes[source].replace(b'"max_plies":3', b'"max_plies":4'),
        ):
            if replacement == self.fixture_bytes[source]:
                replacement = b"x" * len(self.fixture_bytes[source])
            changed = dict(self.fixture_bytes)
            changed[source] = replacement
            variants.append(changed)
        unknown = dict(self.fixture_bytes)
        unknown["extra-fixture"] = b"{}"
        variants.append(unknown)
        for variant in variants:
            with self.subTest(kind=type(variant).__name__):
                with self.assertRaises((TypeError, ValueError)):
                    identity.build_history_identity_projection_v1(
                        self.classification, self.raw, variant
                    )

    def test_cutoff_rejects_numeric_aliases_before_scanning(self):
        for path, value in (
            (("history_cutoff_version",), True),
            (("plan0013", "artifacts_opened"), False),
            (("json_path_count",), float(self.classification["json_path_count"])),
        ):
            changed = copy.deepcopy(self.classification)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.assertRaises((TypeError, ValueError)):
                identity.build_history_identity_projection_v1(changed, {}, {})

    def test_projection_validator_rejects_aliases_and_bounded_resource_violations(self):
        class HostileDict(dict):
            def items(self):
                raise AssertionError("caller method must not run")
        variants = [HostileDict(self.projection)]
        for field, bad in (
            ("source_count", True),
            ("projection_version", 1.0),
            ("identities", tuple(self.projection["identities"])),
            ("parents", HostileDict(self.projection["parents"])),
            ("projection_id", "x" * (2 * 1024 * 1024 + 1)),
            ("source_count", 1 << 100_000),
        ):
            changed = copy.deepcopy(self.projection)
            changed[field] = bad
            variants.append(changed)
        cyclic = {}
        cyclic["self"] = cyclic
        variants.append(cyclic)
        for variant in variants:
            with self.assertRaises((TypeError, ValueError)):
                identity.validate_history_identity_projection_v1(variant)

    def test_identity_output_does_not_depend_on_surrounding_results(self):
        definition = json.loads(next(iter(self.fixture_bytes.values())))
        first = {"definition": definition, "status": "COMPLETE", "result": {"winner": "A"}}
        second = {"definition": definition, "status": "FAILED", "result": {"winner": "B"}}
        self.assertEqual(
            identity._scan_document(first, "fixture"),
            identity._scan_document(second, "fixture"),
        )

    def test_adapter_has_no_filesystem_process_network_or_dynamic_import(self):
        source_path = (
            REPOSITORY
            / "research/parity_forge_history/history_identity.py"
        )
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path), feature_version=(3, 9))
        imports = set()
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imports.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        self.assertTrue(
            imports.isdisjoint(
                {"glob", "importlib", "os", "pathlib", "socket", "subprocess", "urllib"}
            )
        )
        self.assertTrue(
            calls.isdisjoint({"open", "exec", "eval", "compile", "__import__"})
        )


if __name__ == "__main__":
    unittest.main()
