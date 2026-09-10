"""Synthetic 3x3 recorder tests; the Plan 0028 candidate is never loaded."""

import copy
import json
import random
import unittest
from unittest import mock

from parity_forge.agents import GoalDirectedAgent, MinimaxAgent, SearchBudgetExceeded
from parity_forge.dsl import Player, canonical_json, parse_definition
from parity_forge.engine import (
    Action,
    apply_action,
    initial_state,
    legal_actions,
)
from parity_forge.play import play_game
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent
from scripts import plan0028_play as recorder


def _canonical_definition(raw):
    return json.loads(canonical_json(parse_definition(raw)))


def tiny_race():
    """A branching, decisive 3x3 race for all five existing policies."""

    return _canonical_definition(
        {
            "schema_version": 4,
            "name": "plan0028 synthetic branching race",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 7,
            "roles": {
                "A": {
                    "action": {
                        "kind": "MOVE_CAPTURE",
                        "piece": "a",
                        "vectors": [[1, -1], [1, 0], [1, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "a",
                        "edge": "BOTTOM",
                    },
                },
                "B": {
                    "action": {
                        "kind": "PUSH",
                        "piece": "b",
                        "vectors": [[-1, -1], [-1, 0], [-1, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "b",
                        "edge": "TOP",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "a", "position": [0, 0]},
                {"owner": "B", "piece": "b", "position": [2, 2]},
            ],
        }
    )


def tiny_single_lane():
    """A forced decisive line long enough to expose cumulative node caps."""

    return _canonical_definition(
        {
            "schema_version": 4,
            "name": "plan0028 synthetic single lane",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 4,
            "roles": {
                "A": {
                    "action": {
                        "kind": "MOVE",
                        "piece": "a",
                        "vectors": [[1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "a",
                        "edge": "BOTTOM",
                    },
                },
                "B": {
                    "action": {
                        "kind": "PUSH",
                        "piece": "b",
                        "vectors": [[-1, 0]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "b",
                        "edge": "TOP",
                    },
                },
            },
            "initial_pieces": [
                {"owner": "A", "piece": "a", "position": [0, 0]},
                {"owner": "B", "piece": "b", "position": [2, 2]},
            ],
        }
    )


def tiny_immediate_goal():
    """A final-ply GOAL must take precedence over the ply limit."""

    raw = tiny_single_lane()
    raw["name"] = "plan0028 synthetic immediate goal"
    raw["max_plies"] = 1
    raw["initial_pieces"][0]["position"] = [1, 0]
    return _canonical_definition(raw)


def tiny_initial_stuck():
    """A full synthetic board on which the first player has no action."""

    pieces = []
    for row in range(3):
        for column in range(3):
            pieces.append(
                {
                    "owner": "B" if (row, column) == (1, 1) else "A",
                    "piece": "b" if (row, column) == (1, 1) else "block",
                    "position": [row, column],
                }
            )
    return _canonical_definition(
        {
            "schema_version": 4,
            "name": "plan0028 synthetic initial stuck",
            "board_size": 3,
            "first_player": "A",
            "max_plies": 4,
            "roles": {
                "A": {
                    "action": {"kind": "PLACE", "piece": "stone"},
                    "goal": {
                        "kind": "CONNECT_EDGES",
                        "piece": "stone",
                        "edges": ["TOP", "BOTTOM"],
                    },
                },
                "B": {
                    "action": {
                        "kind": "HOP",
                        "piece": "b",
                        "vectors": [[0, 1]],
                    },
                    "goal": {
                        "kind": "REACH_EDGE",
                        "piece": "b",
                        "edge": "TOP",
                    },
                },
            },
            "initial_pieces": pieces,
        }
    )


def make_agent(policy, cap):
    if policy == "G":
        return GoalDirectedAgent()
    if policy.startswith("T"):
        return TerminalOnlyMinimaxAgent(int(policy[1]), cap)
    return MinimaxAgent(depth=int(policy[1]), max_total_nodes=cap)


def without_elapsed(row):
    return {key: value for key, value in row.items() if key != "elapsed_seconds"}


def assert_complete_trace(testcase, definition, row):
    """Check full states, canonical choices, and selected/applied alignment."""

    testcase.assertEqual(len(row["decisions"]), row["plies"])
    state = initial_state(definition)
    for index, decision in enumerate(row["decisions"]):
        choices = legal_actions(definition, state)
        testcase.assertEqual(decision["ply"], index)
        testcase.assertEqual(decision["actor"], state.to_move.value)
        testcase.assertEqual(decision["input_state"], state.to_dict())
        testcase.assertEqual(decision["legal_action_count"], len(choices))
        testcase.assertEqual(
            decision["legal_actions"], [action.to_dict() for action in choices]
        )
        testcase.assertEqual(decision["selected_action"], row["actions"][index])
        testcase.assertEqual(decision["selection_status"], "SELECTED")
        testcase.assertEqual(
            decision["charged_nodes"],
            decision["nodes_after"] - decision["nodes_before"],
        )
        state = apply_action(definition, state, choices[
            [action.to_dict() for action in choices].index(row["actions"][index])
        ])
    testcase.assertEqual(state.to_dict(), row["state_after_prefix"])


class Plan0028RecorderTests(unittest.TestCase):
    def test_policy_surface_and_all_pairs_match_public_game(self):
        raw = tiny_race()
        definition = parse_definition(raw)
        self.assertEqual(recorder.POLICIES, ("T2", "T3", "H2", "H3", "G"))
        self.assertEqual((definition.board_size, len(recorder.POLICIES) ** 2), (3, 25))
        for policy_a in recorder.POLICIES:
            for policy_b in recorder.POLICIES:
                agents = {
                    Player.A: make_agent(policy_a, 10000),
                    Player.B: make_agent(policy_b, 10000),
                }
                expected = play_game(definition, agents, 17).to_dict()
                with mock.patch.object(
                    recorder, "replay_dicts", wraps=recorder.replay_dicts
                ) as replay:
                    actual = recorder.play_one(
                        raw, policy_a, policy_b, 17, 10000
                    )
                self.assertEqual(actual["status"], "COMPLETE", actual)
                self.assertEqual(actual["observed_game_record"], expected)
                self.assertEqual((actual["replay_count"], replay.call_count), (1, 1))
                self.assertTrue(actual["replay_verified"])
                self.assertEqual(
                    actual["nodes_by_role"],
                    {
                        role.value: getattr(agent, "total_nodes", 0)
                        for role, agent in agents.items()
                    },
                )
                self.assertEqual(
                    without_elapsed(actual),
                    without_elapsed(
                        recorder.play_one(raw, policy_a, policy_b, 17, 10000)
                    ),
                )
                self.assertIsNone(actual["unconfirmed_action"])
                assert_complete_trace(self, definition, actual)
                json.dumps(actual, allow_nan=False)

    def test_fresh_agents_and_one_persistent_rng_per_game(self):
        raw = tiny_race()
        original = GoalDirectedAgent.select_action
        observed_agents = []
        observed_rngs = []
        observed_rng_states = []

        def observe(agent, definition, state, choices, rng):
            observed_agents.append(agent)
            observed_rngs.append(rng)
            observed_rng_states.append(rng.getstate())
            return original(agent, definition, state, choices, rng)

        with mock.patch.object(GoalDirectedAgent, "select_action", observe):
            first = recorder.play_one(raw, "G", "G", 19, 1)
            split = len(observed_rngs)
            second = recorder.play_one(raw, "G", "G", 19, 1)

        self.assertEqual((first["status"], second["status"]), ("COMPLETE", "COMPLETE"))
        self.assertGreaterEqual(split, 2)
        self.assertEqual(len({id(rng) for rng in observed_rngs[:split]}), 1)
        self.assertIsNot(observed_rngs[0], observed_rngs[split])
        self.assertEqual(len({id(agent) for agent in observed_agents}), 4)
        self.assertEqual(observed_rng_states[:split], observed_rng_states[split:])
        self.assertEqual(first["nodes_by_role"], {"A": 0, "B": 0})
        self.assertEqual(
            set(first["node_accounting"].values()),
            {"UNMETERED_GOAL_PROGRESS_NOT_ZERO_COMPUTE"},
        )
        for policy in ("T2", "H2"):
            row = recorder.play_one(raw, policy, policy, 0, 10000)
            for owner in ("A", "B"):
                first_decision = next(
                    decision
                    for decision in row["decisions"]
                    if decision["actor"] == owner
                )
                self.assertEqual(first_decision["nodes_before"], 0)

    def test_censor_keeps_only_confirmed_prefix_and_failed_decision(self):
        raw = tiny_single_lane()
        definition = parse_definition(raw)
        for policy in ("T2", "H2"):
            with mock.patch.object(
                recorder, "replay_dicts", wraps=recorder.replay_dicts
            ) as replay:
                row = recorder.play_one(raw, policy, policy, 0, 2)
            self.assertEqual(
                (row["status"], row["plies"], replay.call_count),
                ("UNKNOWN_CENSORED", 2, 1),
            )
            self.assertEqual((row["winner"], row["terminal_reason"]), (None, None))
            self.assertEqual(row["nodes_by_role"], {"A": 2, "B": 2})
            self.assertEqual(len(row["actions"]), 2)
            self.assertEqual(row["decisions"][-1]["ply"], 2)
            self.assertEqual(
                row["decisions"][-1]["selection_status"], "UNKNOWN_CENSORED"
            )
            self.assertIsNone(row["decisions"][-1]["selected_action"])
            self.assertIsNone(row["unconfirmed_action"])
            self.assertTrue(row["replay_verified"])
            state = initial_state(definition)
            for index, action_dict in enumerate(row["actions"]):
                decision = row["decisions"][index]
                choices = legal_actions(definition, state)
                self.assertEqual(decision["input_state"], state.to_dict())
                self.assertEqual(
                    decision["legal_actions"],
                    [action.to_dict() for action in choices],
                )
                self.assertEqual(decision["selected_action"], action_dict)
                selected = next(
                    action for action in choices if action.to_dict() == action_dict
                )
                state = apply_action(definition, state, selected)
            self.assertEqual(state.to_dict(), row["state_after_prefix"])
            self.assertEqual(
                row["decisions"][-1]["input_state"], row["state_after_prefix"]
            )

    def test_search_exception_and_illegal_selection_retain_prefix(self):
        raw = tiny_single_lane()
        original = TerminalOnlyMinimaxAgent.select_action
        for illegal in (False, True):
            def fail(agent, definition, state, choices, rng):
                selected = original(agent, definition, state, choices, rng)
                if state.ply == 1:
                    if illegal:
                        return Action.place(0, 0)
                    raise RuntimeError("synthetic failure after charged nodes")
                return selected

            with mock.patch.object(TerminalOnlyMinimaxAgent, "select_action", fail):
                row = recorder.play_one(raw, "T2", "T2", 0, 100)
            self.assertEqual((row["status"], row["plies"]), ("FAILED", 1))
            self.assertEqual(len(row["actions"]), 1)
            self.assertEqual(row["replay_count"], 1)
            self.assertTrue(row["replay_verified"])
            self.assertIsNone(row["unconfirmed_action"])
            self.assertGreater(row["decisions"][-1]["charged_nodes"], 0)
            self.assertEqual(row["decisions"][-1]["selection_status"], "FAILED")

    def test_apply_failure_separates_unconfirmed_selection(self):
        with mock.patch(
            "parity_forge.play.apply_action",
            side_effect=RuntimeError("synthetic apply failure"),
        ), mock.patch.object(
            recorder, "replay_dicts", wraps=recorder.replay_dicts
        ) as replay:
            row = recorder.play_one(tiny_race(), "G", "G", 0, 1)
        self.assertEqual((row["status"], row["plies"]), ("FAILED", 0))
        self.assertEqual(row["actions"], [])
        self.assertEqual((row["replay_count"], replay.call_count), (1, 1))
        self.assertTrue(row["replay_verified"])
        self.assertEqual(
            row["unconfirmed_action"], row["decisions"][0]["selected_action"]
        )
        self.assertIn(
            row["unconfirmed_action"], row["decisions"][0]["legal_actions"]
        )

    def test_noncanonical_choices_replay_drift_and_bad_censor_fail_closed(self):
        raw = tiny_race()

        for mode in ("reversed", "proper_subset"):
            def noncanonical_loop(definition, agents, seed):
                state = initial_state(definition)
                full = legal_actions(definition, state)
                self.assertGreater(len(full), 1)
                choices = tuple(reversed(full)) if mode == "reversed" else full[:1]
                agents[Player.A].select_action(
                    definition, state, choices, random.Random(seed)
                )
                raise AssertionError("incomplete/noncanonical choices should be rejected")

            with self.subTest(mode=mode), mock.patch.object(
                recorder, "play_game", noncanonical_loop
            ):
                noncanonical = recorder.play_one(raw, "G", "G", 0, 1)
            self.assertEqual(noncanonical["status"], "FAILED")
            self.assertEqual(
                noncanonical["decisions"][0]["selection_status"], "FAILED"
            )
            self.assertIsNone(noncanonical["decisions"][0]["legal_actions"])

        with mock.patch.object(recorder, "replay_dicts", return_value=None) as replay:
            mismatch = recorder.play_one(tiny_race(), "T2", "H2", 0, 1000)
        self.assertEqual((mismatch["status"], replay.call_count), ("FAILED", 1))

        with mock.patch.object(
            MinimaxAgent,
            "select_action",
            side_effect=SearchBudgetExceeded("per-candidate", 1, 1),
        ):
            bad_censor = recorder.play_one(tiny_race(), "H2", "H2", 0, 1)
        self.assertEqual(bad_censor["status"], "FAILED")

        def wrong_scope(agent, definition, state, choices, rng):
            agent.total_nodes = 1
            raise SearchBudgetExceeded("bogus-scope", 1, 1)

        with mock.patch.object(MinimaxAgent, "select_action", wrong_scope):
            bad_scope = recorder.play_one(tiny_race(), "H2", "H2", 0, 1)
        self.assertEqual(bad_scope["status"], "FAILED")
        self.assertEqual(
            bad_scope["decisions"][0]["selection_status"], "FAILED"
        )

        drifting = tiny_race()
        original = GoalDirectedAgent.select_action

        def mutate_input(agent, definition, state, choices, rng):
            drifting["name"] = "externally drifted"
            return original(agent, definition, state, choices, rng)

        with mock.patch.object(GoalDirectedAgent, "select_action", mutate_input):
            drift = recorder.play_one(drifting, "G", "G", 0, 1)
        self.assertEqual(drift["status"], "FAILED")
        self.assertIn("definition drift", drift["verification_error"]["message"])

    def test_terminal_order_initial_stuck_and_configuration_guards(self):
        goal = recorder.play_one(tiny_immediate_goal(), "T3", "H3", 0, 100)
        self.assertEqual(
            (goal["status"], goal["winner"], goal["terminal_reason"], goal["plies"]),
            ("COMPLETE", "A", "GOAL", 1),
        )

        with mock.patch.object(
            GoalDirectedAgent, "select_action", side_effect=AssertionError
        ):
            stuck = recorder.play_one(tiny_initial_stuck(), "G", "G", 0, 1)
        self.assertEqual(
            (
                stuck["status"],
                stuck["winner"],
                stuck["terminal_reason"],
                stuck["plies"],
                stuck["replay_count"],
            ),
            ("COMPLETE", "B", "NO_LEGAL_ACTION", 0, 1),
        )

        raw = tiny_race()
        snapshot = copy.deepcopy(raw)
        self.assertEqual(recorder.play_one(raw, "G", "T2", 5, 1000)["status"], "COMPLETE")
        self.assertEqual(raw, snapshot)
        for args in (
            ("T4", "G", 0, 1),
            ("G", "H4", 0, 1),
            ("R", "G", 0, 1),
            (True, "G", 0, 1),
            ("G", "G", True, 1),
            ("G", "G", 0, 0),
            ("G", "G", 0, True),
        ):
            with self.assertRaises(ValueError):
                recorder.play_one(raw, *args)
        bad_schema = copy.deepcopy(raw)
        bad_schema["schema_version"] = 3
        with self.assertRaises(ValueError):
            recorder.play_one(bad_schema, "G", "G", 0, 1)


if __name__ == "__main__":
    unittest.main()
