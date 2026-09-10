"""Synthetic 3x3 wires and mocked outcomes only; no production play/solve."""

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from parity_forge.dsl import definition_hash, parse_definition
from scripts import plan0022_screen as screen
from scripts.plan0016_pilot import read_json
from tests.test_plan0021_pilot import tiny, fake_exact


def game(w, a, b, seed, cap):
    winner = ("A" if a.endswith("4") else "B") if a != b and (a[-1:] == "2" or b[-1:] == "2" or "G" in (a, b)) else ("A" if seed % 2 else "B")
    decisions = [dict(ply=i, actor="AB"[i % 2], selection_status="SELECTED", legal_action_count=2,
                      last_action_values=[dict(value=v) for v in ((0, 0) if i == 0 else (-1, 1))]) for i in range(4)]
    return dict(status="COMPLETE", definition_hash=definition_hash(parse_definition(w)), first_player="A",
                policy_a=a, policy_b=b, seed=seed, max_nodes_per_role=cap, winner=winner,
                plies=4, actions=[{}]*4, terminal_reason="GOAL", replay_count=1, replay_verified=True,
                nodes_by_role={"A": int(a != "G"), "B": int(b != "G")}, decisions=decisions)


class ScreenTests(unittest.TestCase):
    def run_mocked(self, repo, play=game, exact=fake_exact, snapshot=None):
        source = dict(git_commit="a"*40, sha256={"synthetic.py": "pinned"})
        with mock.patch.object(screen, "HASH", definition_hash(parse_definition(tiny()))), \
             mock.patch.object(screen, "source_snapshot", side_effect=snapshot or (lambda *a, **k: source)), \
             mock.patch.object(screen, "load_definition", return_value=tiny()), \
             mock.patch.object(screen, "play_one", side_effect=play) as games, \
             mock.patch.object(screen, "exact_one", side_effect=exact) as solves:
            result = screen.run_pilot(repo, "a"*40)
        return result, games.call_count, solves.call_count

    def test_full_schedule_positive_gate_separate_cells_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, games, solves = self.run_mocked(Path(tmp))
            self.assertEqual((games, solves, result["attempted"], result["not_started"]), (128, 1, 129, 0))
            self.assertEqual(result["disposition"], "HUMAN_REVIEW_ELIGIBLE")
            self.assertEqual(len(result["cells"]), 12)
            self.assertEqual(result["cross_combined"]["a_wins"], 8)
            self.assertEqual(result["cells"][0]["charged_nodes_by_role"], {"A": 16, "B": 16})
            self.assertFalse(any(result[k+"_established"] for k in ("fairness", "hardness", "fun")))
            output = Path(tmp)/"experiments/runs"/screen.PROTOCOL
            self.assertEqual(read_json(output/"summary.json"), json.loads(json.dumps(result)))
            planned = read_json(output/"manifest.json")["schedule"]
            self.assertEqual([r["stage"] for r in planned[1:33]], ["base"]*32)
            self.assertEqual(len({json.dumps(r, sort_keys=True) for r in planned}), 129)
            with self.assertRaises(FileExistsError):
                self.run_mocked(Path(tmp))

    def test_prospective_early_gates_and_valid_censor(self):
        for mode, label, expected in (("exact", "TOO_EASILY_SOLVED", 0), ("short", "SHORT_FORCED_RESULT", 1),
                                     ("bias", "NO_FLAG", 32), ("censor", "INSUFFICIENT_EVIDENCE", 32)):
            def solve(w, cap):
                r = fake_exact(w, cap)
                if mode == "exact":
                    r.update(status="COMPLETE", replay_count=1, actual_result=dict(value_for_a=1, principal_variation_plies=2, terminal_reason="GOAL"))
                return r
            def play(*args):
                r = game(*args)
                if mode == "short":
                    r["decisions"][0]["last_action_values"] = [dict(value=-1)]*2
                if mode == "bias":
                    r["winner"] = "A"
                if mode == "censor":
                    r.update(status="UNKNOWN_CENSORED", winner=None, terminal_reason=None, plies=0, actions=[], decisions=[],
                             nodes_by_role={"A": screen.MAX_NODES, "B": 0},
                             censor=dict(role="A", visited_nodes=screen.MAX_NODES, max_nodes=screen.MAX_NODES))
                return r
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                r, games, solves = self.run_mocked(Path(tmp), play, solve)
                self.assertEqual((r["execution_status"], r["disposition"], games, solves), ("COMPLETE", label, expected, 1))
                self.assertEqual(r["not_started_gate_closed"], 128-expected)
                self.assertEqual(sum(c["not_started"] for c in r["cells"]), 128-expected)

    def test_final_thresholds_are_not_pooled_or_rescued(self):
        for mode in ("confirm", "cross", "skill", "trivial", "witness"):
            def play(w, a, b, seed, cap):
                r = game(w, a, b, seed, cap)
                if ((mode == "confirm" and seed >= 200 and a == b == "H4")
                        or (mode == "cross" and {a, b} == {"T4", "H4"})):
                    r["winner"] = "A"
                if (mode == "skill" and (a, b) == ("T2", "T4")) or (mode == "trivial" and (a, b) == ("G", "T4")):
                    r["winner"] = "A"
                if mode == "witness":
                    for d in r["decisions"]:
                        if d["actor"] == "B":
                            d["last_action_values"] = [dict(value=0)]*2
                return r
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                r, games, _ = self.run_mocked(Path(tmp), play)
                self.assertEqual((games, r["disposition"]), (128, "NO_FLAG"))

    def test_failures_keep_started_prefix_and_stop(self):
        for mode in ("exception", "draw", "bound", "replay", "source", "publication", "artifact"):
            calls, snapshots, original = [], [], screen._publish
            def play(*args):
                calls.append(1)
                if mode == "exception":
                    raise RuntimeError("synthetic failure")
                r = game(*args)
                if mode == "draw": r["winner"] = None
                if mode == "bound": r.update(plies=40, actions=[{}]*40)
                if mode == "replay": r["replay_count"] = 2
                return r
            def snapshot(*args, **kwargs):
                snapshots.append(1)
                return dict(git_commit="a"*40, sha256={"synthetic.py": "changed" if mode == "source" and calls else "pinned"})
            def publish(path, value):
                if mode == "publication" and path.name == "0001-result.json":
                    raise OSError("synthetic disk failure")
                original(path, value)
                if mode == "artifact" and path.name == "0001-result.json":
                    (path.parent/"manifest.json").write_text("changed")
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp, mock.patch.object(screen, "_publish", side_effect=publish):
                r, games, _ = self.run_mocked(Path(tmp), play, snapshot=snapshot)
                self.assertEqual(r["execution_status"], "FAILED")
                if mode != "artifact":
                    self.assertEqual((games, r["attempted"], r["statuses"]["FAILED"], r["not_started_failure"]), (1, 2, 1, 127))
                    self.assertEqual(len(snapshots), 5)
                failure = read_json(Path(tmp)/"experiments/runs"/screen.PROTOCOL/"failure.json")
                if mode == "publication":
                    self.assertEqual(failure["current"]["result"]["plies"], 4)

    def test_final_summary_publication_failure_cannot_promote(self):
        original = screen._publish
        def publish(path, value):
            if path.name == "summary.json":
                raise OSError("synthetic finalization failure")
            original(path, value)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(screen, "_publish", side_effect=publish):
            r, games, _ = self.run_mocked(Path(tmp))
            self.assertEqual((games, r["execution_status"], r["disposition"]), (128, "FAILED", "FAILED"))
            self.assertEqual(read_json(Path(tmp)/"experiments/runs"/screen.PROTOCOL/"summary-publication-failure.json"), r)

    def test_real_git_pins_and_fixed_wire_load_on_tiny_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, raw = Path(tmp), copy.deepcopy(tiny())
            raw["max_plies"] = 40
            for name, text in ((screen.PLAN, "calibration"), (screen.DATA, json.dumps({"definitions": [raw]})), ("source.py", "# tiny")):
                path = repo/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            def git(*args):
                return subprocess.check_output(("git", "-C", tmp, *args), text=True).strip()
            git("init", "-q"); git("add", ".")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
                "-c", "core.hooksPath=/dev/null", "commit", "-qm", "tiny")
            pins = screen.source_snapshot(repo, clean=True)
            self.assertEqual(set(pins["sha256"]), {screen.PLAN, screen.DATA, "source.py"})
            with mock.patch.object(screen, "HASH", definition_hash(parse_definition(raw))):
                self.assertEqual(screen.load_definition(repo), raw)
            with self.assertRaises(ValueError): screen.load_definition(repo)
            (repo/"source.py").write_text("# changed")
            self.assertNotEqual(screen.source_snapshot(repo), pins)
            with self.assertRaises(ValueError): screen.source_snapshot(repo, clean=True)
            (repo/"extra.py").write_text("# unregistered")
            with self.assertRaises(ValueError): screen.source_snapshot(repo)


if __name__ == "__main__":
    unittest.main()
