"""Runner conformance; all traversed DSL is the production-excluded E/E region."""

import copy
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from parity_forge.dsl import canonical_json, parse_definition
from parity_forge.engine import initial_state
from parity_forge_universe import schema_v4_compiler as compiler
from parity_forge_universe import typed_occupancy as universe
from scripts import plan0018_pilot as pilot
from scripts.plan0018_selection import GOAL_PAIRS


def selection():
    # E/E is excluded semantically, regardless of names, D4 or role exchange.
    raw = {"schema_version": 4, "name": "excluded-ee-calibration", "board_size": 3,
           "max_plies": 18, "first_player": "A",
           "roles": {
               "A": {"action": {"kind": "CONVERT", "piece": "a",
                                "vectors": [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]]},
                     "goal": {"kind": "ELIMINATE", "piece": "b"}},
               "B": {"action": {"kind": "MOVE_CAPTURE", "piece": "b",
                                "vectors": [[-1, 0], [0, -1], [0, 1], [1, 0]]},
                     "goal": {"kind": "ELIMINATE", "piece": "a"}}},
           "initial_pieces": [{"owner": "A", "piece": "a", "position": [1, 1]},
                              {"owner": "B", "piece": "b", "position": [1, 0]}]}
    bases = [json.loads(canonical_json(parse_definition(dict(raw, first_player=first)))) for first in ("A", "B")]
    return {"selected": [{"carrier_id": "synthetic-ee", "definitions": bases,
                          "converter_role": "A", "opponent_role": "B",
                          "no_draw_certificates": [pilot.certify_no_draw(raw) for raw in bases]}]}


def source():
    return {"git_commit": "synthetic", "plan": pilot.PLAN, "git_dirty": False,
            "source_sha256": {pilot.PLAN: "synthetic-plan", "scripts/test.py": "synthetic-source"}}


def attempt():
    return {"protocol_id": pilot.PROTOCOL, "source": source(), "input_sha256": {}}


def count_record(scheduled, winner="A", status="COMPLETE"):
    # Stipulated count input only: not a played trace or an exact label.
    game = {key: scheduled[key] for key in
            ("definition_hash", "first_player", "policy_a", "policy_b", "seed")}
    game.update(status=status, actions=[], plies=0, winner=winner,
                terminal_reason="GOAL", nodes_by_role={"A": 0, "B": 0},
                max_nodes_per_role=5000, decisions=[], censor=None, failure=None)
    if status == "SEARCH_CENSORED":
        game.update(winner=None, terminal_reason=None, censor={"role": "A"})
    return {"scheduled": scheduled, "game": game, "status": pilot._game_status(game, scheduled)}


def count_exact(scheduled, status="COMPLETE"):
    if status == "UNKNOWN_CENSORED":
        return {"scheduled": scheduled, "status": status, "actual_result": None, "verification": None,
                "error": {"type": "SolveBudgetExceeded", "searched_states": 100000, "max_states": 100000}}
    return {"scheduled": scheduled, "status": status, "error": None,
            "actual_result": {"forced_result": "A_WIN", "value_for_a": 1, "principal_variation": [],
                              "principal_variation_plies": 0, "terminal_reason": "GOAL", "searched_states": 1, "cache_hits": 0},
            "verification": {"external_replay_count": 1, "source_unchanged": True,
                             "terminal_state": {"ply": 0, "outcome": {"winner": "A", "reason": "GOAL"}}}}


