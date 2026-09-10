"""Runner plumbing only: solve is always mocked, never run on the original."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from parity_forge import cut_choose_potential_batch as batch
from parity_forge.cut_choose import definition_hash, definition_to_dict, original_definition


class CutChoosePotentialBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in batch.SOURCE_PATHS + (batch.SOURCE_CHAT,):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic pin fixture\n", encoding="utf-8")
        definition = original_definition()
        self.manifest = {"format": batch.FORMAT, "id": "harness-v1",
                         "definition": definition_to_dict(definition),
                         "definition_sha256": definition_hash(definition),
                         "source_chat_sha256": hashlib.sha256(
                             (self.root / batch.SOURCE_CHAT).read_bytes()).hexdigest(),
                         "source_pins": batch.source_hashes(self.root),
                         "query": "EXACT_INITIAL_WINNER",
                         "limits": {"nodes": 10, "transitions": 100, "proof_arcs": 100,
                                    "cpu_seconds": 10, "output_bytes": 4096}}
        self.path = self.root / "manifest.json"
        self.output = self.root / "output"
        self.unknown = {"status": "UNKNOWN", "winner": None, "reason": "NODE_LIMIT",
                        "nodes": 10, "transitions": 20, "proof_arcs": 0, "proof": None,
                        "cut_count": 3, "potential_checks": 10, "potential_leaves": 2}
        self.solver = self.enter_patch("solve", return_value=self.unknown)
        self.checker = self.enter_patch("verify_proof")
        self.enter_patch("_git_provenance", return_value={"head": "fixture", "dirty": True})

    def enter_patch(self, name, **kwargs):
        patcher = patch.object(batch, name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def write_manifest(self, manifest=None):
        self.path.write_text(json.dumps(self.manifest if manifest is None else manifest),
                             encoding="utf-8")

    def run_harness(self):
        self.write_manifest()
        return batch.run(self.path, self.output, repo_root=self.root)

    def test_unknown_is_immutable_and_receipted(self):
        self.assertEqual(self.run_harness(), self.unknown)
        directory = self.output / self.manifest["id"]
        raw = (directory / "result.json").read_bytes()
        receipt = json.loads((directory / "receipt.json").read_text())
        self.assertEqual(receipt["result_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertIsNone(receipt["proof_check"])
        self.assertLessEqual(sum(p.stat().st_size for p in directory.iterdir()), 4096)
        with self.assertRaises(FileExistsError):
            batch.run(self.path, self.output, repo_root=self.root)
        self.solver.assert_called_once()
        self.checker.assert_not_called()

    def test_manifest_schema_and_bounds(self):
        variants = []
        for key, value in (("extra", 1), ("id", "../escape"),
                           ("query", "OTHER"), ("definition_sha256", "0" * 64)):
            item = copy.deepcopy(self.manifest)
            item[key] = value
            variants.append(item)
        for key, value in (("nodes", True), ("nodes", -1), ("nodes", 300001),
                           ("transitions", 6000001), ("proof_arcs", 1000001),
                           ("cpu_seconds", True), ("cpu_seconds", 0),
                           ("cpu_seconds", float("inf")), ("cpu_seconds", 1801),
                           ("output_bytes", 4095), ("output_bytes", 16777217)):
            item = copy.deepcopy(self.manifest)
            item["limits"][key] = value
            variants.append(item)
        item = copy.deepcopy(self.manifest)
        item["definition"]["id"] = "renamed-original"
        variants.append(item)
        item = copy.deepcopy(self.manifest)
        item["source_pins"]["arbitrary.py"] = "0" * 64
        variants.append(item)
        for item in variants:
            with self.subTest(item=item), self.assertRaises(ValueError):
                batch.validate_manifest(item, self.root)
        self.solver.assert_not_called()

    def test_json_duplicate_oversize_and_constants(self):
        for raw in ('{"id":1,"id":2}', '{"limits":{"x":1,"x":2}}',
                    '{"bad":NaN}', " " * 65537):
            self.path.write_text(raw, encoding="utf-8")
            with self.subTest(raw=raw[:50]), self.assertRaises(ValueError):
                batch.load_manifest(self.path)
        self.solver.assert_not_called()

    def test_drift_and_different_graph_rejected(self):
        item = copy.deepcopy(self.manifest)
        item["definition"]["edges"] = item["definition"]["edges"][:-2]
        with self.assertRaises(ValueError):
            batch.validate_manifest(item, self.root)
        for name in (batch.SOURCE_PATHS[0], batch.SOURCE_CHAT):
            path = self.root / name
            old = path.read_bytes()
            path.write_bytes(b"drift")
            with self.assertRaises(ValueError):
                batch.validate_manifest(self.manifest, self.root)
            path.write_bytes(old)
        self.solver.assert_not_called()

    def test_exception_preserves_claim_without_result(self):
        self.solver.side_effect = RuntimeError("harness exception")
        with self.assertRaises(RuntimeError):
            self.run_harness()
        directory = self.output / self.manifest["id"]
        self.assertTrue((directory / "claim.json").exists())
        self.assertTrue((directory / "failure.json").exists())
        self.assertFalse((directory / "result.json").exists())

    def test_interrupt_does_not_invent_unknown(self):
        self.solver.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_harness()
        directory = self.output / self.manifest["id"]
        self.assertTrue((directory / "claim.json").exists())
        self.assertFalse((directory / "result.json").exists())
        self.assertFalse((directory / "failure.json").exists())

    def test_cpu_limit_preserves_observed_counts(self):
        now = [0.0]
        self.enter_patch("time", process_time=lambda: now[0])
        complete = dict(self.unknown, status="COMPLETE", winner="B", reason="PROVED", proof={})
        def delayed(*args, **kwargs):
            now[0] = 11.0
            return complete
        self.solver.side_effect = delayed
        result = self.run_harness()
        self.assertEqual(result["reason"], "CPU_LIMIT")
        self.assertEqual(result["nodes"], 10)
        self.assertIsNone(result["winner"])
        self.checker.assert_not_called()

    def test_complete_requires_independent_check(self):
        self.solver.return_value = dict(self.unknown, status="COMPLETE", winner="B",
                                        reason="PROVED", proof={})
        self.checker.side_effect = ValueError("invalid proof fixture")
        with self.assertRaises(ValueError):
            self.run_harness()
        self.checker.assert_called_once()
        self.assertFalse((self.output / self.manifest["id"] / "result.json").exists())

    def test_result_byte_limit_is_not_a_winner(self):
        self.solver.return_value = dict(self.unknown, status="COMPLETE", winner="B",
                                        reason="PROVED", proof={"padding": "x" * 4096})
        self.checker.return_value = {"status": "PASS", "winner": "B", "nodes": 1, "arcs": 0}
        result = self.run_harness()
        self.assertEqual(result["reason"], "RESULT_BYTE_LIMIT")
        self.assertIsNone(result["winner"])
        self.assertIsNone(result["proof"])
        self.assertEqual(result["transitions"], 20)

    def test_checker_budget_is_unknown_not_failure(self):
        self.solver.return_value = dict(self.unknown, status="COMPLETE", winner="B",
                                        reason="PROVED", proof={})
        self.checker.side_effect = batch.BudgetExceeded("CPU_LIMIT")
        result = self.run_harness()
        self.assertEqual(result["reason"], "CPU_LIMIT")
        self.assertIsNone(result["winner"])

    def test_drift_during_computation_preserves_failure(self):
        def drift(*args, **kwargs):
            (self.root / batch.SOURCE_PATHS[0]).write_bytes(b"late drift")
            return self.unknown
        self.solver.side_effect = drift
        with self.assertRaises(ValueError):
            self.run_harness()
        directory = self.output / self.manifest["id"]
        self.assertTrue((directory / "failure.json").exists())
        self.assertFalse((directory / "result.json").exists())

    def test_first_solver_budget_reason_survives_late_cpu_limit(self):
        now = [0.0]
        self.enter_patch("time", process_time=lambda: now[0])
        def delayed(*args, **kwargs):
            now[0] = 11.0
            return self.unknown
        self.solver.side_effect = delayed
        self.assertEqual(self.run_harness()["reason"], "NODE_LIMIT")

    def test_extra_potential_counters_are_bounded(self):
        for key, value in (("cut_count", 1025), ("cut_count", True),
                           ("potential_checks", 11), ("potential_leaves", 11),
                           ("potential_checks", -1), ("potential_leaves", 1.0)):
            result = dict(self.unknown, **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                batch._validate_result(result, self.manifest["limits"])
        old = dict(self.unknown)
        del old["cut_count"]
        with self.assertRaises(ValueError):
            batch._validate_result(old, self.manifest["limits"])

    def test_old_manifest_format_and_wrong_pin_inventory_rejected(self):
        old = copy.deepcopy(self.manifest)
        old["format"] = "parity-forge:cut-choose-experiment:v1"
        with self.assertRaises(ValueError):
            batch.validate_manifest(old, self.root)
        self.assertEqual(len(batch.SOURCE_PATHS), 7)
        for name in batch.SOURCE_PATHS:
            missing = copy.deepcopy(self.manifest)
            del missing["source_pins"][name]
            with self.subTest(name=name), self.assertRaises(ValueError):
                batch.validate_manifest(missing, self.root)

    def test_cli_failure_is_nonzero(self):
        with patch.object(batch, "run", side_effect=RuntimeError("fixture")):
            self.assertEqual(batch.main(["--manifest", "x", "--output", "y"]), 1)


if __name__ == "__main__":
    unittest.main()
