import ast
import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from parity_forge_universe import static_census_reconstruction as reconstruction

try:  # unittest discovery imports tests as top-level modules.
    import test_static_census as census_fixture
except ModuleNotFoundError:  # package-form focused invocation.
    from tests import test_static_census as census_fixture


_REPORT_DOMAIN = b"parity-forge:plan0015:static-census-report-body:v1\0"
_SHARD_DOMAIN = b"parity-forge:plan0015:static-census-shard-summary:v1\0"


def _canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _domain_hash(domain, value):
    return hashlib.sha256(domain + _canonical(value).encode("utf-8")).hexdigest()


def _resign_report(payload):
    body = copy.deepcopy(payload)
    body.pop("report_digest", None)
    result = dict(body)
    result["report_digest"] = _domain_hash(_REPORT_DOMAIN, body)
    return _canonical(result).encode("utf-8")


def _resign_shard(summary):
    body = copy.deepcopy(summary)
    body.pop("shard_commitment", None)
    result = dict(body)
    result["shard_commitment"] = _domain_hash(_SHARD_DOMAIN, body)
    return result


class StaticCensusStoredReportReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        report = census_fixture._synthetic_complete_report()
        cls.raw = census_fixture.census.canonical_static_census_report_json_v1(
            report
        ).encode("utf-8")
        cls.payload = json.loads(cls.raw.decode("utf-8"))

    def test_honest_complete_report_reconstructs_and_returns_detached_envelope(self):
        observed = reconstruction.reconstruct_static_census_report_artifact_v1(
            self.raw
        )
        self.assertEqual(
            set(observed), {"report", "report_ref", "report_summary"}
        )
        self.assertEqual(observed["report"], self.payload)
        self.assertEqual(
            observed["report_ref"],
            {
                "byte_count": len(self.raw),
                "sha256": hashlib.sha256(self.raw).hexdigest(),
            },
        )
        self.assertEqual(
            observed["report_summary"],
            {
                "report_digest": self.payload["report_digest"],
                "setup_orbit_table_root": (
                    "f1bc82d1cfbaac9933e097aba2f4118737e19f7a190f06bc9f0a83add17c2e23"
                ),
                "skeleton_authority_root": (
                    "53221ffdbd42e4c86e9c54eadb6e0659bf71ff350dcdf0944b062ce56c3e1488"
                ),
                "ordered_shard_commitment_root": self.payload["roots"][
                    "ordered_shard_commitment_root"
                ],
                "population": self.payload["population"],
                "eligibility": {
                    "representative_eligible_count": self.payload["eligibility"][
                        "representative_eligible_count"
                    ],
                    "weighted_eligible_count": self.payload["eligibility"][
                        "weighted_eligible_count"
                    ],
                    "paired_first_player_eligible_member_count": self.payload[
                        "eligibility"
                    ]["paired_first_player_eligible_member_count"],
                },
            },
        )
        observed["report"]["population"]["skeleton_count"] = 0
        self.assertEqual(
            observed["report_summary"]["population"]["skeleton_count"], 1518
        )
        self.assertEqual(self.payload["population"]["skeleton_count"], 1518)

    def test_resigned_aggregate_and_report_root_mutations_fail(self):
        mutations = {
            "aggregate": lambda payload: payload["population"].__setitem__(
                "skeleton_count", 1517
            ),
            "root": lambda payload: payload["roots"].__setitem__(
                "ordered_shard_commitment_root", "0" * 64
            ),
            "authority": lambda payload: payload["authorities"][
                "setup_orbit_table"
            ].__setitem__("descriptor_root", "0" * 64),
        }
        for label, mutate in mutations.items():
            payload = copy.deepcopy(self.payload)
            mutate(payload)
            with self.subTest(label=label):
                with self.assertRaises(reconstruction.StaticCensusReconstructionError):
                    reconstruction.reconstruct_static_census_report_artifact_v1(
                        _resign_report(payload)
                    )

    def test_digest_and_order_mutations_fail(self):
        digest = copy.deepcopy(self.payload)
        digest["report_digest"] = "0" * 64
        with self.assertRaises(reconstruction.StaticCensusReconstructionError):
            reconstruction.reconstruct_static_census_report_artifact_v1(
                _canonical(digest).encode("utf-8")
            )

        order = copy.deepcopy(self.payload)
        order["skeleton_shards"][0], order["skeleton_shards"][1] = (
            order["skeleton_shards"][1],
            order["skeleton_shards"][0],
        )
        with self.assertRaises(reconstruction.StaticCensusReconstructionError):
            reconstruction.reconstruct_static_census_report_artifact_v1(
                _resign_report(order)
            )

    def test_shard_reason_contact_supply_work_and_exact_types_fail(self):
        def reason(payload):
            shard = payload["skeleton_shards"][0]
            shard["eligibility"]["reason_combinations"][0][
                "representative_count"
            ] += 1
            payload["skeleton_shards"][0] = _resign_shard(shard)

        def contact(payload):
            shard = payload["skeleton_shards"][0]
            shard["contact"]["SEPARATED"]["representative_count"] += 1
            payload["skeleton_shards"][0] = _resign_shard(shard)

        def supply(payload):
            shard = payload["skeleton_shards"][0]
            shard["eligible_supply_by_count_pair_and_contact"][0][
                "representative_count"
            ] += 1
            payload["skeleton_shards"][0] = _resign_shard(shard)

        def work(payload):
            shard = payload["skeleton_shards"][0]
            shard["work_extrema"]["A"]["state_weight_sum"]["maximum"] = 115195
            payload["skeleton_shards"][0] = _resign_shard(shard)

        def boolean_alias(payload):
            shard = payload["skeleton_shards"][0]
            shard["setup_orbit"]["representative_count"] = True
            payload["skeleton_shards"][0] = _resign_shard(shard)

        for label, mutate in {
            "reason": reason,
            "contact": contact,
            "supply": supply,
            "work": work,
            "bool-int": boolean_alias,
        }.items():
            payload = copy.deepcopy(self.payload)
            mutate(payload)
            with self.subTest(label=label):
                with self.assertRaises(reconstruction.StaticCensusReconstructionError):
                    reconstruction.reconstruct_static_census_report_artifact_v1(
                        _resign_report(payload)
                    )

    def test_noncanonical_duplicate_float_unknown_and_nonbytes_inputs_fail(self):
        hostile = (
            self.raw + b"\n",
            b'{"x":1,"x":2}',
            b'{"x":1.0}',
            b'{"unknown":1}',
        )
        for raw in hostile:
            with self.subTest(raw=raw[:32]):
                with self.assertRaises(reconstruction.StaticCensusReconstructionError):
                    reconstruction.reconstruct_static_census_report_artifact_v1(raw)
        for raw in (bytearray(self.raw[:1]), memoryview(self.raw[:1]), "{}"):
            with self.subTest(type=type(raw).__name__):
                with self.assertRaises(TypeError):
                    reconstruction.reconstruct_static_census_report_artifact_v1(raw)

    def test_fixed_resource_caps(self):
        self.assertEqual(reconstruction.STATIC_CENSUS_REPORT_MAX_BYTES_V1, 268435456)
        self.assertEqual(
            reconstruction.STATIC_CENSUS_REPORT_MAX_JSON_NODES_V1, 5_000_000
        )
        self.assertEqual(reconstruction.STATIC_CENSUS_REPORT_MAX_JSON_DEPTH_V1, 32)
        self.assertLess(len(self.raw), reconstruction.STATIC_CENSUS_REPORT_MAX_BYTES_V1)

    def test_joint_orbit_weight_inventory_is_exact(self):
        histogram = ((1, 20), (2, 225), (4, 1582))
        individually_feasible_but_jointly_impossible = (
            (86, 152),
            (1330, 5301),
            (411, 1345),
        )
        for bucket in individually_feasible_but_jointly_impossible:
            self.assertTrue(
                reconstruction._weight_pair_is_feasible(*bucket, histogram)
            )
        self.assertFalse(
            reconstruction._bucket_partition_is_feasible(
                individually_feasible_but_jointly_impossible,
                histogram,
                consume_all=True,
            )
        )

        _, pair_tables = reconstruction._build_setup_descriptor()
        for group_index, group_table in enumerate(pair_tables):
            for pair_index, pair_histogram in enumerate(group_table):
                self.assertEqual(
                    sum(weight * count for weight, count in pair_histogram),
                    reconstruction._COUNT_PAIR_SUPPLIES[pair_index],
                    (group_index, pair_index),
                )

    def test_public_boundary_rejects_rebound_private_helper(self):
        with mock.patch.object(reconstruction, "_build_setup_descriptor", lambda: {}):
            with self.assertRaises(reconstruction.StaticCensusReconstructionError):
                reconstruction.reconstruct_static_census_report_artifact_v1(self.raw)
        with mock.patch.object(
            reconstruction,
            "_STATIC_REPORT_BODY_DOMAIN",
            b"attacker-controlled-domain\0",
        ):
            with self.assertRaises(reconstruction.StaticCensusReconstructionError):
                reconstruction.reconstruct_static_census_report_artifact_v1(self.raw)
        with mock.patch.object(
            reconstruction, "globals", lambda: {}, create=True
        ):
            with self.assertRaises(reconstruction.StaticCensusReconstructionError):
                reconstruction.reconstruct_static_census_report_artifact_v1(self.raw)


class StaticCensusReconstructionCapabilityTests(unittest.TestCase):
    def test_source_has_only_standard_library_imports(self):
        source_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "parity_forge_universe"
            / "static_census_reconstruction.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.add(node.module.split(".")[0])
        self.assertEqual(
            imports,
            {"__future__", "copy", "hashlib", "itertools", "json", "math", "typing"},
        )

    def test_isolated_import_does_not_load_calculator_or_legacy_package(self):
        source_root = str(Path(__file__).resolve().parents[1] / "src")
        script = """
import sys
import parity_forge_universe.static_census_reconstruction as module
assert 'parity_forge' not in sys.modules
assert 'parity_forge_universe.static_census' not in sys.modules
assert module.STATIC_CENSUS_REPORT_MAX_BYTES_V1 == 268435456
"""
        process = subprocess.run(
            [sys.executable, "-I", "-c", script],
            cwd=source_root,
            env={"PYTHONPATH": source_root},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if process.returncode != 0 and "No module named" in process.stderr:
            script = "import sys;sys.path.insert(0,{!r});{}".format(
                source_root, script
            )
            process = subprocess.run(
                [sys.executable, "-I", "-c", script],
                cwd=source_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
