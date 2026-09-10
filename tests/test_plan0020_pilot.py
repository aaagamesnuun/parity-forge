"""Only tiny 3x3 calibration and mocked schedules; no production members played."""

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from parity_forge.agents import RandomAgent
from parity_forge.dsl import Player, canonical_json, definition_hash, parse_definition
from parity_forge.engine import Action
from parity_forge.play import play_game
from parity_forge.solver import SolveBudgetExceeded
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent
from scripts import plan0020_pilot as pilot
from tests.test_agency_benchmark import FIXTURE_BY_ID


def tiny(first="A", name="tiny"):
    raw = {"schema_version": 4, "name": name, "board_size": 3, "first_player": first, "max_plies": 7,
           "roles": {r: {"action": {"kind": kind, "piece": r.lower(), "vectors": [[dr, c] for c in (-1, 0, 1)]},
                         "goal": {"kind": "REACH_EDGE", "piece": r.lower(), "edge": edge}}
                     for r, kind, dr, edge in (("A", "MOVE_CAPTURE", 1, "BOTTOM"), ("B", "PUSH", -1, "TOP"))},
           "initial_pieces": [{"owner": "A", "piece": "a", "position": [0, 0]},
                              {"owner": "B", "piece": "b", "position": [2, 2]}]}
    return json.loads(canonical_json(parse_definition(raw)))


def rows():
    result = []
    for i in range(pilot.CANDIDATE_COUNT):
        raw = tiny("B", "tiny-{}".format(i))
        result.append({"definition": raw, "first_player": raw["first_player"], "carrier_id": str(i),
                       "certificate": pilot.certify_no_draw(raw)})
    return result


def fake_game(raw, pa, pb, seed, cap):
    return {"status": "COMPLETE", "definition_hash": definition_hash(parse_definition(raw)),
            "first_player": raw["first_player"], "policy_a": pa, "policy_b": pb, "seed": seed,
            "max_nodes_per_role": cap, "winner": "A" if seed % 2 else "B", "plies": 1,
            "terminal_reason": "GOAL", "actions": [], "replay_count": 1}


def fake_exact(raw, cap):
    return {"status": "UNKNOWN_CENSORED", "definition_hash": definition_hash(parse_definition(raw)),
            "max_states": cap, "actual_result": None, "replay_count": 0,
            "error": {"type": "SolveBudgetExceeded", "searched_states": cap, "max_states": cap}}