class ManifestTests(unittest.TestCase):
    def test_executed_fixture_is_rejected_by_production_semantic_firewall(self):
        self.assertNotIn(("ELIMINATE", "ELIMINATE"), GOAL_PAIRS)
        skeleton = universe.parse_profiled_skeleton({"universe_version": 1, "roles": {
            "A": {"action_primitive": "CONVERT", "goal_primitive": "ELIMINATE",
                  "vector_profile": "KING_8", "target_edges": []},
            "B": {"action_primitive": "MOVE_CAPTURE", "goal_primitive": "ELIMINATE",
                  "vector_profile": "ORTHOGONAL_4", "target_edges": []}}})
        with self.assertRaisesRegex(ValueError, "Plan-0013"):
            compiler.TypedSetupCarrierV1(1, skeleton, compiler.TypedSetupV1(1, ((1, 1),), ((1, 0),)))
        self.assertEqual([r["roles"][p]["goal"]["kind"] for r in selection()["selected"][0]["definitions"]
                          for p in ("A", "B")], ["ELIMINATE"] * 4)

    def test_complete_schedule_and_hard_ceiling(self):
        manifest = pilot.make_manifest(selection(), attempt())
        expected = [(first, orientation, seed, pa, pb) for first in ("A", "B")
                    for orientation in pilot.D4_TRANSFORMS for seed in (0, 1) for pa, pb in pilot.POLICIES]
        self.assertEqual([(s["first_player"], s["orientation"], s["seed"], s["policy_a"], s["policy_b"])
                          for s in manifest["schedule"]], expected)
        self.assertEqual([s["ordinal"] for s in manifest["schedule"]], list(range(160)))
        self.assertEqual([s["first_player"] for s in manifest["exact_schedule"]], ["A", "B"])
        self.assertTrue(all(s["max_states"] == 100000 for s in manifest["exact_schedule"]))
        many = {"selected": selection()["selected"] * 16}
        self.assertEqual(len(pilot.make_manifest(many, attempt())["schedule"]), 2560)
        with self.assertRaises(ValueError):
            pilot.make_manifest({"selected": many["selected"] + selection()["selected"]}, attempt())

    def test_certificates_first_player_and_registered_manifest_reconstruct(self):
        for mutation in ("certificate", "pair", "mechanics"):
            bad = selection()
            carrier = bad["selected"][0]
            if mutation == "certificate":
                carrier["no_draw_certificates"][0]["max_natural_plies"] += 1
            elif mutation == "pair":
                carrier["definitions"].reverse()
            else:
                carrier["definitions"][1]["initial_pieces"][0]["position"] = [0, 0]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                pilot.make_manifest(bad, attempt())
        for mutation in ("missing_profile", "duplicate", "node_cap", "definition", "exact_cap", "protocol", "boolean_seed"):
            manifest = pilot.make_manifest(selection(), attempt())
            if mutation == "missing_profile":
                manifest["schedule"] = [s for s in manifest["schedule"] if s["policy_a"] != 0]
            elif mutation == "duplicate":
                manifest["schedule"][1] = manifest["schedule"][0]
            elif mutation == "node_cap":
                manifest["max_nodes_per_role_game"] = 6000
            elif mutation == "exact_cap":
                manifest["exact_schedule"][0]["max_states"] = 200000
            elif mutation == "protocol":
                manifest["protocol_id"] = "unregistered"
            elif mutation == "boolean_seed":
                manifest["schedule"][0]["seed"] = False
            else:
                next(iter(manifest["definitions"].values()))["max_plies"] = 17
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                pilot.summarize_run(manifest, [], [])

    def test_fixed_first_sweeps_and_positive_nonvacuous_control(self):
        manifest = pilot.make_manifest(selection(), attempt())
        exact = [count_exact(s) for s in manifest["exact_schedule"]]
        rows = [count_record(s, s["first_player"]) for s in manifest["schedule"]]
        self.assertEqual(pilot.summarize_run(manifest, rows, exact)["further_diagnosis_count"], 0)
        rows = [count_record(s, "A" if s["seed"] == 0 else "B") for s in manifest["schedule"]]
        summary = pilot.summarize_run(manifest, rows, exact)
        self.assertEqual(summary["further_diagnosis_count"], 2)
        self.assertFalse(any(summary["claims"].values()))
        self.assertEqual(len(summary["conditions"][0]["profiles"][0]["orientations"]), 8)
        exact[0] = count_exact(manifest["exact_schedule"][0], "UNKNOWN_CENSORED")
        self.assertEqual(pilot.summarize_run(manifest, rows, exact)["further_diagnosis_count"], 1)
        rows[80] = count_record(manifest["schedule"][80], status="SEARCH_CENSORED")
        self.assertEqual(pilot.summarize_run(manifest, rows, exact)["further_diagnosis_count"], 0)

    def test_order_condition_budget_and_proof_failure_boundaries(self):
        manifest = pilot.make_manifest(selection(), attempt())
        row = count_record(manifest["schedule"][0])
        for key, value in (("first_player", "B"), ("max_nodes_per_role", 6000)):
            bad = copy.deepcopy(row)
            bad["game"][key] = value
            with self.assertRaises(ValueError):
                pilot.summarize_run(manifest, [bad], [])
        with self.assertRaises(ValueError):
            pilot.summarize_run(manifest, [row, row], [])
        with self.assertRaises(ValueError):
            pilot.summarize_run(manifest, [], [count_exact(manifest["exact_schedule"][0])])
        for winner, plies in ((None, 0), ("A", 2)):
            game = dict(row["game"], winner=winner, plies=plies)
            self.assertEqual(pilot._game_status(game, row["scheduled"]), "PROOF_INTEGRITY_FAILURE")
        game = dict(row["game"], status="SEARCH_CENSORED", plies=1)
        self.assertEqual(pilot._game_status(game, row["scheduled"]), "PROOF_INTEGRITY_FAILURE")


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.output = self.repo / "run"
        for relative in (pilot.REPORT, pilot.PREVIOUS):
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic input, not production evidence")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(pilot, "source_snapshot", return_value=source()))
        def select(*args):
            self.assertTrue((self.output / "attempt.json").is_file())
            self.assertFalse((self.output / "manifest.json").exists())
            return selection()
        self.selector = self.stack.enter_context(mock.patch.object(pilot, "select_pilot", side_effect=select))

    def run_pilot(self):
        return pilot.run_pilot(self.repo, self.output)

    def test_vertical_slice_publication_order_and_single_external_exact_replay(self):
        real_play, real_solve = pilot.play_one, pilot.solve_game
        def play(*args):
            self.assertTrue((self.output / "manifest.json").is_file())
            self.assertFalse(list((self.output / "exact").glob("*-attempt.json")))
            return real_play(*args)
        calls = []
        def solve(*args, **kwargs):
            self.assertEqual(len(list((self.output / "games").glob("*.json"))), 160)
            self.assertTrue((self.output / "exact" / f"{len(calls):04d}-attempt.json").is_file())
            calls.append(args[0].first_player.value)
            return real_solve(*args, **kwargs)
        with mock.patch.object(pilot, "play_one", side_effect=play), \
             mock.patch.object(pilot, "solve_game", side_effect=solve), \
             mock.patch.object(pilot, "replay_dicts", wraps=pilot.replay_dicts) as replay:
            summary = self.run_pilot()
            self.assertEqual(replay.call_count, 2)
        self.assertEqual(calls, ["A", "B"])
        self.assertEqual(summary["execution_status"], "SCHEDULE_COMPLETE")
        self.assertEqual(summary["game_statuses"], {"COMPLETE": 160})
        self.assertEqual(summary["exact_statuses"], {"COMPLETE": 2})
        self.assertEqual(summary["further_diagnosis_count"], 0)
        with mock.patch.object(pilot, "select_pilot", side_effect=AssertionError("no selector")), \
             mock.patch.object(pilot, "solve_game", side_effect=AssertionError("no solve")), \
             mock.patch.object(pilot, "play_one", side_effect=AssertionError("no policy")), \
             mock.patch.object(pilot, "replay_dicts", wraps=pilot.replay_dicts) as replay:
            self.assertEqual(pilot.inspect_run(self.output), summary)
            self.assertEqual(replay.call_count, 160)  # Gameplay only, not two exact PVs again.
            with self.assertRaises(FileExistsError):
                self.run_pilot()

    def test_preselection_failure_is_recorded_and_never_retried(self):
        self.selector.side_effect = RuntimeError("synthetic selection failure")
        with mock.patch.object(pilot, "play_one") as play, mock.patch.object(pilot, "solve_game") as solve:
            summary = self.run_pilot()
        self.assertEqual(summary["execution_status"], "FAILED")
        play.assert_not_called()
        solve.assert_not_called()
        self.assertEqual(pilot.inspect_run(self.output), summary)
        with self.assertRaises(FileExistsError):
            self.run_pilot()
        self.assertEqual(self.selector.call_count, 1)

    def test_selection_partial_prefix_survives_without_becoming_a_manifest(self):
        prefix = {"completed": False, "slots": [{"attempts": [{"attempt": 0, "rejection": "synthetic"}]}],
                  "selected": [], "current_attempt": {"attempt": 1, "compiled": selection()}}
        self.selector.side_effect = pilot.SelectionError("synthetic partial selection", prefix)
        with mock.patch.object(pilot, "play_one") as play, mock.patch.object(pilot, "solve_game") as solve:
            summary = self.run_pilot()
        play.assert_not_called()
        solve.assert_not_called()
        self.assertEqual(pilot.read_json(self.output / "selection-failure-prefix.json"), prefix)
        self.assertFalse((self.output / "manifest.json").exists())
        self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_failed_game_keeps_prefix_and_stops_before_exact(self):
        real_play = pilot.play_one
        def failed(*args):
            game = real_play(*args)
            game.update(status="FAILED", failure={"type": "Synthetic", "message": "failure"})
            raise pilot.PilotPlayError("test", game)
        with mock.patch.object(pilot, "play_one", side_effect=failed) as play, mock.patch.object(pilot, "solve_game") as solve:
            summary = self.run_pilot()
        self.assertEqual(play.call_count, 1)
        solve.assert_not_called()
        self.assertEqual(summary["game_statuses"], {"FAILED": 1})
        self.assertEqual(summary["not_started_games"], 159)
        self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_draw_is_proof_failure_preserving_original_game_not_a_draw_count(self):
        real_play = pilot.play_one
        def draw(*args):
            return dict(real_play(*args), winner=None, terminal_reason="PLY_LIMIT")
        with mock.patch.object(pilot, "play_one", side_effect=draw) as play, mock.patch.object(pilot, "solve_game") as solve:
            summary = self.run_pilot()
        self.assertEqual(play.call_count, 1)
        solve.assert_not_called()
        self.assertEqual(summary["game_statuses"], {"PROOF_INTEGRITY_FAILURE": 1})
        raw = pilot.read_json(self.output / "games" / "0000.json")
        self.assertEqual(raw["game"]["status"], "COMPLETE")
        self.assertIsNone(raw["game"]["winner"])
        with self.assertRaisesRegex(ValueError, "terminal differs"):
            pilot.inspect_run(self.output)

    def test_search_censor_continues_to_all_exact_calls(self):
        real_play = pilot.play_one
        calls = []
        def play(raw, *args):
            game = real_play(raw, *args)
            calls.append(1)
            if len(calls) == 1:
                game.update(status="SEARCH_CENSORED", actions=[], plies=0, winner=None, terminal_reason=None,
                            decisions=[], censor={"role": "A"}, nodes_by_role={"A": 0, "B": 0},
                            state_after_prefix=initial_state(parse_definition(raw)).to_dict())
            return game
        with mock.patch.object(pilot, "play_one", side_effect=play):
            summary = self.run_pilot()
        self.assertEqual(summary["game_statuses"], {"SEARCH_CENSORED": 1, "COMPLETE": 159})
        self.assertEqual(summary["exact_statuses"], {"COMPLETE": 2})
        self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_exact_budget_unknown_continues_without_replay(self):
        real_solve = pilot.solve_game
        calls = []
        def solve(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise pilot.SolveBudgetExceeded(100000, 100000)
            return real_solve(*args, **kwargs)
        with mock.patch.object(pilot, "solve_game", side_effect=solve), \
             mock.patch.object(pilot, "replay_dicts", wraps=pilot.replay_dicts) as replay:
            summary = self.run_pilot()
            self.assertEqual(replay.call_count, 1)
        self.assertEqual(summary["exact_statuses"], {"UNKNOWN_CENSORED": 1, "COMPLETE": 1})
        self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_unexpected_exact_failure_preserves_attempt_and_stops(self):
        with mock.patch.object(pilot, "solve_game", side_effect=RuntimeError("synthetic exact failure")) as solve:
            summary = self.run_pilot()
        self.assertEqual(solve.call_count, 1)
        self.assertEqual(summary["exact_statuses"], {"FAILED": 1})
        self.assertEqual(summary["exact_attempts"], 1)
        self.assertEqual(summary["unrecorded_exact"], 1)
        self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_invalid_exact_counter_stops_before_second_call_preserving_result(self):
        real_solve = pilot.solve_game
        def solve(*args, **kwargs):
            wire = real_solve(*args, **kwargs).to_dict()
            wire["searched_states"] = 100001
            return SimpleNamespace(to_dict=lambda: wire)
        with mock.patch.object(pilot, "solve_game", side_effect=solve) as call:
            summary = self.run_pilot()
        self.assertEqual(call.call_count, 1)
        self.assertEqual(summary["exact_statuses"], {"FAILED": 1})
        record = pilot.read_json(self.output / "exact" / "0000-result.json")
        self.assertEqual(record["actual_result"]["searched_states"], 100001)
        self.assertEqual(record["verification"]["external_replay_count"], 1)
        self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_post_game_source_drift_stops_before_exact(self):
        changed = source()
        changed["source_sha256"]["scripts/test.py"] = "changed"
        with mock.patch.object(pilot, "source_snapshot", side_effect=[source(), source(), changed]), \
             mock.patch.object(pilot, "solve_game") as solve:
            summary = self.run_pilot()
        solve.assert_not_called()
        self.assertEqual(summary["game_statuses"], {"COMPLETE": 160})
        self.assertEqual(summary["execution_status"], "FAILED")
        self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_saved_exact_verification_cannot_change_and_is_not_replayed(self):
        summary = self.run_pilot()
        self.assertEqual(summary["execution_status"], "SCHEDULE_COMPLETE")
        real_read = pilot.read_json
        def changed(path):
            value = real_read(path)
            if path.name == "0000-result.json":
                value["verification"]["external_replay_count"] = 2
            return value
        with mock.patch.object(pilot, "read_json", side_effect=changed), \
             mock.patch.object(pilot, "replay_dicts", side_effect=AssertionError("no exact replay")), \
             self.assertRaisesRegex(ValueError, "verification disagrees"):
            pilot.inspect_run(self.output)

    def test_exact_draw_or_bound_contradiction_is_persisted_as_proof_failure(self):
        # Stipulated adapter faults, not engine-generated draws/new games.
        scheduled = pilot.make_manifest(selection(), attempt())["exact_schedule"][0]
        raw = selection()["selected"][0]["definitions"][0]
        for value, forced, plies, reason in ((0, "DRAW", 0, "PLY_LIMIT"), (1, "A_WIN", 2, "GOAL")):
            directory = self.repo / forced
            directory.mkdir()
            winner = None if value == 0 else SimpleNamespace(value="A")
            terminal = SimpleNamespace(terminal=True, ply=plies,
                outcome=SimpleNamespace(winner=winner, reason=reason),
                to_dict=lambda: {"ply": plies, "outcome": {"winner": None if value == 0 else "A", "reason": reason}})
            wire = {"value_for_a": value, "forced_result": forced, "principal_variation": [{}] * plies,
                    "principal_variation_plies": plies, "terminal_reason": reason, "searched_states": 1, "cache_hits": 0}
            with mock.patch.object(pilot, "solve_game", return_value=SimpleNamespace(to_dict=lambda: wire)), \
                 mock.patch.object(pilot, "replay_dicts", return_value=terminal) as replay:
                record = pilot._exact_one(directory, scheduled, raw, lambda: None, source())
            self.assertEqual(replay.call_count, 1)
            self.assertEqual(record["status"], "PROOF_INTEGRITY_FAILURE")
            self.assertEqual(record["actual_result"], wire)
            pilot._check_exact(record)
            self.assertEqual(pilot.read_json(directory / "0000-result.json"), record)

    def test_interrupted_exact_result_publication_retains_one_unretried_attempt(self):
        real_publish = pilot.publish_json
        def publish(path, value):
            if path.name == "0000-result.json":
                raise OSError("synthetic publication fault")
            return real_publish(path, value)
        with mock.patch.object(pilot, "publish_json", side_effect=publish), \
             mock.patch.object(pilot, "solve_game", wraps=pilot.solve_game) as solve:
            summary = self.run_pilot()
        self.assertEqual(solve.call_count, 1)
        self.assertEqual(summary["exact_attempts"], 1)
        self.assertEqual(summary["exact_statuses"], {})
        self.assertEqual(summary["execution_status"], "FAILED")
        self.assertEqual([c["exact_status"] for c in summary["conditions"]], ["ATTEMPTED_NO_RESULT", "NOT_STARTED"])
        self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_input_drift_after_selection_stops_before_manifest_or_game(self):
        def drift(*args):
            (self.repo / pilot.PREVIOUS).write_bytes(b"changed synthetic bytes")
            return selection()
        self.selector.side_effect = drift
        with mock.patch.object(pilot, "play_one") as play:
            summary = self.run_pilot()
        play.assert_not_called()
        self.assertEqual(summary["execution_status"], "FAILED")
        self.assertFalse((self.output / "manifest.json").exists())
        self.assertEqual(pilot.read_json(self.output / "selection-failure-prefix.json"), selection())
        self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_completed_selection_is_retained_if_manifest_build_or_publication_fails(self):
        real_publish = pilot.publish_json
        def publish(path, value):
            if path.name == "manifest.json":
                raise OSError("synthetic manifest publication fault")
            return real_publish(path, value)
        for step in ("build", "publish"):
            self.output = self.repo / step
            failure = (mock.patch.object(pilot, "make_manifest", side_effect=ValueError("synthetic build fault"))
                       if step == "build" else mock.patch.object(pilot, "publish_json", side_effect=publish))
            with self.subTest(step=step), failure, mock.patch.object(pilot, "play_one") as play:
                summary = self.run_pilot()
            play.assert_not_called()
            self.assertFalse((self.output / "manifest.json").exists())
            self.assertEqual(pilot.read_json(self.output / "selection-failure-prefix.json"), selection())
            self.assertEqual(pilot.inspect_run(self.output), summary)

    def test_globally_dirty_start_is_rejected_before_creating_attempt(self):
        with mock.patch.object(pilot, "source_snapshot", return_value=dict(source(), git_dirty=True)), \
             self.assertRaisesRegex(ValueError, "globally clean"):
            self.run_pilot()
        self.selector.assert_not_called()
        self.assertFalse(self.output.exists())


class SourceSnapshotTests(unittest.TestCase):
    def test_only_registered_plan_and_all_tracked_python_are_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            files = (pilot.PLAN, "src/example.py", "research/example.py", "scripts/example.py", "tests/example.py", "src/readme.md")
            for relative in files:
                path = repository / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic")
            with mock.patch.object(pilot.subprocess, "check_output", side_effect=["", "", "\n".join(files), "committed", ""]):
                snapshot = pilot.source_snapshot(repository)
            self.assertEqual(set(snapshot["source_sha256"]), set(files[:-1]))
            self.assertEqual(snapshot["git_commit"], "committed")
            self.assertFalse(snapshot["git_dirty"])
            with mock.patch.object(pilot.subprocess, "check_output", side_effect=["", "", "\n".join(files), "committed", "?? experiments/synthetic-run/"]):
                during_run = pilot.source_snapshot(repository)
            self.assertTrue(during_run["git_dirty"])
            self.assertEqual(during_run["source_sha256"], snapshot["source_sha256"])
            for replies in (["dirty.py"], ["", "untracked.py"], ["", "", "src/example.py"]):
                with mock.patch.object(pilot.subprocess, "check_output", side_effect=replies), self.assertRaises(ValueError):
                    pilot.source_snapshot(repository)


if __name__ == "__main__":
    unittest.main()
