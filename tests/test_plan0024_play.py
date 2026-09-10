"""Synthetic 3x3 tests only; no Plan 0024 candidate data is loaded."""

import copy
import json
import random
import unittest
from unittest import mock

from parity_forge.agents import RandomAgent, SearchBudgetExceeded
from parity_forge.dsl import Player, canonical_json, parse_definition
from parity_forge.engine import Action, initial_state, legal_actions
from parity_forge.play import play_game
from parity_forge.terminal_search import TerminalOnlyMinimaxAgent
from scripts import plan0024_play as recorder


def tiny_race():
    """A small decisive race with branching and at least three plies."""

    raw = {
        "schema_version": 4,
        "name": "plan0024 synthetic branching race",
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
    return json.loads(canonical_json(parse_definition(raw)))


def tiny_single_lane():
    """A deterministic decisive race used to expose cumulative node caps."""

    raw = {
        "schema_version": 4,
        "name": "plan0024 synthetic single lane",
        "board_size": 3,
        "first_player": "A",
        "max_plies": 4,
        "roles": {
            "A": {
                "action": {
                    "kind": "PUSH",
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
                    "kind": "MOVE",
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
    return json.loads(canonical_json(parse_definition(raw)))


def make_agent(policy, cap):
    if policy == "R":
        return RandomAgent()
    return TerminalOnlyMinimaxAgent(int(policy[1]), cap)


def without_elapsed(row):
    return {key: value for key, value in row.items() if key != "elapsed_seconds"}


class Plan0024RecorderTests(unittest.TestCase):
    def test_all_sixteen_policy_pairs_match_public_play_game(self):
        raw = tiny_race()
        definition = parse_definition(raw)
        self.assertEqual(definition.board_size, 3)
        self.assertEqual(len(recorder.POLICIES) ** 2, 16)
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
                self.assertEqual(
                    (actual["replay_count"], replay.call_count), (1, 1)
                )
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
                        recorder.play_one(
                            raw, policy_a, policy_b, 17, 10000
                        )
                    ),
                )
                self.assertIsNone(actual["unconfirmed_action"])
                json.dumps(actual, allow_nan=False)

    def test_fresh_agents_and_one_persistent_seeded_rng_per_game(self):
        raw = tiny_race()
        original = RandomAgent.select_action
        observed_agents = []
        observed_rngs = []
        observed_states = []

        def observe(agent, definition, state, choices, rng):
            observed_agents.append(agent)
            observed_rngs.append(rng)
            observed_states.append(rng.getstate())
            return original(agent, definition, state, choices, rng)

        with mock.patch.object(RandomAgent, "select_action", observe):
            first = recorder.play_one(raw, "R", "R", 19, 1)
            split = len(observed_rngs)
            second = recorder.play_one(raw, "R", "R", 19, 1)

        self.assertEqual((first["status"], second["status"]), ("COMPLETE", "COMPLETE"))
        self.assertGreaterEqual(split, 2)
        self.assertEqual(len({id(rng) for rng in observed_rngs[:split]}), 1)
        self.assertIsNot(observed_rngs[0], observed_rngs[split])
        self.assertEqual(len({id(agent) for agent in observed_agents}), 4)
        self.assertEqual(observed_states[:split], observed_states[split:])
        self.assertEqual(first["nodes_by_role"], {"A": 0, "B": 0})
        self.assertEqual(
            set(first["node_accounting"].values()),
            {"UNMETERED_RANDOM_SELECTION_NOT_ZERO_COMPUTE"},
        )

    def test_terminal_values_and_cumulative_cap_censor_are_audited(self):
        complete = recorder.play_one(tiny_single_lane(), "T4", "T3", 0, 100)
        self.assertEqual(
            (complete["status"], complete["winner"], complete["terminal_reason"]),
            ("COMPLETE", "A", "GOAL"),
        )
        self.assertTrue(
            all(
                "last_action_values" in decision
                for decision in complete["decisions"]
            )
        )

        censored = recorder.play_one(tiny_single_lane(), "T2", "T2", 0, 2)
        self.assertEqual(censored["status"], "UNKNOWN_CENSORED", censored)
        self.assertEqual((censored["winner"], censored["terminal_reason"]), (None, None))
        self.assertEqual(censored["nodes_by_role"], {"A": 2, "B": 2})
        self.assertEqual(censored["censor"]["visited_nodes"], 2)
        self.assertEqual(censored["decisions"][-1]["nodes_before"], 2)
        self.assertEqual(
            censored["decisions"][-1]["selection_status"],
            "UNKNOWN_CENSORED",
        )
        self.assertEqual(censored["replay_count"], 1)
        self.assertTrue(censored["replay_verified"])

    def test_failure_keeps_only_confirmed_prefix_and_charged_nodes(self):
        raw = tiny_single_lane()
        original = TerminalOnlyMinimaxAgent.select_action

        def fail_after_search(agent, definition, state, choices, rng):
            selected = original(agent, definition, state, choices, rng)
            if state.ply == 1:
                raise RuntimeError("synthetic failure after search")
            return selected

        with mock.patch.object(
            TerminalOnlyMinimaxAgent, "select_action", fail_after_search
        ):
            row = recorder.play_one(raw, "T2", "T2", 0, 100)
        self.assertEqual((row["status"], row["plies"]), ("FAILED", 1))
        self.assertEqual(len(row["actions"]), 1)
        self.assertIsNone(row["unconfirmed_action"])
        self.assertEqual(row["replay_count"], 1)
        self.assertTrue(row["replay_verified"])
        self.assertGreater(row["decisions"][-1]["charged_nodes"], 0)
        self.assertEqual(row["decisions"][-1]["selection_status"], "FAILED")

    def test_apply_failure_separates_unconfirmed_action(self):
        with mock.patch(
            "parity_forge.play.apply_action",
            side_effect=RuntimeError("synthetic apply failure"),
        ), mock.patch.object(
            recorder, "replay_dicts", wraps=recorder.replay_dicts
        ) as replay:
            row = recorder.play_one(tiny_race(), "R", "R", 0, 1)
        self.assertEqual((row["status"], row["plies"]), ("FAILED", 0))
        self.assertEqual(row["actions"], [])
        self.assertEqual(replay.call_count, 1)
        self.assertTrue(row["replay_verified"])
        self.assertEqual(
            row["unconfirmed_action"], row["decisions"][0]["selected_action"]
        )

    def test_noncanonical_choices_illegal_selection_and_bad_censor_fail_closed(self):
        raw = tiny_race()

        def noncanonical_loop(definition, agents, seed):
            state = initial_state(definition)
            choices = tuple(reversed(legal_actions(definition, state)))
            agents[Player.A].select_action(
                definition, state, choices, random.Random(seed)
            )
            raise AssertionError("selection should reject noncanonical choices")

        with mock.patch.object(recorder, "play_game", noncanonical_loop):
            noncanonical = recorder.play_one(raw, "R", "R", 0, 1)
        self.assertEqual(noncanonical["status"], "FAILED")
        self.assertEqual(
            noncanonical["decisions"][0]["selection_status"], "FAILED"
        )

        with mock.patch.object(
            RandomAgent,
            "select_action",
            return_value=Action.place(0, 0),
        ):
            illegal = recorder.play_one(raw, "R", "R", 0, 1)
        self.assertEqual(illegal["status"], "FAILED")

        with mock.patch.object(
            TerminalOnlyMinimaxAgent,
            "select_action",
            side_effect=SearchBudgetExceeded("synthetic", 1, 1),
        ):
            bad_censor = recorder.play_one(raw, "T2", "T2", 0, 1)
        self.assertEqual(bad_censor["status"], "FAILED")

    def test_input_immutability_replay_failure_and_configuration_guards(self):
        raw = tiny_race()
        snapshot = copy.deepcopy(raw)
        row = recorder.play_one(raw, "R", "T2", 5, 1000)
        self.assertEqual(raw, snapshot)
        self.assertEqual(row["status"], "COMPLETE")

        with mock.patch.object(recorder, "replay_dicts", return_value=None) as replay:
            mismatch = recorder.play_one(tiny_race(), "T2", "R", 0, 1000)
        self.assertEqual((mismatch["status"], replay.call_count), ("FAILED", 1))

        drifting = tiny_race()
        original = RandomAgent.select_action

        def mutate_input(agent, definition, state, choices, rng):
            drifting["name"] = "externally drifted"
            return original(agent, definition, state, choices, rng)

        with mock.patch.object(RandomAgent, "select_action", mutate_input):
            drift = recorder.play_one(drifting, "R", "R", 0, 1)
        self.assertEqual(drift["status"], "FAILED")
        self.assertIn("definition drift", drift["verification_error"]["message"])

        bad_schema = tiny_race()
        bad_schema["schema_version"] = 3
        for args in (
            ("T5", "R", 0, 1),
            (True, "R", 0, 1),
            ("R", "R", True, 1),
            ("R", "R", 0, 0),
            ("R", "R", 0, True),
        ):
            with self.assertRaises(ValueError):
                recorder.play_one(raw, *args)
        with self.assertRaises(ValueError):
            recorder.play_one(bad_schema, "R", "R", 0, 1)


if __name__ == "__main__":
    unittest.main()
