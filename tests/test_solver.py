import unittest

from parity_forge.dsl import parse_definition
from parity_forge.solver import SolveBudgetExceeded, solve_game

from tests.support import crossing_definition


class SolverTests(unittest.TestCase):
    def test_immediate_a_win_is_proven(self) -> None:
        raw = crossing_definition()
        raw["initial_pieces"].extend(
            [
                {"owner": "A", "piece": "seed", "position": [0, 0]},
                {"owner": "A", "piece": "seed", "position": [1, 0]},
            ]
        )
        result = solve_game(parse_definition(raw))
        self.assertEqual(result.forced_result, "A_WIN")
        self.assertGreaterEqual(len(result.principal_variation), 1)
        self.assertEqual(result.terminal_reason, "GOAL")

    def test_one_ply_without_goal_is_draw(self) -> None:
        raw = crossing_definition()
        raw["max_plies"] = 1
        result = solve_game(parse_definition(raw))
        self.assertEqual(result.forced_result, "DRAW")
        self.assertEqual(len(result.principal_variation), 1)

    def test_solve_is_reproducible(self) -> None:
        definition = parse_definition(crossing_definition())
        self.assertEqual(solve_game(definition), solve_game(definition))

    def test_exact_state_budget_is_deterministic(self) -> None:
        definition = parse_definition(crossing_definition())
        with self.assertRaises(SolveBudgetExceeded) as raised:
            solve_game(definition, max_states=1)
        self.assertEqual(raised.exception.searched_states, 1)
        self.assertEqual(raised.exception.max_states, 1)


if __name__ == "__main__":
    unittest.main()
