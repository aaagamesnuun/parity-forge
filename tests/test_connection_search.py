"""Small functional fixtures and controlled trees; no registered games or 9x9 search."""

from dataclasses import FrozenInstanceError
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from parity_forge.connection import Action, Definition, State, apply_action, initial_state
from parity_forge import connection_search as search
from parity_forge.dsl import Player


def definition(size=3, first=Player.A, bridge=0, conversion=0):
    return Definition("search-fixture", size, first, bridge, conversion)


class CountingRng:
    def __init__(self):
        self.choices = []

    def choice(self, values):
        self.choices.append(tuple(values))
        return values[-1]


class ConnectionDistanceTests(unittest.TestCase):
    def test_bounded_topology_cache_does_not_rebuild_per_evaluation(self):
        search._topology.cache_clear()
        self.addCleanup(search._topology.cache_clear)
        game = definition()
        empty = initial_state(game)
        with patch.object(search, "neighbors", wraps=search.neighbors) as adjacent:
            self.assertEqual(search.connection_distance(game, empty, Player.A), 3)
            self.assertEqual(adjacent.call_count, 9)
            self.assertEqual(search.connection_distance(game, empty, Player.B), 3)
            self.assertEqual(search.evaluate_state(game, empty), 0)
            self.assertEqual(adjacent.call_count, 9)
        self.assertEqual(search._topology.cache_info().maxsize, 32)

    def test_empty_start_cost_and_role_signs(self):
        game = definition()
        empty = initial_state(game)
        self.assertEqual(search.connection_distance(game, empty, Player.A), 3)
        self.assertEqual(search.connection_distance(game, empty, Player.B), 3)
        self.assertEqual(search.evaluate_state(game, empty), 0)
        one_a = apply_action(game, empty, Action("PLACE_ONE", (4,)))
        self.assertEqual(search.connection_distance(game, one_a, Player.A), 2)
        self.assertEqual(search.evaluate_state(game, one_a), 1)
        game_b = definition(first=Player.B)
        one_b = apply_action(game_b, initial_state(game_b), Action("PLACE_ONE", (4,)))
        self.assertEqual(search.evaluate_state(game_b, one_b), -1)
        at_target = apply_action(game, empty, Action("PLACE_ONE", (5,)))
        self.assertEqual(search.connection_distance(game, at_target, Player.A), 2)

    def test_terminal_scores_blocked_paths_and_hex_diagonal(self):
        game = definition()
        a_win = State((1 << 2) | (1 << 4) | (1 << 6), (1 << 0) | (1 << 8),
                      0, 0, Player.A, 5, Player.A)
        self.assertEqual(search.connection_distance(game, a_win, Player.A), 0)
        self.assertEqual(search.connection_distance(game, a_win, Player.B), 10)
        self.assertEqual(search.evaluate_state(game, a_win), 1000)
        game_b = definition(first=Player.B)
        b_win = State(a_win.b, a_win.a, 0, 0, Player.B, 5, Player.B)
        self.assertEqual(search.connection_distance(game_b, b_win, Player.B), 0)
        self.assertEqual(search.connection_distance(game_b, b_win, Player.A), 10)
        self.assertEqual(search.evaluate_state(game_b, b_win), -1000)

    def test_credits_add_no_static_bonus_and_invalid_role_is_rejected(self):
        plain, resources = definition(), definition(bridge=3, conversion=2)
        self.assertEqual(search.evaluate_state(plain, initial_state(plain)),
                         search.evaluate_state(resources, initial_state(resources)))
        with self.assertRaises(ValueError):
            search.connection_distance(plain, initial_state(plain), "C")