class PlayTests(unittest.TestCase):
    def test_profiles_match_public_reference_and_one_replay(self):
        for first in ("A", "B"):
            raw, definition = tiny(first), parse_definition(tiny(first))
            for pa, pb in pilot.PROFILES:
                agents = {r: RandomAgent() if p == 0 else TerminalOnlyMinimaxAgent(p, 20000)
                          for r, p in ((Player.A, pa), (Player.B, pb))}
                expected = play_game(definition, agents, 0).to_dict()
                with mock.patch.object(pilot, "replay_dicts", wraps=pilot.replay_dicts) as replay:
                    actual = pilot.play_one(raw, pa, pb, 0)
                self.assertEqual(actual["status"], "COMPLETE")
                for key in ("actions", "winner", "terminal_reason", "plies"):
                    self.assertEqual(actual[key], expected[key])
                self.assertEqual(replay.call_count, 1)
                self.assertEqual(actual["nodes_by_role"], {r.value: getattr(a, "total_nodes", 0) for r, a in agents.items()})

    def test_censor_nonempty_prefix_and_failed_decision_nodes(self):
        raw = copy.deepcopy(FIXTURE_BY_ID["swap-both-roles-repeat-v1"]["definition"])
        censored = pilot.play_one(raw, 2, 2, 0, 2)
        self.assertEqual((censored["status"], censored["plies"], censored["replay_count"]), ("UNKNOWN_CENSORED", 2, 1))
        self.assertIsNone(censored["winner"])
        original = TerminalOnlyMinimaxAgent.select_action
        for illegal in (False, True):
            def fail(agent, definition, state, actions, rng):
                action = original(agent, definition, state, actions, rng)
                if state.ply == 1:
                    if illegal:
                        return Action.place(0, 0)
                    raise RuntimeError("after charged nodes")
                return action
            with mock.patch.object(TerminalOnlyMinimaxAgent, "select_action", fail):
                failed = pilot.play_one(raw, 2, 2, 0)
            self.assertEqual((failed["status"], failed["plies"], failed["replay_count"]), ("FAILED", 1, 1))
            decision = failed["decisions"][-1]
            self.assertEqual(decision["selection_status"], "FAILED")
            self.assertGreater(decision["nodes_after"], decision["nodes_before"])

    def test_last_ply_goal_stuck_and_replay_failure(self):
        raw = copy.deepcopy(FIXTURE_BY_ID["push-win-draw-loss-v1"]["definition"])
        self.assertEqual(pilot.play_one(raw, 2, 2, 0)["terminal_reason"], "GOAL")
        stuck = copy.deepcopy(FIXTURE_BY_ID["initial-stuck-zero-v1"]["definition"])
        with mock.patch.object(TerminalOnlyMinimaxAgent, "select_action", side_effect=AssertionError):
            self.assertEqual(pilot.play_one(stuck, 3, 3, 0)["plies"], 0)
        with mock.patch.object(pilot, "replay_dicts", return_value=None):
            self.assertEqual(pilot.play_one(raw, 2, 2, 0)["status"], "FAILED")
        for args in ((True, 0, 0, 2), (1, 0, 0, 2), (0, 0, True, 2), (0, 0, 0, 0)):
            with self.assertRaises(ValueError):
                pilot.play_one(raw, *args)

    def test_exact_success_censor_invalid_counter_and_pv(self):
        with mock.patch.object(pilot, "replay_dicts", wraps=pilot.replay_dicts) as replay:
            solved = pilot.exact_one(tiny(), 1000)
        self.assertEqual((solved["status"], replay.call_count), ("COMPLETE", 1))
        with mock.patch.object(pilot, "replay_dicts", wraps=pilot.replay_dicts) as replay:
            censored = pilot.exact_one(tiny(), 1)
        self.assertEqual((censored["status"], replay.call_count), ("UNKNOWN_CENSORED", 0))
        bad = copy.deepcopy(solved["actual_result"])
        bad["searched_states"] = True
        with mock.patch.object(pilot, "solve_game") as solve:
            solve.return_value.to_dict.return_value = bad
            self.assertEqual(pilot.exact_one(tiny(), 1000)["status"], "FAILED")
        with mock.patch.object(pilot, "solve_game", side_effect=SolveBudgetExceeded(0, 1)):
            self.assertEqual(pilot.exact_one(tiny(), 1)["status"], "FAILED")
        with mock.patch.object(pilot, "replay_dicts", return_value=None):
            self.assertEqual(pilot.exact_one(tiny(), 1000)["status"], "FAILED")


