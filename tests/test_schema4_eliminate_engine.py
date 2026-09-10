import random
import unittest
from collections import Counter
from itertools import product
from unittest.mock import patch

from parity_forge.agents import GoalDirectedAgent, MinimaxAgent, goal_progress
from parity_forge.dsl import InitialPiece, Player, parse_definition
from parity_forge.engine import (
    Action,
    GameState,
    apply_action,
    goal_satisfied,
    initial_state,
    legal_actions,
)


def eliminate_definition(
    *,
    a_action="MOVE_CAPTURE",
    a_goal_piece="prey",
    b_goal_piece="hunter",
    max_plies=20,
):
    return {
        "schema_version": 4,
        "name": "Eliminate engine probe",
        "board_size": 3,
        "first_player": "A",
        "max_plies": max_plies,
        "roles": {
            "A": {
                "action": {
                    "kind": a_action,
                    "piece": "hunter" if a_action == "MOVE_CAPTURE" else "converter",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "ELIMINATE",
                    "piece": a_goal_piece,
                },
            },
            "B": {
                "action": {
                    "kind": "MOVE",
                    "piece": "runner",
                    "vectors": [[0, 1]],
                },
                "goal": {
                    "kind": "ELIMINATE",
                    "piece": b_goal_piece,
                },
            },
        },
        "initial_pieces": [],
    }


def canonical_pieces(*pieces):
    return tuple(
        sorted(
            pieces,
            key=lambda piece: (piece.position, piece.owner.value, piece.piece),
        )
    )


def state_with(*pieces, ply=0):
    return GameState(
        ply=ply,
        to_move=Player.A,
        pieces=canonical_pieces(*pieces),
    )


