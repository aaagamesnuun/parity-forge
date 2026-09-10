"""Tiny3x3 calibration only; production definitions are checked statically."""

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from parity_forge.dsl import Player, canonical_json, definition_hash, parse_definition
from parity_forge.engine import apply_action, initial_state, legal_actions
from scripts import plan0021_pilot as pilot
from scripts.plan0016_pilot import read_json
from tests.test_plan0020_pilot import tiny as push_tiny


def tiny(first="A", friendly=False):
    w = push_tiny(first)
    w["roles"]["B"]["action"]["kind"] = "HOP"
    if friendly:
        w["initial_pieces"].append({"owner": "B", "piece": "b", "position": [1, 2]})
    return json.loads(canonical_json(parse_definition(w)))


def potential(d, state):
    return sum(d.board_size-1-p.position[0] if p.owner is Player.A else p.position[0] for p in state.pieces)


def fake_exact(w, cap):
    return dict(status="UNKNOWN_CENSORED", definition_hash=definition_hash(parse_definition(w)),
                max_states=cap, replay_count=0, actual_result=None,
                error=dict(type="SolveBudgetExceeded", searched_states=cap, max_states=cap))


def fake_game(w, a, b, seed, cap):
    return dict(status="COMPLETE", definition_hash=definition_hash(parse_definition(w)),
                first_player=w["first_player"], policy_a=a, policy_b=b, seed=seed,
                max_nodes_per_role=cap, replay_count=1, winner="A" if seed % 2 else "B",
                plies=2, terminal_reason="GOAL")