class RunnerTests(unittest.TestCase):
    def test_real_git_pins_clean_head_untracked_and_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            def git(*args):
                return subprocess.check_output(("git", "-C", tmp, *args), text=True).strip()
            git("init", "-q")
            plan = repo / pilot.PLAN
            plan.parent.mkdir(parents=True)
            plan.write_text("artificial registration\n")
            outside = repo / "outside.py"
            outside.write_text("# tiny tracked source\n")
            git("add", ".")
            git("-c", "user.name=Calibration", "-c", "user.email=calibration@example.invalid",
                "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "-qm", "fixture")
            source = pilot.source_snapshot(repo, clean=True)
            self.assertEqual(set(source["source_sha256"]), {"outside.py", pilot.PLAN})
            with self.assertRaises(ValueError):
                pilot.run_pilot(repo, "0" * 40, repo / "no-run")
            self.assertFalse((repo / "no-run").exists())
            outside.write_text("# changed\n")
            self.assertNotEqual(pilot.source_snapshot(repo), source)
            with self.assertRaises(ValueError):
                pilot.source_snapshot(repo, clean=True)
            (repo / "untracked.py").write_text("# new\n")
            with self.assertRaisesRegex(ValueError, "untracked Python"):
                pilot.source_snapshot(repo)

    def run_mocked(self, path, game=fake_game, exact=fake_exact, snapshot=None):
        source = {"git_commit": "a" * 40, "source_sha256": {"tiny.py": "pinned"}}
        with mock.patch.object(pilot, "source_snapshot", side_effect=snapshot or (lambda *a, **k: source)), \
                mock.patch.object(pilot, "build_candidates", side_effect=rows), \
                mock.patch.object(pilot, "play_one", side_effect=game) as play, \
                mock.patch.object(pilot, "exact_one", side_effect=exact) as solve:
            summary = pilot.run_pilot(path, "a" * 40, path / "run")
        return summary, play.call_count, solve.call_count

    def test_fixed_schedule_denominators_flags_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            summary, games, exact = self.run_mocked(path)
            self.assertEqual((games, exact), (pilot.CANDIDATE_COUNT * 20, pilot.CANDIDATE_COUNT))
            self.assertEqual(summary, pilot.read_json(path / "run/summary.json"))
            self.assertEqual({r["disposition"] for r in summary["candidates"]}, {"REVIEW_ONLY"})
            self.assertTrue(all(c["planned"] == c["completed"] == 4 for c in summary["cells"]))
            self.assertFalse(summary["fairness_established"] or summary["hardness_established"] or summary["fun_established"])
            with self.assertRaises(FileExistsError):
                self.run_mocked(path)

    def test_drift_failure_preserves_completed_prefix_and_stops(self):
        calls = []
        def changed(raw, pa, pb, seed, cap):
            calls.append(seed)
            return fake_game(raw, pa, pb, seed, cap)
        def snapshot(*args, **kwargs):
            return {"git_commit": "a" * 40, "source_sha256": {"tiny.py": "changed" if calls else "pinned"}}
        with tempfile.TemporaryDirectory() as tmp:
            summary, games, exact = self.run_mocked(Path(tmp), game=changed, snapshot=snapshot)
            self.assertEqual((games, exact, summary["execution_status"]), (1, 0, "FAILED"))
            saved = pilot.read_json(Path(tmp) / "run/games/0000-result.json")["result"]
            self.assertEqual((saved["status"], saved["plies"], saved["replay_count"]), ("FAILED", 1, 1))
            self.assertEqual(summary["games_not_started"], pilot.CANDIDATE_COUNT * 20 - 1)

    def test_exception_prefix_draw_bound_and_readback_fail_closed(self):
        for mode in ("exception", "draw", "bound", "replay"):
            def fail(*args):
                if mode == "exception":
                    raise RuntimeError("before record return")
                result = fake_game(*args)
                result.update({"draw": {"winner": None}, "bound": {"plies": 100}, "replay": {"replay_count": 2}}[mode])
                return result
            with tempfile.TemporaryDirectory() as tmp:
                summary, games, exact = self.run_mocked(Path(tmp), game=fail)
                self.assertEqual((summary["execution_status"], games, exact), ("FAILED", 1, 0))
                self.assertEqual((summary["games_attempted"], summary["games_not_started"]),
                                 (1, pilot.CANDIDATE_COUNT * 20 - 1))
                self.assertTrue((Path(tmp) / "run/failure.json").exists())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.json"
            with mock.patch.object(pilot, "read_json", return_value={}):
                with self.assertRaises(ValueError):
                    pilot._publish(path, {"preserved": True})

    def test_unpublished_execution_remains_a_failed_attempt_not_unstarted(self):
        publish = pilot._publish
        def fail_result(path, value):
            if path.name.endswith("-result.json"):
                raise OSError("synthetic publication failure")
            publish(path, value)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pilot, "_publish", side_effect=fail_result):
            summary, games, exact = self.run_mocked(Path(tmp))
            self.assertEqual((games, exact, summary["games_attempted"]), (1, 0, 1))
            self.assertEqual(summary["game_statuses"], {"FAILED": 1})
            self.assertEqual(summary["games_not_started"], pilot.CANDIDATE_COUNT * 20 - 1)
            pending = pilot.read_json(Path(tmp) / "run/failure.json")["current"]["result"]
            self.assertEqual((pending["status"], pending["status_before_publication"], pending["plies"]),
                             ("FAILED", "COMPLETE", 1))

    def test_summary_requires_full_cells_and_exact_success_is_not_quality(self):
        manifest = pilot.make_manifest(rows(), {})
        games = [{"scheduled": s, "result": fake_game(rows()[s["candidate_index"]]["definition"], s["policy_a"], s["policy_b"], s["seed"], 20000)} for s in manifest["games"]]
        exact = [{"scheduled": s, "result": {"status": "COMPLETE"}} for s in manifest["exact"]]
        self.assertEqual({r["disposition"] for r in pilot.summarize(manifest, games, exact)["candidates"]}, {"TOO_EASILY_SOLVED"})
        exact[0]["result"]["status"] = "UNKNOWN_CENSORED"
        self.assertEqual(pilot.summarize(manifest, games[1:], exact)["candidates"][0]["disposition"], "NO_FLAG")
        with self.assertRaises(ValueError):
            pilot.make_manifest(rows()[:-1], {})
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            pilot.run_pilot(tmp, "not-a-commit")


if __name__ == "__main__":
    unittest.main()