class SchemaV4EliminateEngineTests(unittest.TestCase):
    def test_eliminate_predicate_matches_exhaustive_independent_oracle(self) -> None:
        definition = parse_definition(
            eliminate_definition(a_goal_piece="target", b_goal_piece="target")
        )
        cells = tuple((row, column) for row in range(3) for column in range(3))
        distribution = Counter()
        predicate_checks = 0

        for labels in product(range(3), repeat=len(cells)):
            pieces = []
            has_a_target = False
            has_b_target = False
            for position, label in zip(cells, labels):
                if label == 1:
                    pieces.append(InitialPiece(Player.A, "target", position))
                    has_a_target = True
                elif label == 2:
                    pieces.append(InitialPiece(Player.B, "target", position))
                    has_b_target = True
            frozen = canonical_pieces(*pieces)
            actual_a = goal_satisfied(definition, frozen, Player.A)
            actual_b = goal_satisfied(definition, frozen, Player.B)
            expected_a = not has_b_target
            expected_b = not has_a_target
            self.assertEqual((actual_a, actual_b), (expected_a, expected_b))
            distribution[(actual_a, actual_b)] += 1
            predicate_checks += 2

        self.assertEqual(predicate_checks, 39366)
        self.assertEqual(
            distribution,
            Counter(
                {
                    (False, False): 18660,
                    (True, False): 511,
                    (False, True): 511,
                    (True, True): 1,
                }
            ),
        )

    def test_eliminate_ignores_owned_same_kind_and_opponent_other_kind(self) -> None:
        definition = parse_definition(
            eliminate_definition(a_goal_piece="target", b_goal_piece="target")
        )
        irrelevant = canonical_pieces(
            InitialPiece(Player.A, "target", (0, 0)),
            InitialPiece(Player.B, "other", (1, 1)),
        )
        self.assertTrue(goal_satisfied(definition, irrelevant, Player.A))
        self.assertFalse(goal_satisfied(definition, irrelevant, Player.B))

        with_opponent_target = canonical_pieces(
            *irrelevant,
            InitialPiece(Player.B, "target", (2, 2)),
        )
        self.assertFalse(
            goal_satisfied(definition, with_opponent_target, Player.A)
        )

    def test_initial_zero_targets_for_both_roles_uses_first_player_priority(self) -> None:
        definition = parse_definition(eliminate_definition())
        state = initial_state(definition)

        self.assertTrue(state.terminal)
        self.assertEqual(state.outcome.winner, Player.A)
        self.assertEqual(state.outcome.reason, "GOAL")
        self.assertEqual(state.ply, 0)

    def test_move_capture_distinguishes_last_nonlast_and_wrong_kind_targets(self) -> None:
        definition = parse_definition(eliminate_definition())
        action = Action.move_capture((1, 0), (1, 1))
        hunter = InitialPiece(Player.A, "hunter", (1, 0))
        runner = InitialPiece(Player.B, "runner", (2, 0))

        last = state_with(
            hunter,
            InitialPiece(Player.B, "prey", (1, 1)),
            runner,
        )
        after_last = apply_action(definition, last, action)
        self.assertEqual(after_last.outcome.winner, Player.A)
        self.assertEqual(after_last.outcome.reason, "GOAL")

        nonlast = state_with(
            hunter,
            InitialPiece(Player.B, "prey", (0, 2)),
            InitialPiece(Player.B, "prey", (1, 1)),
            runner,
        )
        after_nonlast = apply_action(definition, nonlast, action)
        self.assertFalse(after_nonlast.terminal)
        self.assertFalse(
            goal_satisfied(definition, after_nonlast.pieces, Player.A)
        )
        self.assertTrue(legal_actions(definition, after_nonlast))

        wrong_kind = state_with(
            hunter,
            InitialPiece(Player.B, "prey", (0, 2)),
            InitialPiece(Player.B, "decoy", (1, 1)),
            runner,
        )
        after_wrong_kind = apply_action(definition, wrong_kind, action)
        self.assertFalse(after_wrong_kind.terminal)
        self.assertFalse(
            goal_satisfied(definition, after_wrong_kind.pieces, Player.A)
        )

    def test_convert_eliminates_same_kind_and_other_kind_opponent_targets(self) -> None:
        for target_kind in ("converter", "prey"):
            with self.subTest(target_kind=target_kind):
                definition = parse_definition(
                    eliminate_definition(
                        a_action="CONVERT",
                        a_goal_piece=target_kind,
                        b_goal_piece="converter",
                    )
                )
                state = state_with(
                    InitialPiece(Player.A, "converter", (1, 0)),
                    InitialPiece(Player.B, target_kind, (1, 1)),
                    InitialPiece(Player.B, "runner", (2, 0)),
                )
                after = apply_action(
                    definition,
                    state,
                    Action.convert((1, 0), (1, 1)),
                )

                self.assertEqual(after.outcome.winner, Player.A)
                self.assertEqual(after.outcome.reason, "GOAL")
                self.assertFalse(
                    any(
                        piece.owner is Player.B and piece.piece == target_kind
                        for piece in after.pieces
                    )
                )

    def test_push_swap_and_hop_do_not_change_eliminate_predicate(self) -> None:
        cases = (
            ("PUSH", Action.push((1, 0), (1, 1)), (1, 2)),
            ("SWAP", Action.swap((1, 0), (1, 1)), (1, 0)),
            ("HOP", Action.hop((1, 0), (1, 2)), (1, 1)),
        )
        for action_kind, action, expected_target_position in cases:
            with self.subTest(action_kind=action_kind):
                raw = eliminate_definition(
                    a_action=action_kind,
                    a_goal_piece="target",
                    b_goal_piece="actor",
                )
                raw["roles"]["A"]["action"]["piece"] = "actor"
                definition = parse_definition(raw)
                state = state_with(
                    InitialPiece(Player.A, "actor", (1, 0)),
                    InitialPiece(Player.B, "target", (1, 1)),
                    InitialPiece(Player.B, "runner", (2, 0)),
                )
                before = goal_satisfied(definition, state.pieces, Player.A)
                after = apply_action(definition, state, action)

                self.assertFalse(before)
                self.assertEqual(
                    goal_satisfied(definition, after.pieces, Player.A),
                    before,
                )
                target = next(
                    piece
                    for piece in after.pieces
                    if piece.owner is Player.B and piece.piece == "target"
                )
                self.assertEqual(target.position, expected_target_position)

    def test_actor_goal_precedes_opponent_goal_and_ply_cap(self) -> None:
        both_definition = parse_definition(
            eliminate_definition(b_goal_piece="phantom", max_plies=1)
        )
        state = state_with(
            InitialPiece(Player.A, "hunter", (1, 0)),
            InitialPiece(Player.B, "prey", (1, 1)),
        )
        after = apply_action(
            both_definition,
            state,
            Action.move_capture((1, 0), (1, 1)),
        )

        self.assertTrue(
            goal_satisfied(both_definition, after.pieces, Player.A)
        )
        self.assertTrue(
            goal_satisfied(both_definition, after.pieces, Player.B)
        )
        self.assertEqual(after.outcome.winner, Player.A)
        self.assertEqual(after.outcome.reason, "GOAL")

    def test_opponent_goal_precedes_ply_cap_and_next_player_immobility(self) -> None:
        definition = parse_definition(
            eliminate_definition(b_goal_piece="phantom", max_plies=1)
        )
        state = state_with(
            InitialPiece(Player.A, "hunter", (1, 0)),
            InitialPiece(Player.B, "prey", (0, 2)),
            InitialPiece(Player.B, "decoy", (1, 1)),
        )
        after = apply_action(
            definition,
            state,
            Action.move_capture((1, 0), (1, 1)),
        )

        self.assertFalse(goal_satisfied(definition, after.pieces, Player.A))
        self.assertTrue(goal_satisfied(definition, after.pieces, Player.B))
        self.assertEqual(after.outcome.winner, Player.B)
        self.assertEqual(after.outcome.reason, "GOAL")

    def test_ply_cap_precedes_stuck_and_plain_stuck_remains_a_loss(self) -> None:
        pieces = (
            InitialPiece(Player.A, "hunter", (1, 0)),
            InitialPiece(Player.B, "prey", (0, 2)),
            InitialPiece(Player.B, "decoy", (1, 1)),
        )
        action = Action.move_capture((1, 0), (1, 1))

        capped_definition = parse_definition(eliminate_definition(max_plies=1))
        after_cap = apply_action(
            capped_definition,
            state_with(*pieces),
            action,
        )
        self.assertIsNone(after_cap.outcome.winner)
        self.assertEqual(after_cap.outcome.reason, "PLY_LIMIT")

        stuck_definition = parse_definition(eliminate_definition(max_plies=2))
        after_stuck = apply_action(
            stuck_definition,
            state_with(*pieces),
            action,
        )
        self.assertEqual(after_stuck.outcome.winner, Player.A)
        self.assertEqual(after_stuck.outcome.reason, "NO_LEGAL_ACTION")

    def test_v1_heuristic_agents_fail_closed_before_work_or_rng_use(self) -> None:
        for eliminate_player in (Player.A, Player.B):
            with self.subTest(eliminate_player=eliminate_player):
                raw = eliminate_definition()
                other = eliminate_player.other.value
                raw["roles"][other]["goal"] = {
                    "kind": "REACH_EDGE",
                    "piece": "runner",
                    "edge": "RIGHT",
                }
                definition = parse_definition(raw)
                state = state_with(
                    InitialPiece(Player.A, "hunter", (1, 0)),
                    InitialPiece(Player.B, "prey", (1, 1)),
                )
                actions = (Action.move_capture((1, 0), (1, 1)),)

                with self.assertRaisesRegex(ValueError, "ELIMINATE"):
                    goal_progress(definition, state, eliminate_player)

                for agent in (GoalDirectedAgent(), MinimaxAgent(depth=2)):
                    rng = random.Random(9182)
                    before_rng = rng.getstate()
                    if isinstance(agent, MinimaxAgent):
                        agent.total_nodes = 7
                    with patch(
                        "parity_forge.agents.apply_action",
                        side_effect=AssertionError("action application must not run"),
                    ):
                        with self.assertRaisesRegex(ValueError, "ELIMINATE"):
                            agent.select_action(definition, state, actions, rng)
                    self.assertEqual(rng.getstate(), before_rng)
                    if isinstance(agent, MinimaxAgent):
                        self.assertEqual(agent.total_nodes, 7)


if __name__ == "__main__":
    unittest.main()
