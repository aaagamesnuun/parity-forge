"""Bounded runner calibration; no production report or selected member access."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from parity_forge.dsl import canonical_json, definition_hash, parse_definition
from scripts import plan0016_pilot as pilot
from scripts.plan0016_play import PilotPlayError, play_one
from tests.test_agency_benchmark import FIXTURE_BY_ID


def fixture():
    return copy.deepcopy(FIXTURE_BY_ID["push-win-draw-loss-v1"]["definition"])


def selection():
    # Static manifest construction only. Never execute these 18-ply test wires.
    bases = []
    for first in ("A", "B"):
        raw = fixture()
        raw.update(first_player=first, max_plies=18)
        bases.append(json.loads(canonical_json(parse_definition(raw))))
    return {"selected": [{"carrier_id": "synthetic-carrier", "definitions": bases}]}


def record_for(scheduled, winner="A", status="COMPLETE"):
    # Deliberately stipulated count input, not a game trace or solver label.
    game = {key: scheduled[key] for key in
            ("definition_hash", "first_player", "policy_a", "policy_b", "seed")}
    game.update(status=status, actions=[], plies=0, winner=winner,
                terminal_reason="GOAL", nodes_by_role={"A": 0, "B": 0},
                decisions=[], censor=None, failure=None)
    if status == "SEARCH_CENSORED":
        game.update(winner=None, terminal_reason=None, censor={"role": "A"})
    return {"scheduled": scheduled, "game": game}


class PilotManifestTests(unittest.TestCase):
    def test_exact_schedule_order_and_bounds(self):
        manifest = pilot.make_manifest(selection(), {"test_source": True})
        schedule = manifest["schedule"]
        self.assertEqual(len(schedule), 160)
        expected = []
        for first in ("A", "B"):
            for orientation in pilot.D4_TRANSFORMS:
                for seed in (0, 1):
                    for pa, pb in pilot.POLICIES:
                        expected.append((first, orientation, seed, pa, pb))
        self.assertEqual([(s["first_player"], s["orientation"], s["seed"], s["policy_a"], s["policy_b"])
                          for s in schedule], expected)
        self.assertEqual([s["ordinal"] for s in schedule], list(range(160)))
        for row in schedule:
            definition = parse_definition(manifest["definitions"][row["definition_hash"]])
            self.assertEqual(definition_hash(definition), row["definition_hash"])
            self.assertEqual(definition.first_player.value, row["first_player"])

    def test_invalid_pair_envelope_and_count_rejected_without_gameplay(self):
        bad = selection()
        bad["selected"][0]["definitions"].reverse()
        with self.assertRaises(ValueError):
            pilot.make_manifest(bad, {})
        bad = selection()
        bad["selected"][0]["definitions"][0]["max_plies"] = 1
        with self.assertRaises(ValueError):
            pilot.make_manifest(bad, {})
        with self.assertRaises(ValueError):
            pilot.make_manifest({"selected": selection()["selected"] * 25}, {})

    def test_first_player_sweeps_do_not_create_a_false_positive(self):
        manifest = pilot.make_manifest(selection(), {})
        records = [record_for(s, winner=s["first_player"]) for s in manifest["schedule"]]
        result = pilot.summarize_run(manifest, records)
        self.assertEqual(result["further_diagnosis_count"], 0)
        self.assertEqual(result["complete_games"], 160)
        self.assertEqual(result["execution_status"], "SCHEDULE_COMPLETE")
        self.assertEqual(len(result["conditions"]), 2)
        self.assertEqual(len(result["conditions"][0]["profiles"][0]["orientations"]), 8)

    def test_positive_calculation_control_and_censor_prevents_triage(self):
        manifest = pilot.make_manifest(selection(), {})
        records = [record_for(s, winner="A" if s["seed"] == 0 else "B") for s in manifest["schedule"]]
        result = pilot.summarize_run(manifest, records)
        self.assertEqual(result["further_diagnosis_count"], 2)
        self.assertFalse(result["claims"]["fair_game"])
        records[0] = record_for(manifest["schedule"][0], status="SEARCH_CENSORED")
        censored = pilot.summarize_run(manifest, records)
        self.assertEqual(censored["further_diagnosis_count"], 1)
        self.assertEqual(censored["censored_games"], 1)
        self.assertEqual(censored["not_started_games"], 0)
        partial = pilot.summarize_run(manifest, records[:10])
        self.assertEqual(partial["not_started_games"], 150)
        self.assertEqual(partial["further_diagnosis_count"], 0)

    def test_wrong_ordinal_condition_or_extra_record_fails(self):
        manifest = pilot.make_manifest(selection(), {})
        row = record_for(manifest["schedule"][0])
        changed = copy.deepcopy(row)
        changed["scheduled"]["ordinal"] = 1
        with self.assertRaises(ValueError):
            pilot.summarize_run(manifest, [changed])
        changed = copy.deepcopy(row)
        changed["game"]["first_player"] = "B"
        with self.assertRaises(ValueError):
            pilot.summarize_run(manifest, [changed])
        with self.assertRaises(ValueError):
            pilot.summarize_run(manifest, [row] * 161)

    def test_registered_manifest_rejects_missing_duplicate_or_changed_schedule(self):
        original = pilot.make_manifest(selection(), {})
        for mutation in ("missing", "duplicate", "node_cap", "definition"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(original)
                if mutation == "missing":
                    changed["schedule"] = [s for s in changed["schedule"]
                                           if (s["policy_a"], s["policy_b"]) != (0, 0)]
                elif mutation == "duplicate":
                    changed["schedule"][1] = copy.deepcopy(changed["schedule"][0])
                elif mutation == "node_cap":
                    changed["max_nodes_per_role_game"] = 6000
                else:
                    next(iter(changed["definitions"].values()))["max_plies"] = 17
                for i, scheduled in enumerate(changed["schedule"]):
                    scheduled["ordinal"] = i
                records = [record_for(s, winner="A" if s["seed"] == 0 else "B")
                           for s in changed["schedule"]]
                with self.assertRaisesRegex(ValueError, "registered schedule"):
                    pilot.summarize_run(changed, records)
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory)
                    (output / "games").mkdir()
                    pilot.publish_json(output / "manifest.json", changed)
                    for row in records:
                        pilot.publish_json(output / "games" / "{:04d}.json".format(
                            row["scheduled"]["ordinal"]), row)
                    with mock.patch.object(pilot, "play_one", side_effect=AssertionError("no policy")), \
                         mock.patch.object(pilot, "select_pilot", side_effect=AssertionError("no selection")), \
                         self.assertRaisesRegex(ValueError, "registered schedule"):
                        pilot.inspect_run(output)


class PilotPublicationTests(unittest.TestCase):
    def test_atomic_no_overwrite_and_canonical_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            pilot.publish_json(path, {"example": 1})
            original = path.read_bytes()
            self.assertEqual(pilot.read_json(path), {"example": 1})
            with self.assertRaises(FileExistsError):
                pilot.publish_json(path, {"example": 2})
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(list(path.parent.glob(".pending-*")))
            damaged = Path(directory) / "damaged.json"
            pilot.publish_bytes(damaged, original.replace(b'"example":1', b'"example":2'))
            with self.assertRaises(ValueError):
                pilot.read_json(damaged)

    def _tiny_manifest(self, game_count=1):
        # The real publication/play vertical slice uses the untouched one-ply
        # fixture, not the 18-ply static constructor test above.
        raw = fixture()
        identity = definition_hash(parse_definition(raw))
        schedule = [{"ordinal": i, "carrier_index": 0, "carrier_id": "calibration",
                     "first_player": "A", "orientation": "I", "seed": i,
                     "policy_a": 1, "policy_b": 1, "definition_hash": identity}
                    for i in range(game_count)]
        return {"protocol_id": "CALIBRATION_ONLY", "source": {},
                "selection": {"selected": []}, "definitions": {identity: raw},
                "schedule": schedule, "max_nodes_per_role_game": 5000,
                "acceptance": "SYNTHETIC_INTEGRATION_ONLY"}

    def test_manifest_is_persisted_before_real_tiny_game(self):
        manifest = self._tiny_manifest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tiny"
            def checked(*args):
                self.assertEqual(pilot.read_json(output / "manifest.json"), manifest)
                return play_one(*args)
            with mock.patch.object(pilot, "play_one", side_effect=checked):
                summary = pilot.execute_manifest(output, manifest)
            self.assertEqual(summary["complete_games"], 1)
            game = pilot.read_json(output / "games" / "0000.json")["game"]
            self.assertEqual((game["winner"], game["terminal_reason"]), ("A", "GOAL"))
            self.assertTrue((output / "summary.json").is_file())
            self.assertTrue((output / "report.md").is_file())
            with mock.patch.object(pilot, "play_one", side_effect=AssertionError("must not replay policy")), \
                 mock.patch.object(pilot, "select_pilot", side_effect=AssertionError("must not select")):
                self.assertEqual(pilot.inspect_run(output), summary)
            with self.assertRaises(FileExistsError), mock.patch.object(pilot, "play_one") as no_game:
                pilot.execute_manifest(output, manifest)
            no_game.assert_not_called()

    def test_failure_prefix_is_persisted_and_stops_schedule(self):
        manifest = self._tiny_manifest(2)
        partial = play_one(fixture(), 1, 1, 0)
        partial.update(status="FAILED", failure={"type": "SyntheticFailure", "message": "test"})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "failed"
            with mock.patch.object(pilot, "play_one", side_effect=PilotPlayError("test", partial)) as call:
                summary = pilot.execute_manifest(output, manifest)
            self.assertEqual(call.call_count, 1)
            self.assertEqual(summary["execution_status"], "FAILED")
            self.assertEqual(summary["not_started_games"], 1)
            self.assertEqual(pilot.read_json(output / "games" / "0000.json")["game"], partial)
            self.assertFalse((output / "games" / "0001.json").exists())
            self.assertEqual(pilot.inspect_run(output), summary)

    def test_saved_winner_is_checked_against_replay_not_just_hash(self):
        manifest = self._tiny_manifest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "forged"
            output.mkdir()
            (output / "games").mkdir()
            pilot.publish_json(output / "manifest.json", manifest)
            game = play_one(fixture(), 1, 1, 0)
            game["winner"] = "B"
            pilot.publish_json(output / "games" / "0000.json",
                               {"scheduled": manifest["schedule"][0], "game": game})
            with self.assertRaisesRegex(ValueError, "winner differs"):
                pilot.inspect_run(output)

    def test_report_is_explicitly_diagnostic(self):
        manifest = pilot.make_manifest(selection(), {})
        summary = pilot.summarize_run(manifest, [])
        report = pilot.render_report(manifest, summary)
        self.assertIn("公平性・面白さの認定ではありません", report)
        self.assertIn("DSL由来の完全ルール", report)
        self.assertIn("summary.json", report)
        self.assertIn("```text", report)


if __name__ == "__main__":
    unittest.main()
