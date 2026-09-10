import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from parity_forge.finite_space import definition_hash, parse_definition
from parity_forge.finite_space_batch import (
    FORMAT, evaluate, load_json, play_game, run_batch, source_hashes, terminal_play, validate_manifest,
)
from test_finite_space_search import search_fixture


def manifest_fixture():
    definition = search_fixture()
    return {
        "format": FORMAT, "run_id": "synthetic-batch", "episode": 1,
        "definitions": [definition],
        "definition_hashes": [definition_hash(parse_definition(definition))],
        "origins": [{"family": "TILE", "source": "synthetic-control", "change": "hand-proved fixture"}],
        "profiles": [{"label": "control", "A": "random-v1", "B": "deny-v1", "seeds": [2, 3]}],
        "search": {"max_nodes": 30, "max_depth": 2, "game_max_nodes": 100},
        "proof": {"max_plies": 1, "max_nodes": 30},
        "limits": {"max_games": 2, "cpu_seconds": 10, "max_output_bytes": 100_000},
        "source_hashes": source_hashes(),
    }


class FiniteSpaceBatchTests(unittest.TestCase):
    def test_strict_json_and_nonfinite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for text in ('{"a":1,"a":2}', '{"n":NaN}', '{"n":Infinity}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    load_json(path)
            path.write_text('{"valid":true}')
            with self.assertRaises(ValueError):
                load_json(path, max_bytes=2)
            self.assertEqual(load_json(path, max_bytes=100), {"valid": True})
            with self.assertRaises(ValueError):
                load_json(path, max_bytes=True)

    def test_manifest_source_identity_schedule_and_budget_guards(self):
        manifest = manifest_fixture()
        self.assertEqual(len(validate_manifest(manifest)), 1)
        bad = []
        item = copy.deepcopy(manifest); item["source_hashes"] = {}; bad.append(item)
        item = copy.deepcopy(manifest); item["definition_hashes"] = ["x"]; bad.append(item)
        item = copy.deepcopy(manifest); item["limits"]["max_games"] = 1; bad.append(item)
        item = copy.deepcopy(manifest); item["search"]["max_nodes"] = True; bad.append(item)
        item = copy.deepcopy(manifest); item["profiles"][0]["A"] = "unknown"; bad.append(item)
        item = copy.deepcopy(manifest); item["profiles"][0]["seeds"] = [3, 3]; bad.append(item)
        item = copy.deepcopy(manifest); item["extra"] = 0; bad.append(item)
        item = copy.deepcopy(manifest)
        item["profiles"].append(dict(item["profiles"][0], label="renamed-duplicate"))
        item["limits"]["max_games"] = 4; bad.append(item)
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_manifest(value)

    def test_known_force_is_defect_not_a_quality_pass(self):
        manifest = manifest_fixture()
        report = evaluate(manifest, validate_manifest(manifest), lambda: False)
        self.assertEqual(report["game_count"], 0)
        self.assertEqual(report["results"][0]["disposition"], "PROVED_DEFECT")
        self.assertFalse(report["human_review_eligible"])

    def test_proof_unknown_does_not_prevent_observations_or_become_bad_game(self):
        manifest = manifest_fixture()
        manifest["proof"]["max_nodes"] = 1
        report = evaluate(manifest, validate_manifest(manifest), lambda: False)
        row = report["results"][0]
        self.assertEqual(row["proofs"][0]["status"], "UNKNOWN")
        self.assertEqual(report["game_count"], 2)
        self.assertEqual(row["disposition"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(all(game["winner"] in ("A", "B") for game in row["games"]))

    def test_game_limit_is_unknown_and_replay_preserves_partial_position(self):
        manifest = manifest_fixture()
        record = play_game(parse_definition(search_fixture()), manifest["profiles"][0], 2,
                           manifest["search"], cpu_expired=lambda: True)
        self.assertEqual(record["status"], "UNKNOWN")
        self.assertIsNone(record["winner"])
        self.assertEqual(record["plies"], 0)
        self.assertEqual(record["replay_transitions"], 0)

    def test_empty_cpu_budget_closes_slots_without_game_results(self):
        manifest = manifest_fixture()
        report = evaluate(manifest, validate_manifest(manifest), lambda: True)
        self.assertEqual(report["game_count"], 0)
        self.assertEqual(report["results"][0]["disposition"], "INSUFFICIENT_EVIDENCE")

    def test_play_is_deterministic_and_records_policy_work(self):
        manifest = manifest_fixture()
        definition = parse_definition(search_fixture())
        first = play_game(definition, manifest["profiles"][0], 3, manifest["search"])
        second = play_game(definition, manifest["profiles"][0], 3, manifest["search"])
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "COMPLETE")
        self.assertEqual(first["nodes"], sum(d["nodes"] for d in first["decisions"]))

    def test_exclusive_outputs_and_immutable_registration(self):
        manifest = manifest_fixture()
        with tempfile.TemporaryDirectory() as directory, patch(
                "parity_forge.finite_space_batch.RUN_ROOT", Path(directory)):
            output = Path(directory) / manifest["run_id"]
            report = run_batch(manifest, output)
            self.assertEqual(load_json(output / "registration.json"), manifest)
            self.assertEqual(load_json(output / "results.json"), report)
            before = (output / "results.json").read_bytes()
            with self.assertRaises(FileExistsError):
                run_batch(manifest, output)
            self.assertEqual((output / "results.json").read_bytes(), before)

    def test_failure_is_saved_without_another_run(self):
        manifest = manifest_fixture()
        with tempfile.TemporaryDirectory() as directory, patch(
                "parity_forge.finite_space_batch.RUN_ROOT", Path(directory)):
            output = Path(directory) / manifest["run_id"]
            with patch("parity_forge.finite_space_batch.evaluate", side_effect=RuntimeError("fault")):
                with self.assertRaises(RuntimeError):
                    run_batch(manifest, output)
            self.assertEqual(load_json(output / "failure.json")["status"], "FAILED_TECHNICAL")
            self.assertFalse((output / "results.json").exists())

    def test_campaign_claim_blocks_new_id_in_same_episode_and_alternate_root(self):
        manifest = manifest_fixture()
        with tempfile.TemporaryDirectory() as directory, patch(
                "parity_forge.finite_space_batch.RUN_ROOT", Path(directory)):
            with self.assertRaises(ValueError):
                run_batch(manifest, Path(directory) / "alternate-directory")
            run_batch(manifest, Path(directory) / manifest["run_id"])
            manifest["run_id"] = "another-id"
            with self.assertRaises(FileExistsError):
                run_batch(manifest, Path(directory) / manifest["run_id"])
            self.assertFalse((Path(directory) / "another-id").exists())

    def test_conservative_asymmetry_absence_is_not_invalid_game(self):
        manifest = manifest_fixture()
        wire = manifest["definitions"][0]
        wire["roles"]["A"] = copy.deepcopy(wire["roles"]["B"])
        manifest["definition_hashes"] = [definition_hash(parse_definition(wire))]
        row = evaluate(manifest, validate_manifest(manifest), lambda: False)["results"][0]
        self.assertEqual(row["disposition"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(row["not_started_games"], 2)
        self.assertIn("MECHANICAL_ASYMMETRY_NOT_ESTABLISHED", row["warnings"])

    def test_terminal_prototype_has_real_input_and_no_invented_playtest(self):
        messages = []
        state = terminal_play(parse_definition(search_fixture()),
                              input_fn=lambda prompt: "0,1", output_fn=messages.append)
        self.assertEqual(state.winner.value, "A")
        self.assertTrue(any("未認定" in message for message in messages))
        state = terminal_play(parse_definition(search_fixture()), human="both",
                              input_fn=lambda prompt: "q", output_fn=messages.append)
        self.assertIsNone(state.winner)
        self.assertEqual(state.plies, 0)

    def test_unapplied_decision_work_is_counted_on_cpu_expiry(self):
        checks = 0
        def expired():
            nonlocal checks
            checks += 1
            return checks >= 3
        manifest = manifest_fixture()
        profile = dict(manifest["profiles"][0], A="deny-v1")
        record = play_game(parse_definition(search_fixture()), profile, 2,
                           manifest["search"], expired)
        self.assertEqual(record["status"], "UNKNOWN")
        self.assertEqual(record["plies"], 0)
        self.assertEqual(record["nodes"], 1)
        self.assertFalse(record["decisions"][0]["applied"])

    def test_next_episode_requires_accepted_hashes_not_file_existence(self):
        manifest = manifest_fixture()
        with tempfile.TemporaryDirectory() as directory, patch(
                "parity_forge.finite_space_batch.RUN_ROOT", Path(directory)):
            first = Path(directory) / manifest["run_id"]
            run_batch(manifest, first)
            claim = load_json(Path(directory) / "episode-1.json")
            self.assertEqual(claim["manifest_sha256"], load_json(first / "runtime.json")["manifest_sha256"])
            (first / "results.json").write_text("{}")
            manifest.update(run_id="next-episode", episode=2)
            with self.assertRaises(ValueError):
                run_batch(manifest, Path(directory) / manifest["run_id"])
            self.assertFalse((Path(directory) / "episode-2.json").exists())


if __name__ == "__main__":
    unittest.main()