class CertificateTests(unittest.TestCase):
    def test_static_definition_hashes_and_schedule(self):
        rows = pilot.load_definitions(Path(__file__).resolve().parents[1])
        self.assertEqual([w["first_player"] for w in rows], ["A", "B"])
        self.assertEqual([pilot.certify(w)["max_natural_plies"] for w in rows], [40, 40])
        schedule = pilot.schedule(rows)
        self.assertEqual(len(schedule), 26)
        self.assertEqual([s["kind"] for s in schedule].count("exact"), 2)
        self.assertTrue(all(s["max_states"] == 100000 for s in schedule if s["kind"] == "exact"))

    def test_all_tiny_branches_terminate_and_hop_both_owners(self):
        tags = set()
        for first in ("A", "B"):
            for friendly in (False, True):
                d = parse_definition(tiny(first, friendly))
                bound = pilot.certify(tiny(first, friendly))["max_natural_plies"]
                todo, seen = [initial_state(d)], set()
                while todo:
                    state = todo.pop()
                    if state in seen:
                        continue
                    seen.add(state)
                    self.assertGreaterEqual(potential(d, state), 0)
                    self.assertLessEqual(state.ply, bound)
                    if state.terminal:
                        self.assertIn(state.outcome.winner, (Player.A, Player.B))
                        self.assertIn(state.outcome.reason, ("GOAL", "NO_LEGAL_ACTION"))
                        continue
                    actions = legal_actions(d, state)
                    self.assertTrue(actions)
                    occupied = {p.position: p for p in state.pieces}
                    for action in actions:
                        if abs(action.to_position[0]-action.from_position[0]) == 2:
                            middle = tuple((x+y)//2 for x, y in zip(action.from_position, action.to_position))
                            tags.add("hop_"+occupied[middle].owner.value)
                        nxt = apply_action(d, state, action)
                        self.assertLess(potential(d, nxt), potential(d, state))
                        todo.append(nxt)
        self.assertEqual(tags, {"hop_A", "hop_B"})

    def test_rejects_theorem_and_cap_changes(self):
        for mutation in (
            lambda w: w["roles"]["B"]["action"].update(kind="PUSH"),
            lambda w: w["roles"]["A"]["action"].update(vectors=[[0, 1]]),
            lambda w: w["roles"]["B"]["goal"].update(edge="BOTTOM"),
            lambda w: w.update(max_plies=4),
            lambda w: w["initial_pieces"][0].update(piece="x"),
        ):
            w = tiny()
            mutation(w)
            with self.assertRaises(ValueError):
                pilot.certify(w)

    def test_reused_recorders_on_tiny_hop_only(self):
        w = tiny()
        for a, b in pilot.PROFILES:
            result = pilot.play_one(w, a, b, 0, 100000)
            item = dict(kind="game", first_player="A", policy_a=a, policy_b=b, seed=0,
                        max_nodes_per_role=100000, definition_hash=definition_hash(parse_definition(w)))
            pilot.validate_result(item, result, pilot.certify(w)["max_natural_plies"])
        solved = pilot.exact_one(w, 1000)
        pilot.validate_result(dict(kind="exact", max_states=1000, definition_hash=solved["definition_hash"]),
                              solved, pilot.certify(w)["max_natural_plies"])


class RunnerTests(unittest.TestCase):
    def run_mocked(self, repo, exact=fake_exact, game=fake_game, snapshot=None):
        source = dict(git_commit="a"*40, sha256={"tiny.py": "pinned"})
        with mock.patch.object(pilot, "source_snapshot", side_effect=snapshot or (lambda *a, **k: source)), \
             mock.patch.object(pilot, "load_definitions", return_value=[tiny("A"), tiny("B")]), \
             mock.patch.object(pilot, "exact_one", side_effect=exact) as solve, \
             mock.patch.object(pilot, "play_one", side_effect=game) as play:
            summary = pilot.run_pilot(repo, "a"*40)
        return summary, solve.call_count, play.call_count

    def test_schedule_summary_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            summary, exact, games = self.run_mocked(repo)
            self.assertEqual((exact, games, summary["attempted"], summary["not_started"]), (2, 24, 26, 0))
            self.assertEqual({r["disposition"] for r in summary["candidates"]}, {"TRIAL_REVIEW_ONLY"})
            self.assertFalse(summary["hardness_established"] or summary["fairness_established"] or summary["fun_established"])
            self.assertEqual(read_json(repo/"experiments/runs"/pilot.PROTOCOL/"summary.json"), summary)
            with self.assertRaises(FileExistsError):
                self.run_mocked(repo)

    def test_failure_and_publication_count_started_attempts(self):
        for mode in ("exception", "wrong_replay", "publication", "draw", "drift"):
            calls = []
            def exact(w, cap):
                calls.append(1)
                if mode == "exception":
                    raise RuntimeError("synthetic failure")
                result = fake_exact(w, cap)
                if mode == "wrong_replay":
                    result["replay_count"] = 2
                if mode == "draw":
                    result.update(status="COMPLETE", replay_count=1, actual_result=dict(
                        value_for_a=0, principal_variation_plies=1, terminal_reason="PLY_LIMIT"))
                return result
            def snapshot(*a, **k):
                return dict(git_commit="a"*40, sha256={"tiny.py": "changed" if mode == "drift" and calls else "pinned"})
            original = pilot._publish
            def publish(path, value):
                if mode == "publication" and path.name.endswith("-result.json"):
                    raise OSError("synthetic publication failure")
                original(path, value)
            with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pilot, "_publish", side_effect=publish):
                summary, exact_count, games = self.run_mocked(Path(tmp), exact=exact, snapshot=snapshot)
                self.assertEqual((exact_count, games, summary["execution_status"]), (1, 0, "FAILED"))
                self.assertEqual((summary["attempted"], summary["not_started"]), (1, 25))
                self.assertEqual(summary["statuses"], {"FAILED": 1})

    def test_real_git_source_pins_and_registration_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            def git(*args):
                return subprocess.check_output(("git", "-C", tmp, *args), text=True).strip()
            git("init", "-q")
            for name in (pilot.PLAN, pilot.DATA, "source.py"):
                path = repo/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("calibration\n")
            git("add", ".")
            git("-c", "user.name=Calibration", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
                "-c", "core.hooksPath=/dev/null", "commit", "-qm", "tiny")
            source = pilot.source_snapshot(repo, clean=True)
            self.assertEqual(set(source["sha256"]), {pilot.PLAN, pilot.DATA, "source.py"})
            with self.assertRaises(ValueError):
                pilot.run_pilot(repo, "0"*40)
            (repo/pilot.DATA).write_text("changed\n")
            self.assertNotEqual(source, pilot.source_snapshot(repo))
            with self.assertRaises(ValueError):
                pilot.source_snapshot(repo, clean=True)
            (repo/"unknown.py").write_text("# untracked\n")
            with self.assertRaises(ValueError):
                pilot.source_snapshot(repo)


if __name__ == "__main__":
    unittest.main()
