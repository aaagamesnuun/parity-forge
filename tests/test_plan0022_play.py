"""Synthetic 3x3 calibration only; no production definitions or exact calls."""

import copy
import json
import unittest
from unittest import mock

from parity_forge.agents import GoalDirectedAgent, MinimaxAgent, SearchBudgetExceeded
from parity_forge.dsl import Player, parse_definition
from parity_forge.engine import Action
from parity_forge.play import play_game
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent
from scripts import plan0022_play as pilot
from tests.test_agency_benchmark import FIXTURE_BY_ID
from tests.test_plan0021_pilot import tiny


def agent(policy, cap):
    if policy == "G":
        return GoalDirectedAgent()
    if policy[0] == "T":
        return TerminalOnlyMinimaxAgent(int(policy[1]), cap)
    return MinimaxAgent(int(policy[1]), max_total_nodes=cap)


def without_elapsed(row):
    return {k: v for k, v in row.items() if k != "elapsed_seconds"}


class RecorderTests(unittest.TestCase):
    def test_every_policy_pair_matches_public_game_and_is_deterministic(self):
        raw, definition = tiny(), parse_definition(tiny())
        self.assertEqual(definition.board_size, 3)
        for pa in pilot.POLICIES:
            for pb in pilot.POLICIES:
                agents = {Player.A: agent(pa, 10000), Player.B: agent(pb, 10000)}
                expected = play_game(definition, agents, 7).to_dict()
                with mock.patch.object(pilot, "replay_dicts", wraps=pilot.replay_dicts) as replay:
                    row = pilot.play_one(raw, pa, pb, 7, 10000)
                self.assertEqual(row["status"], "COMPLETE", row)
                self.assertEqual(row["observed_game_record"], expected)
                self.assertEqual((replay.call_count, row["replay_verified"]), (1, True))
                self.assertEqual(row["nodes_by_role"], {r.value: getattr(a, "total_nodes", 0) for r, a in agents.items()})
                self.assertEqual(without_elapsed(row), without_elapsed(pilot.play_one(raw, pa, pb, 7, 10000)))
                self.assertIsNone(row["unconfirmed_action"])
                json.dumps(row, allow_nan=False)

    def test_fresh_agents_per_role_and_game_with_one_persistent_rng(self):
        raw = copy.deepcopy(FIXTURE_BY_ID["swap-both-roles-repeat-v1"]["definition"])
        original, rngs, instances = GoalDirectedAgent.select_action, [], []
        def observe(a, d, state, choices, rng):
            instances.append(a)
            rngs.append(rng)
            return original(a, d, state, choices, rng)
        with mock.patch.object(GoalDirectedAgent, "select_action", observe):
            first = pilot.play_one(raw, "G", "G", 0, 1)
            split = len(rngs)
            pilot.play_one(raw, "G", "G", 0, 1)
        self.assertEqual(len({id(r) for r in rngs[:split]}), 1)
        self.assertIsNot(rngs[0], rngs[-1])
        self.assertEqual(len({id(a) for a in instances}), 4)
        self.assertEqual(first["nodes_by_role"], {"A": 0, "B": 0})
        self.assertTrue(all("NOT_ZERO_COMPUTE" in label for label in first["node_accounting"].values()))
        for policy in ("T2", "H2"):
            row = pilot.play_one(raw, policy, policy, 0, 20)
            for owner in ("A", "B"):
                self.assertEqual(next(d for d in row["decisions"] if d["actor"] == owner)["nodes_before"], 0)

    def test_search_censor_keeps_applied_prefix_and_failed_decision_charge(self):
        raw = copy.deepcopy(FIXTURE_BY_ID["swap-both-roles-repeat-v1"]["definition"])
        for policy in ("T2", "H2"):
            with mock.patch.object(pilot, "replay_dicts", wraps=pilot.replay_dicts) as replay:
                row = pilot.play_one(raw, policy, policy, 0, 2)
            self.assertEqual((row["status"], row["plies"], replay.call_count), ("UNKNOWN_CENSORED", 2, 1))
            self.assertEqual((row["winner"], row["terminal_reason"]), (None, None))
            self.assertEqual(row["nodes_by_role"], {"A": 2, "B": 2})
            self.assertEqual(row["decisions"][-1]["selection_status"], "UNKNOWN_CENSORED")
            self.assertIsNone(row["unconfirmed_action"])

    def test_node_consuming_exception_and_illegal_selection_retain_prefix(self):
        raw = copy.deepcopy(FIXTURE_BY_ID["swap-both-roles-repeat-v1"]["definition"])
        original = TerminalOnlyMinimaxAgent.select_action
        for illegal in (False, True):
            def fail(a, d, state, choices, rng):
                selected = original(a, d, state, choices, rng)
                if state.ply == 1:
                    if illegal:
                        return Action.place(0, 0)
                    raise RuntimeError("after charged nodes")
                return selected
            with mock.patch.object(TerminalOnlyMinimaxAgent, "select_action", fail):
                row = pilot.play_one(raw, "T2", "T2", 0, 100)
            self.assertEqual((row["status"], row["plies"], row["replay_count"]), ("FAILED", 1, 1))
            self.assertTrue(row["replay_verified"])
            self.assertGreater(row["decisions"][-1]["charged_nodes"], 0)
            self.assertEqual(row["decisions"][-1]["selection_status"], "FAILED")

    def test_apply_exception_never_replays_the_unconfirmed_selection(self):
        raw = tiny()
        with mock.patch("parity_forge.play.apply_action", side_effect=RuntimeError("apply failed")), \
                mock.patch.object(pilot, "replay_dicts", wraps=pilot.replay_dicts) as replay:
            row = pilot.play_one(raw, "G", "G", 0, 100)
        self.assertEqual((row["status"], row["plies"], replay.call_count), ("FAILED", 0, 1))
        self.assertEqual(row["actions"], [])
        self.assertIsNotNone(row["unconfirmed_action"])
        self.assertEqual(row["unconfirmed_action"], row["decisions"][0]["selected_action"])
        self.assertTrue(row["replay_verified"])

    def test_replay_mismatch_drift_and_invalid_censor_fail_closed(self):
        with mock.patch.object(pilot, "replay_dicts", return_value=None) as replay:
            row = pilot.play_one(tiny(), "T2", "H2", 0, 1000)
        self.assertEqual((row["status"], replay.call_count), ("FAILED", 1))
        with mock.patch.object(MinimaxAgent, "select_action", side_effect=SearchBudgetExceeded("per-candidate", 1, 1)):
            row = pilot.play_one(tiny(), "H2", "H2", 0, 1)
        self.assertEqual(row["status"], "FAILED")
        raw, original = tiny(), GoalDirectedAgent.select_action
        def mutate(a, d, state, choices, rng):
            raw["name"] = "drifted"
            return original(a, d, state, choices, rng)
        with mock.patch.object(GoalDirectedAgent, "select_action", mutate):
            row = pilot.play_one(raw, "G", "G", 0, 100)
        self.assertEqual(row["status"], "FAILED")

    def test_last_ply_goal_initial_stuck_and_configuration_limits(self):
        raw = copy.deepcopy(FIXTURE_BY_ID["push-win-draw-loss-v1"]["definition"])
        row = pilot.play_one(raw, "T4", "H4", 0, 100)
        self.assertEqual((row["winner"], row["terminal_reason"], row["plies"]), ("A", "GOAL", 1))
        stuck = copy.deepcopy(FIXTURE_BY_ID["initial-stuck-zero-v1"]["definition"])
        with mock.patch.object(GoalDirectedAgent, "select_action", side_effect=AssertionError):
            row = pilot.play_one(stuck, "G", "G", 0, 1)
        self.assertEqual((row["status"], row["plies"], row["replay_count"]), ("COMPLETE", 0, 1))
        for args in (("T3", "G", 0, 1), (True, "G", 0, 1), ("G", "G", True, 1), ("G", "G", 0, 0), ("G", "G", 0, True)):
            with self.assertRaises(ValueError):
                pilot.play_one(raw, *args)


if __name__ == "__main__":
    unittest.main()
