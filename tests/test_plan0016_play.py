"""Tiny existing-fixture integration tests; never load selected pilot members."""

import ast
import copy
import hashlib
import json
import random
import unittest
from pathlib import Path
from unittest import mock

from parity_forge.agents import RandomAgent
from parity_forge.dsl import Player, parse_definition
from parity_forge.engine import Action, Outcome, initial_state, legal_actions, replay_dicts
from parity_forge.play import play_game
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent
from scripts import plan0016_play as pilot
from tests.test_agency_benchmark import FIXTURE_BY_ID


def fixture(name):
    return copy.deepcopy(FIXTURE_BY_ID[name]["definition"])


def role_swapped(raw):
    value = copy.deepcopy(raw)
    value["first_player"] = "B" if value["first_player"] == "A" else "A"
    value["roles"] = {"A": value["roles"]["B"], "B": value["roles"]["A"]}
    for piece in value["initial_pieces"]:
        piece["owner"] = "B" if piece["owner"] == "A" else "A"
    return value


class PilotPlayTests(unittest.TestCase):
    def test_all_five_profiles_match_public_play_and_replay_on_tiny_fixtures(self):
        names = (
            "push-win-draw-loss-v1", "convert-immediate-reconvergence-v1",
            "capture-eliminate-one-sided-b-v1", "swap-both-roles-repeat-v1",
            "initial-stuck-zero-v1",
        )
        for name in names:
            raw = fixture(name)
            definition = parse_definition(raw)
            self.assertLessEqual(definition.max_plies, 4)
            for pa, pb in ((0, 0), (1, 1), (2, 2), (2, 1), (1, 2)):
                for seed in (0, 1):
                    with self.subTest(fixture=name, policies=(pa, pb), seed=seed):
                        agents = {
                            role: RandomAgent() if depth == 0 else TerminalOnlyMinimaxAgent(depth, 5000)
                            for role, depth in ((Player.A, pa), (Player.B, pb))
                        }
                        expected = play_game(definition, agents, seed).to_dict()
                        observed = pilot.play_one(raw, pa, pb, seed)
                        self.assertEqual(observed["status"], "COMPLETE")
                        for key in ("seed", "agent_a", "agent_b", "actions", "winner", "terminal_reason", "plies"):
                            self.assertEqual(observed[key], expected[key])
                        self.assertEqual(observed["nodes_by_role"], {
                            role.value: getattr(agent, "total_nodes", 0)
                            for role, agent in agents.items()
                        })
                        self.assertEqual(replay_dicts(definition, observed["actions"]).to_dict(), observed["state_after_prefix"])
                        self.assertEqual(pilot.play_one(raw, pa, pb, seed), observed)

    def test_goal_at_last_permitted_ply_precedes_ply_limit(self):
        result = pilot.play_one(fixture("push-win-draw-loss-v1"), 1, 1, 0)
        self.assertEqual((result["winner"], result["terminal_reason"], result["plies"]), ("A", "GOAL", 1))
        self.assertEqual(result["actions"], [{"kind": "PUSH", "from": [1, 1], "to": [2, 1]}])
        self.assertEqual(result["decisions"][0]["legal_action_count"], 3)
        self.assertEqual(result["nodes_by_role"], {"A": 3, "B": 0})

    def test_reconvergence_ignores_action_identity_and_keeps_real_terminal(self):
        result = pilot.play_one(fixture("convert-immediate-reconvergence-v1"), 1, 1, 0)
        first = result["decisions"][0]
        self.assertEqual((first["legal_action_count"], first["distinct_successor_position_count"]), (2, 1))
        self.assertEqual((first["expanded_nodes"], first["cache_hits"]), (1, 1))
        self.assertEqual((result["winner"], result["terminal_reason"]), (None, "PLY_LIMIT"))
        state = initial_state(parse_definition(fixture("convert-immediate-reconvergence-v1")))
        changed_metadata = type(state)(ply=1, to_move=state.to_move, pieces=state.pieces, outcome=Outcome(Player.A, "GOAL"))
        self.assertEqual(pilot._position_key(state), pilot._position_key(changed_metadata))

    def test_existing_source_only_connect_fixture_keeps_actor_goal_priority(self):
        # Extract only literal fixture wires; never import/run the atlas builder.
        path = Path(__file__).resolve().parents[1] / "src/parity_forge/atlas_agent_benchmark.py"
        assignment = next(
            node for node in ast.parse(path.read_text()).body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "_FIXTURE_SPECS_V1" for target in node.targets)
        )
        wire = next(row[2] for row in ast.literal_eval(assignment.value) if row[0] == "swap-simultaneous-connect-v1")
        self.assertEqual(hashlib.sha256(wire.encode()).hexdigest(), "eaaf30187d95c215c2d330f1e68c92b10ff7718b85e16801de2a15353b8c3db2")
        result = pilot.play_one(json.loads(wire), 2, 2, 0)
        self.assertEqual((result["winner"], result["terminal_reason"], result["plies"]), ("A", "GOAL", 1))
        self.assertEqual(result["actions"], [{"kind": "SWAP", "from": [1, 0], "to": [1, 1]}])

    def test_existing_capture_fixture_checks_depth_sensitivity_and_minimizing_b(self):
        raw = fixture("capture-eliminate-one-sided-b-v1")
        definition = parse_definition(raw)
        state = initial_state(definition)
        values = []
        for depth in (1, 2):
            agent = TerminalOnlyMinimaxAgent(depth, 5000)
            agent.select_action(definition, state, legal_actions(definition, state), random.Random(0))
            values.append(agent.last_action_values[0][1])
        self.assertEqual(values, [0, -1])
        result = pilot.play_one(raw, 2, 1, 0)
        self.assertEqual((result["winner"], result["terminal_reason"], result["plies"]), ("B", "GOAL", 2))

    def test_repetition_is_ply_limit_and_initial_stuck_never_calls_policy(self):
        repeat = pilot.play_one(fixture("swap-both-roles-repeat-v1"), 1, 1, 0)
        self.assertEqual((repeat["winner"], repeat["terminal_reason"], repeat["plies"]), (None, "PLY_LIMIT", 3))
        with mock.patch.object(TerminalOnlyMinimaxAgent, "select_action", side_effect=AssertionError("must not act")):
            stuck = pilot.play_one(fixture("initial-stuck-zero-v1"), 2, 2, 0)
        self.assertEqual((stuck["winner"], stuck["terminal_reason"], stuck["plies"]), ("B", "NO_LEGAL_ACTION", 0))
        self.assertEqual(stuck["decisions"], [])
        self.assertEqual(stuck["nodes_by_role"], {"A": 0, "B": 0})

    def test_censor_preserves_nonempty_prefix_and_counts_failed_decision(self):
        raw = fixture("swap-both-roles-repeat-v1")
        result = pilot.play_one(raw, 1, 1, 0, max_nodes=1)
        self.assertEqual(result["status"], "SEARCH_CENSORED")
        self.assertEqual(result["plies"], 2)
        self.assertEqual(result["actions"], FIXTURE_BY_ID["swap-both-roles-repeat-v1"]["actions"][:2])
        self.assertEqual((result["winner"], result["terminal_reason"]), (None, None))
        self.assertEqual(result["nodes_by_role"], {"A": 1, "B": 1})
        self.assertEqual(result["censor"], {"role": "A", "reason": "SEARCH_BUDGET", "scope": "per-slot", "visited_nodes": 1, "max_nodes": 1})
        self.assertEqual(len(result["decisions"]), 3)
        self.assertEqual(result["decisions"][-1]["selection_status"], "SEARCH_CENSORED")
        self.assertIsNone(result["decisions"][-1]["selected_action"])
        self.assertEqual(replay_dicts(parse_definition(raw), result["actions"]).to_dict(), result["state_after_prefix"])
        partial_search = pilot.play_one(fixture("push-win-draw-loss-v1"), 1, 1, 0, max_nodes=2)
        self.assertEqual(partial_search["nodes_by_role"], {"A": 2, "B": 0})
        self.assertEqual(partial_search["decisions"][0]["expanded_nodes"], 2)
        self.assertEqual(partial_search["actions"], [])

    def test_unexpected_failure_retains_prefix_and_never_becomes_censor(self):
        raw = fixture("swap-both-roles-repeat-v1")
        original = RandomAgent.select_action
        calls = []
        def fail_second(agent, definition, state, actions, rng):
            calls.append(state.ply)
            if state.ply == 1:
                raise RuntimeError("calibration failure")
            return original(agent, definition, state, actions, rng)
        with mock.patch.object(RandomAgent, "select_action", fail_second):
            with self.assertRaises(pilot.PilotPlayError) as raised:
                pilot.play_one(raw, 0, 0, 0)
        row = raised.exception.partial_record
        self.assertEqual((row["status"], row["plies"]), ("FAILED", 1))
        self.assertEqual(row["failure"]["type"], "RuntimeError")
        self.assertEqual(row["decisions"][-1]["selection_status"], "FAILED")
        self.assertEqual(row["decisions"][-1]["expanded_nodes"], 0)
        self.assertEqual(replay_dicts(parse_definition(raw), row["actions"]).to_dict(), row["state_after_prefix"])

    def test_node_consuming_exception_and_illegal_action_finalize_failed_decision(self):
        raw = fixture("swap-both-roles-repeat-v1")
        original = TerminalOnlyMinimaxAgent.select_action
        for failure in ("exception", "illegal_action"):
            with self.subTest(failure=failure):
                def fail_after_search(agent, definition, state, actions, rng):
                    selected = original(agent, definition, state, actions, rng)
                    if state.ply == 2:
                        if failure == "exception":
                            raise RuntimeError("failure after charged search")
                        return Action.place(0, 0)
                    return selected
                with mock.patch.object(TerminalOnlyMinimaxAgent, "select_action", fail_after_search):
                    with self.assertRaises(pilot.PilotPlayError) as raised:
                        pilot.play_one(raw, 1, 1, 0)
                row = raised.exception.partial_record
                self.assertEqual((row["status"], row["plies"]), ("FAILED", 2))
                self.assertEqual(row["nodes_by_role"], {"A": 2, "B": 1})
                decision = row["decisions"][-1]
                self.assertEqual(decision["selection_status"], "FAILED")
                self.assertEqual((decision["nodes_before"], decision["nodes_after"], decision["expanded_nodes"]), (1, 2, 1))
                self.assertIsNone(decision["selected_action"])
                self.assertIsNone(row["censor"])
                self.assertEqual(replay_dicts(parse_definition(raw), row["actions"]).to_dict(), row["state_after_prefix"])

    def test_illegal_action_input_drift_and_replay_mismatch_fail_with_evidence(self):
        raw = fixture("push-win-draw-loss-v1")
        with mock.patch.object(RandomAgent, "select_action", return_value=Action.place(0, 0)):
            with self.assertRaises(pilot.PilotPlayError):
                pilot.play_one(raw, 0, 0, 0)
        original = RandomAgent.select_action
        def mutate(agent, definition, state, actions, rng):
            raw["name"] += " changed"
            return original(agent, definition, state, actions, rng)
        with mock.patch.object(RandomAgent, "select_action", mutate):
            with self.assertRaisesRegex(pilot.PilotPlayError, "input drifted"):
                pilot.play_one(raw, 0, 0, 0)
        with mock.patch.object(pilot, "replay_dicts", return_value=None):
            with self.assertRaisesRegex(pilot.PilotPlayError, "replayed prefix") as raised:
                pilot.play_one(fixture("push-win-draw-loss-v1"), 1, 1, 0)
        self.assertEqual(raised.exception.partial_record["plies"], 1)

    def test_policy_seed_and_node_cap_reject_boolean_aliases(self):
        raw = fixture("push-win-draw-loss-v1")
        for args in ((True, 0, 0, 5000), (3, 0, 0, 5000), (0, 0, True, 5000), (0, 0, 0, 0), (0, 0, 0, True)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                pilot.play_one(raw, *args)


class PilotSummaryTests(unittest.TestCase):
    def test_all_draw_empty_and_partial_completion_have_separate_denominators(self):
        raw = fixture("swap-both-roles-repeat-v1")
        complete = pilot.play_one(raw, 1, 1, 0)
        censored = pilot.play_one(raw, 1, 1, 0, max_nodes=1)
        result = pilot.summarize_games([complete, censored], 3)
        self.assertEqual((result["completed"], result["search_censored"], result["not_started"]), (1, 1, 1))
        self.assertEqual((result["draws"], result["ply_limit_draws"], result["natural_draws"]), (1, 1, 0))
        self.assertEqual(result["decisive_games"], 0)
        self.assertIsNone(result["decisive_a_share"])
        self.assertEqual(result["lengths"]["completed"]["mean"], 3)
        self.assertEqual(result["lengths"]["censored_prefixes"]["mean"], 2)
        self.assertEqual(result["choices"]["decision_starts"], 6)
        empty = pilot.summarize_games([], 4)
        self.assertEqual((empty["condition"], empty["attempted"], empty["not_started"]), (None, 0, 4))
        self.assertIsNone(empty["lengths"]["completed"]["mean"])

    def test_first_player_pooled_false_balance_and_mixed_policies_are_rejected(self):
        raw = fixture("push-win-draw-loss-v1")
        a = pilot.play_one(raw, 1, 1, 0)
        b = pilot.play_one(role_swapped(raw), 1, 1, 0)
        self.assertEqual((a["winner"], b["winner"]), ("A", "B"))
        with self.assertRaisesRegex(ValueError, "cannot pool"):
            pilot.summarize_games([a, b], 2)
        self.assertEqual(pilot.summarize_games([a], 1)["decisive_a_share"], 1)
        self.assertEqual(pilot.summarize_games([b], 1)["decisive_a_share"], 0)
        changed = copy.deepcopy(a)
        changed["policy_b"] = 2
        with self.assertRaisesRegex(ValueError, "cannot pool"):
            pilot.summarize_games([a, changed], 2)

    def test_nontrivial_count_control_and_reconvergence_are_descriptive(self):
        # Hand-authored count rows vary only result labels, not game definitions.
        base = pilot.play_one(fixture("convert-immediate-reconvergence-v1"), 1, 1, 0)
        rows = []
        for winner, reason in (("A", "GOAL"), ("A", "GOAL"), ("B", "GOAL"), (None, "PLY_LIMIT"), (None, "NO_LEGAL_ACTION")):
            row = copy.deepcopy(base)
            row.update(winner=winner, terminal_reason=reason)
            rows.append(row)
        result = pilot.summarize_games(rows, 5)
        self.assertEqual((result["a_wins"], result["b_wins"], result["natural_draws"], result["ply_limit_draws"]), (2, 1, 1, 1))
        self.assertEqual(result["decisive_a_share"], 2 / 3)
        self.assertEqual(result["choices"]["reconvergent_decisions"], 5)
        self.assertNotIn("fairness", result)
        self.assertNotIn("confidence_interval", result)
        self.assertNotIn("FURTHER_DIAGNOSIS", result)

    def test_invalid_censor_outcome_and_denominator_fail(self):
        row = pilot.play_one(fixture("swap-both-roles-repeat-v1"), 1, 1, 0, max_nodes=1)
        with self.assertRaises(ValueError):
            pilot.summarize_games([row], 0)
        row["terminal_reason"] = "PLY_LIMIT"
        with self.assertRaisesRegex(ValueError, "must not carry"):
            pilot.summarize_games([row], 1)


if __name__ == "__main__":
    unittest.main()