class ConnectionSelectionTests(unittest.TestCase):
    def select(self, game, state, policy="connection-search-v1", rng=None,
               cap=32768, depth=3, expired=lambda: False):
        return search.select_action(game, state, policy, random.Random(10) if rng is None else rng,
                                    cap, depth, expired)

    def test_random_is_seeded_uniform_choice_without_speculation(self):
        game = definition(size=2, bridge=1)
        state = initial_state(game)
        expected = random.Random(9).choice(search.legal_actions(game, state))
        with patch.object(search, "apply_action", side_effect=AssertionError("no speculation")):
            selection = self.select(game, state, "random-v1", random.Random(9), cap=0)
        self.assertEqual(selection.action, expected)
        self.assertEqual(selection.search_transitions, 0)
        self.assertEqual(selection.completed_depth, 0)
        self.assertFalse(selection.fallback)
        with self.assertRaises(FrozenInstanceError):
            selection.completed_depth = 1

    def test_greedy_actual_cost_and_determinism_on_small_board(self):
        game = definition(size=2)
        state = initial_state(game)
        actions = search.legal_actions(game, state)
        first = self.select(game, state, "connection-greedy-v1", cap=len(actions))
        again = self.select(game, state, "connection-greedy-v1", cap=len(actions))
        self.assertEqual(first, again)
        self.assertEqual(first.completed_depth, 1)
        self.assertEqual(first.search_transitions, len(actions))
        self.assertFalse(first.budget_exhausted)
        self.assertFalse(first.fallback)

    def test_no_completed_iteration_uses_tagged_canonical_fallback_without_rng(self):
        game = definition(size=2)
        state = initial_state(game)
        rng = CountingRng()
        for cap in (0, 1):
            selection = self.select(game, state, rng=rng, cap=cap)
            self.assertEqual(selection.action, search.legal_actions(game, state)[0])
            self.assertEqual(selection.completed_depth, 0)
            self.assertEqual(selection.search_transitions, cap)
            self.assertTrue(selection.budget_exhausted)
            self.assertTrue(selection.fallback)
        self.assertEqual(rng.choices, [])

    def controlled_tree(self, root_player=Player.A, shallow=(5, 5), deep=((5, 5), (5, 0))):
        states = {"r": SimpleNamespace(label="r", to_move=root_player, winner=None)}
        actions = (Action("PLACE_ONE", (0,)), Action("PLACE_ONE", (1,)))
        scores, edges = {}, {}
        for index, branch in enumerate(("x", "y")):
            states[branch] = SimpleNamespace(label=branch, to_move=root_player.other, winner=None)
            edges[("r", actions[index])] = states[branch]
            scores[branch] = shallow[index]
            for j in range(2):
                label = branch + str(j)
                states[label] = SimpleNamespace(label=label, to_move=root_player, winner=None)
                edges[(branch, actions[j])] = states[label]
                scores[label] = deep[index][j]
        patches = [patch.object(search, "validate_state"),
                   patch.object(search, "legal_actions", side_effect=lambda d, s: actions),
                   patch.object(search, "apply_action", side_effect=lambda d, s, a: edges[(s.label, a)]),
                   patch.object(search, "evaluate_state", side_effect=lambda d, s: scores[s.label])]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        return states["r"], actions

    def test_full_root_child_windows_do_not_turn_pruned_bounds_into_ties(self):
        root, actions = self.controlled_tree()
        rng = CountingRng()
        selection = self.select(None, root, rng=rng, depth=2, cap=8)
        self.assertEqual(selection.action, actions[0])
        self.assertEqual(selection.completed_depth, 2)
        self.assertEqual(selection.search_transitions, 8)
        self.assertEqual(rng.choices, [(actions[0],)])
        self.assertFalse(selection.budget_exhausted)

    def test_partial_depth_retains_previous_complete_depth_and_single_rng_call(self):
        root, actions = self.controlled_tree(shallow=(1, 9), deep=((100, 100), (0, 0)))
        rng = CountingRng()
        selection = self.select(None, root, rng=rng, depth=2, cap=5)
        self.assertEqual(selection.action, actions[1])
        self.assertEqual(selection.completed_depth, 1)
        self.assertEqual(selection.search_transitions, 5)
        self.assertTrue(selection.budget_exhausted)
        self.assertFalse(selection.fallback)
        self.assertEqual(rng.choices, [(actions[1],)])

    def test_b_minimizes_and_equal_root_ties_are_retained(self):
        root, actions = self.controlled_tree(root_player=Player.B, shallow=(1, 9))
        rng = CountingRng()
        selection = self.select(None, root, "connection-greedy-v1", rng=rng)
        self.assertEqual(selection.action, actions[0])
        self.assertEqual(rng.choices, [(actions[0],)])

    def test_all_equal_root_scores_get_one_final_rng_choice(self):
        root, actions = self.controlled_tree(deep=((5, 5), (5, 5)))
        rng = CountingRng()
        selection = self.select(None, root, rng=rng, depth=2)
        self.assertEqual(selection.action, actions[1])
        self.assertEqual(rng.choices, [actions])

    def test_cpu_expiration_never_returns_an_applied_fallback(self):
        game = definition(size=2)
        rng = CountingRng()
        selection = self.select(game, initial_state(game), rng=rng, expired=lambda: True)
        self.assertIsNone(selection.action)
        self.assertTrue(selection.cpu_expired)
        self.assertFalse(selection.fallback)
        self.assertEqual(selection.search_transitions, 0)
        self.assertEqual(rng.choices, [])

    def test_cpu_after_one_complete_depth_retains_cost_but_no_action(self):
        root, _ = self.controlled_tree()
        original_apply = search.apply_action.side_effect
        calls = [0]
        def apply(d, s, a):
            calls[0] += 1
            return original_apply(d, s, a)
        search.apply_action.side_effect = apply
        rng = CountingRng()
        selection = self.select(None, root, rng=rng, depth=2, expired=lambda: calls[0] >= 3)
        self.assertIsNone(selection.action)
        self.assertTrue(selection.cpu_expired)
        self.assertFalse(selection.fallback)
        self.assertEqual(selection.completed_depth, 1)
        self.assertEqual(selection.search_transitions, 3)
        self.assertEqual(rng.choices, [])

    def test_random_cpu_expiration_after_choice_still_returns_no_action(self):
        game = definition(size=2)
        rng = CountingRng()
        selection = self.select(game, initial_state(game), "random-v1", rng=rng,
                                expired=lambda: bool(rng.choices))
        self.assertIsNone(selection.action)
        self.assertTrue(selection.cpu_expired)
        self.assertFalse(selection.fallback)
        self.assertEqual(len(rng.choices), 1)

    def test_terminal_returns_no_action_and_missing_nonterminal_actions_is_error(self):
        game = definition()
        won = State((1 << 2) | (1 << 4) | (1 << 6), (1 << 0) | (1 << 8),
                    0, 0, Player.A, 5, Player.A)
        self.assertEqual(self.select(game, won), search.Selection(None, 0, 0, False, False, False))
        with patch.object(search, "legal_actions", return_value=()):
            with self.assertRaises(ValueError):
                self.select(game, initial_state(game))

    def test_invalid_limits_and_policy_are_rejected(self):
        game = definition(size=2)
        state = initial_state(game)
        for cap in (-1, True, 1.0, 32769):
            with self.assertRaises(ValueError):
                self.select(game, state, cap=cap)
        for depth in (0, True, 1.0, 4):
            with self.assertRaises(ValueError):
                self.select(game, state, depth=depth)
        with self.assertRaises(ValueError):
            self.select(game, state, "unregistered-policy")


if __name__ == "__main__":
    unittest.main()
