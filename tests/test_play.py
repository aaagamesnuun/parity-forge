import unittest

from parity_forge.agents import (
    GoalDirectedAgent,
    MinimaxAgent,
    RandomAgent,
    SearchBudgetExceeded,
)
from parity_forge.dsl import Player, parse_definition
from parity_forge.play import evaluate_matchup, play_game, profile_disagreement

from tests.support import crossing_definition


class PlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definition = parse_definition(crossing_definition())

    def test_seeded_random_play_is_reproducible(self) -> None:
        agent = RandomAgent()
        agents = {Player.A: agent, Player.B: agent}
        self.assertEqual(
            play_game(self.definition, agents, 12345),
            play_game(self.definition, agents, 12345),
        )

    def test_agents_only_emit_legal_complete_games(self) -> None:
        agent = GoalDirectedAgent()
        record = play_game(self.definition, {Player.A: agent, Player.B: agent}, 7)
        self.assertGreater(record.plies, 0)
        self.assertLessEqual(record.plies, self.definition.max_plies)
        self.assertIn(record.terminal_reason, {"GOAL", "NO_LEGAL_ACTION", "PLY_LIMIT"})

    def test_matchup_separates_draws_and_is_reproducible(self) -> None:
        agent = RandomAgent()
        agents = {Player.A: agent, Player.B: agent}
        first = evaluate_matchup(self.definition, "weak", agents, range(20))
        second = evaluate_matchup(self.definition, "weak", agents, range(20))
        self.assertEqual(first, second)
        self.assertEqual(first.a_wins + first.b_wins + first.draws, first.samples)
        if first.decisive_a_wilson_95 is not None:
            low, high = first.decisive_a_wilson_95
            self.assertLessEqual(low, first.decisive_a_share)
            self.assertGreaterEqual(high, first.decisive_a_share)

    def test_schema_v2_stalemate_draw_propagates_through_sampled_play(self) -> None:
        raw = crossing_definition()
        raw["schema_version"] = 2
        raw["terminal_policy"] = {"no_legal_action": "DRAW"}
        raw["roles"]["B"]["action"]["vectors"] = [[1, 0]]
        definition = parse_definition(raw)

        for profile, agent in (
            ("weak-random", RandomAgent()),
            ("medium-goal-directed", GoalDirectedAgent()),
            ("minimax-v1-depth2", MinimaxAgent(depth=2)),
        ):
            with self.subTest(profile=profile):
                result = evaluate_matchup(
                    definition,
                    profile,
                    {Player.A: agent, Player.B: agent},
                    range(3),
                )
                self.assertEqual((result.a_wins, result.b_wins, result.draws), (0, 0, 3))
                self.assertEqual(dict(result.terminal_reasons), {"NO_LEGAL_ACTION": 3})
                self.assertIsNone(result.decisive_a_share)
                self.assertIsNone(result.decisive_a_wilson_95)
                self.assertTrue(
                    all(
                        record.winner is None
                        and record.terminal_reason == "NO_LEGAL_ACTION"
                        and record.plies == 1
                        for record in result.records
                    )
                )

    def test_duplicate_or_empty_seed_sets_are_rejected(self) -> None:
        agent = RandomAgent()
        agents = {Player.A: agent, Player.B: agent}
        with self.assertRaisesRegex(ValueError, "at least one"):
            evaluate_matchup(self.definition, "weak", agents, [])
        with self.assertRaisesRegex(ValueError, "unique"):
            evaluate_matchup(self.definition, "weak", agents, [1, 1])

    def test_profile_disagreement_threshold(self) -> None:
        random_agent = RandomAgent()
        directed = GoalDirectedAgent()
        weak = evaluate_matchup(
            self.definition,
            "weak",
            {Player.A: random_agent, Player.B: random_agent},
            range(30),
        )
        medium = evaluate_matchup(
            self.definition,
            "medium",
            {Player.A: directed, Player.B: directed},
            range(30),
        )
        expected = abs(weak.decisive_a_share - medium.decisive_a_share) >= 0.15
        self.assertEqual(profile_disagreement((weak, medium)), expected)

    def test_minimax_play_is_seeded_and_complete(self) -> None:
        agent = MinimaxAgent(depth=2)
        agents = {Player.A: agent, Player.B: agent}
        first = play_game(self.definition, agents, 91)
        second = play_game(self.definition, agents, 91)
        self.assertEqual(first, second)
        self.assertGreater(first.plies, 0)

    def test_minimax_node_budget_is_deterministic(self) -> None:
        agent = MinimaxAgent(depth=5, max_nodes_per_move=1)
        with self.assertRaises(SearchBudgetExceeded) as raised:
            play_game(self.definition, {Player.A: agent, Player.B: agent}, 1)
        self.assertEqual(raised.exception.scope, "per-move")
        self.assertEqual(raised.exception.visited_nodes, 1)
        self.assertEqual(raised.exception.max_nodes, 1)

    def test_minimax_candidate_budget_accumulates_across_moves(self) -> None:
        agent = MinimaxAgent(depth=2, max_total_nodes=10)
        with self.assertRaises(SearchBudgetExceeded) as raised:
            play_game(self.definition, {Player.A: agent, Player.B: agent}, 1)
        self.assertEqual(raised.exception.scope, "per-candidate")
        self.assertEqual(raised.exception.visited_nodes, 10)


if __name__ == "__main__":
    unittest.main()
