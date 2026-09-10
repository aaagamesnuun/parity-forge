from dataclasses import replace
import random
import unittest

from parity_forge.dsl import Player
from parity_forge.finite_space import initial_state, legal_actions, parse_definition
from parity_forge.finite_space_search import Budget, mobility_value, select_action, short_win


def search_fixture(width=3, a_single=True):
    """Exactly three canonical search fixtures, shared with batch tests."""
    singleton, domino = [[[0, 0]]], [[[0, 0], [0, 1]]]
    return {
        "format": "parity-forge:finite-space:v1", "id": "search-control",
        "board": {"rows": 1, "cols": width, "blocked": []},
        "first_player": "A", "terminal_rule": "NO_LEGAL_ACTION_LOSES",
        "roles": {
            "A": {"kind": "TILE", "shapes": singleton if a_single else domino},
            "B": {"kind": "TILE", "shapes": singleton if width == 4 and not a_single else domino},
        },
    }


class FiniteSpaceSearchTests(unittest.TestCase):
    def setUp(self):
        self.definition = parse_definition(search_fixture())
        self.state = initial_state(self.definition)

    def test_goal_directed_policies_find_hand_proved_middle_win(self):
        for policy in ("deny-v1", "mobility-search-v1"):
            action, info = select_action(
                self.definition, self.state, policy, random.Random(8), 100, 2)
            self.assertEqual(action.cells, (1,))
            self.assertGreaterEqual(info["completed_depth"], 1)
            self.assertFalse(info["fallback"])

    def test_proof_matches_hand_complete_trees(self):
        self.assertIs(short_win(self.definition, Player.A, 1, 20)["forced_win"], True)
        self.assertIs(short_win(self.definition, Player.B, 3, 20)["forced_win"], False)
        other = parse_definition(search_fixture(4, False))
        self.assertIs(short_win(other, Player.B, 2, 30)["forced_win"], True)
        self.assertIs(short_win(other, Player.A, 3, 30)["forced_win"], False)

    def test_zero_horizon_is_not_eventual_loss(self):
        answer = short_win(self.definition, Player.A, 0, 0)
        self.assertEqual(answer["status"], "COMPLETE")
        self.assertIs(answer["forced_win"], False)
        self.assertEqual(answer["nodes"], 0)

    def test_exhausted_proof_is_unknown_not_false_or_draw(self):
        answer = short_win(self.definition, Player.A, 1, 0)
        self.assertEqual(answer["status"], "UNKNOWN")
        self.assertIsNone(answer["forced_win"])
        self.assertEqual(answer["nodes"], 0)

    def test_exhausted_policy_keeps_last_complete_iteration(self):
        action, info = select_action(
            self.definition, self.state, "mobility-search-v1", random.Random(1), 3, 2)
        self.assertEqual(action.cells, (1,))
        self.assertEqual(info["completed_depth"], 1)
        self.assertTrue(info["budget_exhausted"])
        self.assertEqual(info["nodes"], 3)
        self.assertFalse(info["fallback"])

    def test_no_complete_iteration_is_explicit_legal_fallback(self):
        action, info = select_action(
            self.definition, self.state, "deny-v1", random.Random(1), 1, 2)
        self.assertIn(action, legal_actions(self.definition, self.state))
        self.assertTrue(info["fallback"])
        self.assertTrue(info["budget_exhausted"])
        self.assertEqual(info["nodes"], 1)

    def test_deterministic_policy_and_random_is_unsearched(self):
        one = select_action(self.definition, self.state, "random-v1", random.Random(3), 0)
        two = select_action(self.definition, self.state, "random-v1", random.Random(3), 0)
        self.assertEqual(one, two)
        self.assertEqual(one[1]["nodes"], 0)
        self.assertFalse(one[1]["fallback"])

    def test_invalid_budgets_and_policies_fail(self):
        for limit in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                Budget(limit)
        with self.assertRaises(ValueError):
            select_action(self.definition, self.state, "mystery", random.Random(0), 10)
        with self.assertRaises(ValueError):
            short_win(self.definition, Player.A, True, 10)
        with self.assertRaises(ValueError):
            Budget(10, used=False)
        with self.assertRaises(TypeError):
            Budget(10, expired=1)

    def test_forged_terminal_is_not_accepted_by_proof_or_heuristic(self):
        forged = replace(self.state, winner=Player.B)
        with self.assertRaises(ValueError):
            short_win(self.definition, Player.B, 1, 10, state=forged)
        with self.assertRaises(ValueError):
            mobility_value(self.definition, forged)

    def test_cpu_deadline_inside_proof_is_unknown(self):
        answer = short_win(self.definition, Player.A, 1, 20, cpu_expired=lambda: True)
        self.assertEqual(answer["status"], "UNKNOWN")
        self.assertIsNone(answer["forced_win"])
        self.assertEqual(answer["nodes"], 0)


if __name__ == "__main__":
    unittest.main()
